/*
 * 	This Java class , has been developed as part of the SAIL project. 
 * 	(http://sail-project.eu)
 * 	
 *  Specification(s) - note, versions may change::
 * 	-	http://tools.ietf.org/html/farrell-decade-ni-00
 * 	-	http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00
 * 
 * 	Authors: 	Petteri Pöyhönen <petteri.poyhonen@nsn.com> 	
 * 				Janne Tuonnonen <janne.tuononen@nsn.com> 				
 * 
 *  Copyright: 	Copyright 2012 Petteri Pöyhönen <petteri.poyhonen@nsn.com> and
 *  			Janne Tuonnonen <janne.tuononen@nsn.com>, Nokia Siemens Networks
 *	
 *  License: http://www.apache.org/licenses/LICENSE-2.0
 *  
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  
 *  See the License for the specific language governing permissions and
 *  limitations under the License. 	 	
 */
package niproxy;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.io.UnsupportedEncodingException;
import java.net.URLDecoder;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import niproxy.data.CacheControl;
import niproxy.data.InMemoryDB;
import niproxy.data.NotationUtils;
import niproxy.data.NiPublishForm;
import niproxy.data.PublishEntryValue;
import niproxy.data.impl.CacheControlImpl;
import niproxy.data.impl.InMemoryDBImpl;

import org.apache.http.Header;
import org.apache.http.HttpEntity;
import org.apache.http.HttpEntityEnclosingRequest;
import org.apache.http.HttpException;
import org.apache.http.HttpHost;
import org.apache.http.HttpInetConnection;
import org.apache.http.HttpRequest;
import org.apache.http.HttpResponse;
import org.apache.http.HttpStatus;
import org.apache.http.HttpVersion;
import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.entity.InputStreamEntity;
import org.apache.http.impl.client.DefaultHttpClient;
import org.apache.http.nio.ContentDecoder;
import org.apache.http.nio.IOControl;
import org.apache.http.nio.entity.ConsumingNHttpEntity;
import org.apache.http.nio.entity.ConsumingNHttpEntityTemplate;
import org.apache.http.nio.entity.ContentListener;
import org.apache.http.nio.protocol.NHttpRequestHandler;
import org.apache.http.nio.protocol.NHttpResponseTrigger;
import org.apache.http.protocol.HttpContext;
import org.apache.log4j.Logger;
import org.json.simple.JSONValue;


/**
 * Implementation of the {@link NHttpRequestHandler} to be used in {@link NiProxy}. 
 */
public class NiProxyMonitor implements NHttpRequestHandler {
	
	/** The Constant DBHandler. */
	private final static InMemoryDB DBHandler = new InMemoryDBImpl();
	
	/** The Constant parser. */
	private final static MessageParser parser = new MessageParserImpl();
	
	/** The post buffer. */
	private static ByteBuffer postBuffer;
	
  /**
	 * The Class NIRequestHandler.
	 */
  private static class NIRequestHandler implements Runnable {

  /**
   * Checks whether the {@link String} name follows the predefined publish format.
   * 	  
   * @param name	{@link String} to be inspected.
   * @return		<code>true</code> if the name is constructed according to the 
   * 				publish format; <code>false</code> otherwise.
   */
   private static boolean isPublish(String name) {
		if (name.contains(".well-known/netinfproto/publish"))
		return true;
	return false;
	}

   /**
    * Checks whether the {@link String} name follows the predefined get format.
    * 	  
    * @param name	{@link String} to be inspected.
    * @return		<code>true</code> if the name is constructed according to the 
    * 				get format; <code>false</code> otherwise.
    */
	private static boolean isGet(String name) {
		if (name.contains(".well-known/netinfproto/get"))
			return true;
		return false;
	}

   /**
	 * Checks whether the {@link String} url follows the predefined get format
	 * and is POST message.
	 * 
	 * @param url
	 *            the url
	 * @param methodName
	 *            the method name
	 * @return <code>true</code> if the url is constructed according to the get
	 *         format and method name is POST; <code>false</code> otherwise.
	 */	
    private static boolean isPostGet(String url, String methodName) {
    	// We will handle this only if
    	// i) this is GET or POST, and
    	if (!methodName.equalsIgnoreCase("POST")) {
    		return false;
    	}
    	// ii) url is well-known get
    	if (isGet(url))
    		return true;
    	return false;
    }

    /**
	 * Checks whether the {@link String} url follows the predefined publish
	 * format and is POST message.
	 * 
	 * @param url
	 *            the url
	 * @param methodName
	 *            the method name
	 * @return <code>true</code> if the url is constructed according to the
	 *         publish format and method name is POST; <code>false</code>
	 *         otherwise.
	 */	    
    private static boolean isPostPublish(String url, String methodName) {
    	// Publish() only if
    	// i) this is POST, and
    	if (!methodName.equalsIgnoreCase("POST")) {
    		return false;
    	}
    	// ii) url is well-known publish
    	if (isPublish(url))
    		return true;
    	return false;
    }

    /** The context. */
    private final HttpContext context;

    /** The request. */
    private final HttpRequest request;

    /** The response. */
    private final HttpResponse response;

    /** The trigger. */
    private final NHttpResponseTrigger trigger;
    
    /**
	 * Instantiates a new nI request handler.
	 * 
	 * @param request
	 *            the request
	 * @param response
	 *            the response
	 * @param trigger
	 *            the trigger
	 * @param context
	 *            the context
	 */
    public NIRequestHandler(HttpRequest request, HttpResponse response, NHttpResponseTrigger trigger,
        HttpContext context) {
      this.request = request;
      this.response = response;
      this.trigger = trigger;
      this.context = context;
    }
    
    /**
     * Creates a new {@link HttpEntity} containing the given file. 
     * @param filename					Filename of the file to be included in the new {@link HttpEntity}.
     * @return							New {@link HttpEntity} constructed around the file and in case of 
     * 									error, then null otherwise.
     * @throws FileNotFoundException	If file is not found.
     */
    private HttpEntity createNewHttpEntity(String filename) throws FileNotFoundException {
    	FileInputStream fStream = null;
    	File f = new File(filename);
    	long cLen=f.length();
    	
    	if (0==cLen)
    		return null;
    	
    	logger.info("File length: "+cLen);
		fStream = new FileInputStream(filename);
    	byte[] buffer = new byte[(int) cLen];
    	
		try {
			for (int i=0; i<cLen; i++) {
				buffer[i]=(byte) fStream.read();
			}
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		try {
			fStream.close();
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		logger.debug("Read "+buffer.length+" bytes");	
    	InputStream iStream = new ByteArrayInputStream(buffer);
    	HttpEntity newEntity = new InputStreamEntity(iStream, cLen);
    	logger.debug("New Content Length: "+newEntity.getContentLength());
    	return newEntity;
    }
    
    /**
     * Gets the boundary string from the given header.
     *  
     * @param data 	Header to be inspected.
     * @return		Boundary string.
     */
    private static String getBoundaryString(Header data) {
    	return data.getValue().substring(data.getValue().indexOf("boundary=")+"boundary=".length(), data.getValue().length());
    }

    /**
     * Processes the publish message. The message is parsed and publications DB is updated accordingly.
     * 
     * @param incomingEntity	{@link HttpEntity} to be processed.
     * @param url				Url from the publish message.
     * @return					<code>true</code> if the publish processing was successful; <code>false</code> otherwise.
     */
    private static boolean handlePublish(HttpEntity incomingEntity, String url) {
    	ByteArrayInputStream is = null;
        Header ct = null;
        NiPublishForm form = new NiPublishForm();
        
    	ct = incomingEntity.getContentType();
        logger.debug("ContentLength: "+incomingEntity.getContentLength());
  	    is = new ByteArrayInputStream(postBuffer.array());
  	    form = parser.parsePublishMessage(is, getBoundaryString(ct));
  	    if (null==form) {
  	    	// Something wrong, return false
  	    	return false;
  	    }
  	    String[] keyParts = NotationUtils.expandNotation(form.getUri());
  	    logger.debug("key[0]: "+keyParts[0]);
  	    logger.debug("key[1]: "+keyParts[1]);
  	    DBHandler.AddPublication(keyParts[0], keyParts[1], form.getloc());
    	return true;
    }
    
    /**
	 * Converts {@link InputStream} to {@link String}.
	 * 
	 * @param bais
	 *            Input data to be converted.
	 * @return Converted data.
	 */
    private static String toString(ByteArrayInputStream bais) {
        int size = bais.available();
        char[] c = new char[size];
        byte[] b = new byte[size];

        bais.read(b, 0, size);
        for (int i = 0; i < size;)
            c[i] = (char)(b[i++]&0xff); 
        return new String(c);
    }    
    
    /**
     * Checks whether header is encoded according to the predefined get encoding type.
     * 
     * @param h	Header to be inspected.
     * @return	<code>true</code> if get encoded; <code>false</code> otherwise.
     */
    private static boolean isGetEncoded(Header h) {
    	if (h.toString().contains("application/x-www-form-urlencoded"))
    		return true;
    	return false;
    }
    
    /**
     * Processes the get message. The message is parsed and the parsed url is returned.
     * 
     * @param incomingEntity	{@link HttpEntity} to be processed.
     * @param url				Url from the get message.
     * @return					Parsed url if the processing was successful; otherwise <code>null</code>.
     */
    private static String handleGet(HttpEntity incomingEntity, String url) {
    	ByteArrayInputStream is = null;
        Header ct = null;
 	        
    	ct = incomingEntity.getContentType();
    	// Check that encoding is correct
    	if (null==ct || !isGetEncoded(ct)) {
    		logger.error("GET ERROR (Wrong content type): "+ct);
    		return null;
    	}
        System.out.println("ContentLength: "+incomingEntity.getContentLength());
  	    is = new ByteArrayInputStream(postBuffer.array());
  	    String parsedData = new String();
  	    try {
			parsedData=URLDecoder.decode(toString(is), "UTF-8");
		} catch (UnsupportedEncodingException e) {
			e.printStackTrace();
		}
  	    logger.debug("parsedUrl: "+parsedData);
  	    if (null==parsedData) {
  	    	// Something wrong, return false
  	    	return null;    	  
  	    }
  	    String key = parsedData.substring(parsedData.indexOf("=")+1,parsedData.indexOf("&"));
  	    logger.debug("key: "+key);
    	return key;
    }
    
    /**
     * Checks if data represents Unix file name.
     * 
     * @param data	Data to be inspected.
     * @return		<code>true</code> if Unix file name; <code>false</code> otherwise.
     */
    private boolean isUnixFilename(String data) {
    	if (null!=data && data.contains("file:///"))
    		return true;
    	return false;
    }

    //TO DO: Further detail the used file name prefix in Windows OSes. 
    /**
     * Checks if data represents Windows file name.
     * 
     * @param data	Data to be inspected.
     * @return		<code>true</code> if Windows file name; <code>false</code> otherwise.
     */    
    private boolean isWinFilename(String data) {
        if (null!=data && data.contains("file:"))
    		return true;
    	return false;
    }
    
    /* (non-Javadoc)
     * @see java.lang.Runnable#run()
     */
    @SuppressWarnings({ "rawtypes", "unchecked" })
	@Override
    public void run() {
        // split the request url to request and query parts
        String url = request.getRequestLine().getUri();
                
        // Check if this is PUBLISH()
        if (isPostPublish(url, request.getRequestLine().getMethod())) {
      	  if (isMultiPart(request)) {
  	        if (request instanceof HttpEntityEnclosingRequest) {
  	        	if (!handlePublish(((HttpEntityEnclosingRequest) request).getEntity(), url)) {
  	        		// Error
  	        		response.setStatusLine(HttpVersion.HTTP_1_1, 403);
  	        		logger.info("PUBLISH ERROR: "+url);
  	        	} else {
  	        		// All ok
  	        		response.setStatusLine(HttpVersion.HTTP_1_1, 200);
  	        		logger.info("PUBLISH OK: "+url);
  	        	}  	        
  	        	// Send response
  	        	trigger.submitResponse(response);
  	        	return;
  	        }  	
      	  }
        }
      
      if (isPostGet(url, request.getRequestLine().getMethod())) {
    	  // Check if the requested content is in our cache
    	  String parsedUrl=null;
    	  if (request instanceof HttpEntityEnclosingRequest) {
    		  parsedUrl = handleGet(((HttpEntityEnclosingRequest) request).getEntity(), url);
    		  if (null==parsedUrl) {
    			  // Error, so lets send 403 error back
	    		  logger.error("GET ERROR (Corrupted msg): "+parsedUrl);
	    		  response.setStatusLine(HttpVersion.HTTP_1_1, 403);
		          trigger.submitResponse(response);
		    	  return;
    		  }
    		  // Check our publications
    		  String[] keys = NotationUtils.expandNotation(parsedUrl);
    		  if (2>keys.length) {
    			  // No hast value given in the url, so stop and generate error
    			  setErrorResponse(response);
    			  logger.error("GET ERROR: No hash value given in the url.");
    			  trigger.submitResponse(response);
    			  return;
    		  }
    		  PublishEntryValue locList = DBHandler.GetLocList(keys[0],keys[1]);
    		  if (null==locList || 1>locList.getSize()) {
    			  // We have no matching entries for the request, so lets send 404 error back
    			  setErrorResponse(response);
    			  logger.error("GET ERROR: No mappings found.");
    			  trigger.submitResponse(response);
    			  return;
    		  }
    		  Set<String> locs = locList.getLocList();    		  
    		  List<String> list = new ArrayList<String>(locs);    		  
    		  // Check if we have to return file or a list of locs
    		  HttpEntity newEntity=null;
    		  if (isUnixFilename(list.get(0)) || isWinFilename(list.get(0))) {
    			  try {
    				  // Remove leading "file://"
    				  String realFilename=list.get(0).substring("file://".length(), list.get(0).length()); 
    				  logger.debug("realFilename: "+realFilename);
    				  newEntity = createNewHttpEntity(realFilename);
    			  } catch (FileNotFoundException e) {
    				  // TODO Auto-generated catch block
	    			  setErrorResponse(response);
	    			  logger.error("GET ERROR: FileNotFoundException "+e);
	    			  trigger.submitResponse(response);
	    			  return;
    			  }
    			  response.addHeader("Content-Type","application/octet-stream");
    			  logger.info("GET OK (ndo): "+list.get(0));
    		  } else {
    			  LinkedList llist = new LinkedList();
	    		  for (int i=0; i<list.size(); i++) {
	    			  llist.add(list.get(i));
	    		  }
	    		  String jsonText = JSONValue.toJSONString(list);
	    		  InputStream iStream = null;
	    		  try {
	    			  iStream = new ByteArrayInputStream(jsonText.getBytes("UTF-8"));
	    		  } catch (UnsupportedEncodingException e1) {
	    			  // Error, so lets send 404 error back
	    			  setErrorResponse(response);
	    			  logger.error("GET ERROR: UnsupportedEncodingException "+e1);
	    			  trigger.submitResponse(response);
	    			  return;
	    		  }
	    	      newEntity = new InputStreamEntity(iStream, jsonText.length());
	    	      response.addHeader("Content-Type","application/json");
	    	      logger.info("GET OK (locs): "+jsonText);
    		  }
    		  response.setEntity(newEntity);
    		  response.setStatusLine(HttpVersion.HTTP_1_1, 200);
    		  trigger.submitResponse(response);
    		  return;
	      } else {
	    	  // Lets call transparent handler, which will act as a http proxy
	    	  new TransparentRequestHandler(request, response, trigger, context).run();
	      }
	   } else {
		   // Lets call transparent handler, which will act as a http proxy
		   new TransparentRequestHandler(request, response, trigger, context).run();
      }
    }
            
    /**
     * Sets 404 HTTP error message code to the response.
     * 
     * @param response {@link HttpResponse} message to be edited.
     */
	private void setErrorResponse(HttpResponse response) {
      logger.debug("Setting error message to file not found.");
      response.setStatusLine(HttpVersion.HTTP_1_1, HttpStatus.SC_NOT_FOUND, "Not Found");
    }
  }

  /**
   * 
   * If no NetInf/Ni specific processing was needed, then this handler is called and it is
   * acting as a standard http proxy.
   *
   */
  private static class TransparentRequestHandler implements Runnable {

    /** The context. */
    private final HttpContext context;
    
    /** The request. */
    private final HttpRequest request;
    
    /** The response. */
    private final HttpResponse response;
    
    /** The trigger. */
    private final NHttpResponseTrigger trigger; 

    /**
	 * Instantiates a new transparent request handler.
	 * 
	 * @param request
	 *            the request
	 * @param response
	 *            the response
	 * @param trigger
	 *            the trigger
	 * @param context
	 *            the context
	 */
    public TransparentRequestHandler(HttpRequest request, HttpResponse response, NHttpResponseTrigger trigger,
        HttpContext context) {
      this.request = request;
      this.response = response;
      this.context = context;
      this.trigger = trigger;
    }

    /* (non-Javadoc)
     * @see java.lang.Runnable#run()
     */
    @Override
    public void run() {
    	    	    	
      DefaultHttpClient client = new DefaultHttpClient();
      HttpInetConnection conn = null;
      HttpResponse resp;
      
      try {                
    	logger.debug("Serving as normal (non-cacheable) proxy for "+request.getRequestLine().getUri());
    	// We just serve this request as normal proxy, i.e., no need to intercept the response
    	if (HttpGet.METHOD_NAME.equalsIgnoreCase(request.getRequestLine().getMethod())) {
          HttpGet get = new HttpGet(request.getRequestLine().getUri());
          resp = client.execute(get);
    	} else {
          HttpHost host2 = new HttpHost(conn.getRemoteAddress().getHostName(), conn.getRemotePort());
          resp = client.execute(host2, request);
        }
        	
        response.setEntity(resp.getEntity());
        response.setStatusLine(resp.getStatusLine());
        trigger.submitResponse(response);

      } catch (ClientProtocolException e) {
        trigger.handleException(new HttpException("Client exception", e));
      } catch (IOException e) {
        trigger.handleException(e);
      } catch (Exception e) {
        // proxy error so reply with HTTP STATUS 502 BADGATEWAY
        logger.error("Unhandled exception: " + e + " Responding with HTTP 502 (Gateway error)");
        response.setStatusLine(HttpVersion.HTTP_1_1, 502);
        trigger.submitResponse(response);
      }
    }
  }

  /** The instance. */
  private static NiProxyMonitor instance = new NiProxyMonitor();
  
  /** The logger. */
  private static Logger logger = Logger.getLogger(NiProxyMonitor.class);

  /**
	 * Gets the.
	 * 
	 * @return the ni proxy monitor
	 */
  public static NiProxyMonitor get() {
    return instance;
  }

  /**
   * Checks whether the {@link HttpRequest} is multi-part message.
   * 
   * @param request Request to be inspected.
   * @return		<code>true</code> if multi-part message; <code>false</code> otherwise.
   */
  public static boolean isMultiPart(HttpRequest request) {
	Header[] allHeaders = request.getAllHeaders();
	
	for (Header header : allHeaders) {
		if (header.getName().contains("Content-Type")) {
			if (header.getValue().contains("multipart/form-data")) {
				return true;
			}
		}
	}
	return false;
}

/** The executor. */
private final ExecutorService executor;

  /**
	 * Instantiates a new ni proxy monitor.
	 */
  private NiProxyMonitor() {
    executor = Executors.newCachedThreadPool();
  }

  /* (non-Javadoc)
   * @see org.apache.http.nio.protocol.NHttpRequestHandler#handle(org.apache.http.HttpRequest, org.apache.http.HttpResponse, org.apache.http.nio.protocol.NHttpResponseTrigger, org.apache.http.protocol.HttpContext)
   */
  @Override
  public void handle(HttpRequest request, HttpResponse response, NHttpResponseTrigger trigger, HttpContext context)
      throws HttpException, IOException {
    if (request.getRequestLine().getMethod().equalsIgnoreCase(HttpGet.METHOD_NAME) || request.getRequestLine().getMethod().equalsIgnoreCase("POST")) {
      // Check if the request should be handled
      executor.execute(new NIRequestHandler(request, response, trigger, context));
    } else {
      // execute the request through the proxy
      executor.execute(new TransparentRequestHandler(request, response, trigger, context));
    }
  }

/* (non-Javadoc)
 * @see org.apache.http.nio.protocol.NHttpRequestHandler#entityRequest(org.apache.http.HttpEntityEnclosingRequest, org.apache.http.protocol.HttpContext)
 */
@Override
public ConsumingNHttpEntity entityRequest(HttpEntityEnclosingRequest request,
		HttpContext context) throws HttpException, IOException {
	return new ConsumingNHttpEntityTemplate(
            request.getEntity(),
            new contentListenerImpl(request.getEntity().getContentLength()));
	}

/**
 * The Class contentListenerImpl.
 */
static class contentListenerImpl implements ContentListener { 
	
	/** The len. */
	private final long len;
	
	/** The bytes. */
	private byte[] bytes=null;
	
	/** The bb. */
	private ByteBuffer bb=null;
	
	/**
	 * Instantiates a new content listener impl.
	 * 
	 * @param readLen
	 *            the read len
	 */
	public contentListenerImpl(long readLen) {
		this.len=readLen;
		logger.debug("Input data size: "+len);
	}
		
	/**
	 * Reads all data from POST message. This might consists of multiple reads
	 * through {@link ContentDecoder}
	 * 
	 * @param arg0
	 *            the arg0
	 * @param arg1
	 *            the arg1
	 * @throws IOException
	 *             Signals that an I/O exception has occurred.
	 */
	@Override
	public void contentAvailable(ContentDecoder arg0, IOControl arg1)
			throws IOException {
		if (null==bytes) {
			bytes = new byte[(int) len];
			bb = ByteBuffer.wrap(bytes);
		    
			// Create a non-direct ByteBuffer with a 'len' byte capacity
			// The underlying storage is a byte array.
			bb = ByteBuffer.allocate((int) len);
		}
		arg0.read(bb);
		 
		if (arg0.isCompleted()) {
			postBuffer = bb;
			bb.rewind();
		}
		logger.debug("arg0: "+arg0+" - IOControl: "+arg1);
	}

	/* (non-Javadoc)
	 * @see org.apache.http.nio.entity.ContentListener#finished()
	 */
	@Override
	public void finished() {
		logger.debug("Finishing a session");
	}
	
}

}
