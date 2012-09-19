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
import java.io.ByteArrayOutputStream;  
import java.io.IOException;  
import java.io.InputStream;

import niproxy.data.CacheControl;
import niproxy.data.NiPublishForm;
import niproxy.data.impl.CacheControlImpl;

import org.apache.james.mime4j.MimeException;
import org.apache.james.mime4j.message.BinaryBody;  
import org.apache.james.mime4j.message.Entity;  
import org.apache.james.mime4j.message.Message;  
import org.apache.james.mime4j.message.TextBody;  
import org.apache.james.mime4j.parser.Field;
import org.apache.james.mime4j.message.MessageBuilder;
import org.apache.james.mime4j.parser.ContentHandler;
import org.apache.james.mime4j.parser.MimeEntityConfig;
import org.apache.james.mime4j.parser.MimeStreamParser;
import org.apache.james.mime4j.storage.MemoryStorageProvider;
import org.apache.log4j.Logger;

/**
 * Default implementation of MessageParser interface.
 */
public class MessageParserImpl implements MessageParser {  
    
    /** The txt body. */
    private StringBuffer txtBody;  
    
    /** The Opt name. */
    private final String OptName = "name=";
    
    /** The File name. */
    private final String FileName = "filename=";
    
    /** The Constant cacheHandler. */
    private final static CacheControl cacheHandler = new CacheControlImpl();    
    
    /** The Constant logger. */
    private final static Logger logger = Logger.getLogger(MessageParserImpl.class);

    /**
     * Parse the provided message as {@link InputStream} and fill up a new {@link NiPublishForm} form 
     * using the parsed data. Additionally, if the message contains a (binary) file, then the file is stored 
     * to the predefined cache root in the local file system.
     * 
	 * @param data		{@link InputStream} message to be inspected.	
	 * @param boundary	Boundary string separating different options for the parsing process. 
	 * @return			Parsed message data in {@link NiPublishForm}.
     */
    public NiPublishForm parsePublishMessage(InputStream data, String boundary) {  
        txtBody = new StringBuffer();  
        InputStream ndo=null;
        int ndoLen=-1;
        int ndoOffset=-1;
        int ndoArrayPos=-1;
        String[] parts=null;
        String fName=null;
        Field msgID=null;
        NiPublishForm form=null;
        try {          	
        	Message mimeMsg = new Message(); 
        	MimeEntityConfig config = new MimeEntityConfig();
        	config.setMaxLineLen(-1);
        	MimeStreamParser parser = new MimeStreamParser(config);
        	ContentHandler handler = new MessageBuilder(mimeMsg, new MemoryStorageProvider());
        		
        	parser.setContentHandler(handler); 
        	try {        		
        		parser.parse(data);
			} catch (MimeException e1) {
				e1.printStackTrace();
			}
        	
        	msgID  = mimeMsg.getHeader().getField("Content-Disposition");
        	if (!textType(mimeMsg.getMimeType()) && binaryType(mimeMsg.getMimeType()) && ("octets".equals(getFieldValue(msgID.toString(), OptName)))) {
        		// Content is in BinaryBody
        		fName=getFieldValue(msgID.toString(), FileName);
	        	BinaryBody b = (BinaryBody) mimeMsg.getBody();
	            ndo = b.getInputStream(); 
	            ndo.mark(0);
	            logger.debug("ndo len: "+ndo.available());
	            String ndoS = toString(ndo);
	            //logger.debug("ndoS: "+ndoS);
	            ndo.reset();
	            parts = ndoS.split(boundary);
	            int len=0;
	            logger.debug("parts len: "+len);
	            ndoLen=parts[0].length();
	            ndoOffset=0;
	            ndoArrayPos=0;
        	} else {
        	  // Content is in TextBody
              String text = getTxtPart(mimeMsg);
              txtBody.append(text);  
              logger.debug("Text body: " + txtBody.toString());
              parts = txtBody.toString().split(boundary);
              ndoArrayPos = checkBinaryPositionInArray(parts);
              if (-1<ndoArrayPos) {
            	  fName=getFieldValue(parts[ndoArrayPos], FileName);
            	  int fileOff=checkFilePositionInBuffer(parts[ndoArrayPos]);
            	  ndoOffset=fileOff;
            	  ndoLen=parts[ndoArrayPos].length()-fileOff;
            	  logger.debug("File length: "+(parts[ndoArrayPos].length()-fileOff));
            	  ndo = new ByteArrayInputStream(parts[ndoArrayPos].getBytes());
            	  ndoArrayPos=0;
              }
        	}
        	
        	form=parseMsgData(parts, msgID.toString(), ndoArrayPos);
        	if (!haveAllMandatoryFormFields(form, isFullPut(form))) {
        		logger.error("Form does not have all mandatory fields");
        		logger.debug(printAllFormFieldsStatus(form));
        		return null;
        	}
        		
        	
        } catch (IOException ex) {  
            ex.fillInStackTrace();
            return null;
        }
        
        if (null!=form.getFullPut() && form.getFullPut().equalsIgnoreCase("yes")) {
        	// Store this file
        	String inputValue = cacheHandler.getCacheFileName(fName);
        	form.setloc("file://"+inputValue);
        	try {
				cacheHandler.writeCacheFile(readPartialInputStream(ndo, ndoLen-4, ndoOffset), inputValue);
			} catch (IOException e) {
				e.printStackTrace();
			}
        }
        return form;
    }  

    /**
     * Checks whether the message has the FullPut option and whether it has value 'no' or 'yes'.
     * 
     * @param form 	Form to be inspected.
     * @return		<code>true</code> if the full put exists with "yes" value; 
	 * 				<code>false</code> otherwise.
     */
    private boolean isFullPut(NiPublishForm form) {
		if (null!= form.getFullPut() && form.getFullPut().equalsIgnoreCase("yes"))
			return true;
		return false;
	}

	/**
     * Checks whether input {@link String} follows the predefined Ni format.
     * 
	 * @param name	{@link String} to be inspected.	
	 * @return		<code>true</code> if the input is compatible with the Ni type; 
	 * 				<code>false</code> otherwise.
     */
    private static boolean isNi(String name) {
		if (name.contains("ni://"))
			return true;
		return false;
	}

	/**
	 * Checks whether input {@link String} follows the predefined NiHttp format.
	 * 
	 * @param name	{@link String} to be inspected.	
	 * @return		<code>true</code> if the input is compatible with the NiHttp type; 
	 * 				<code>false</code> otherwise.
	 */
	private static boolean isNiHttp(String name) {
		if (name.contains("nihttp://"))
			return true;
		return false;
	}

	/**
	 * Checks whether input {@link String} follows the predefined WKU format.
	 *  
	 * @param name	{@link String} to be inspected.	
	 * @return		<code>true</code> if the input is compatible with the WKU type; 
	 * 				<code>false</code> otherwise.
	 */
	private static boolean isWku(String name) {
		if (name.contains("http://") && name.contains("/.well-known/ni/"))
			return true;
		return false;
	}
    
    /**
     * Print all form fields into a {@link String}.
     * 
     * @param form	{@link NiPublishForm} to be inspected.	
     * @return		{@link String} where the content of all inspected form fields are included.
     */
    private Object printAllFormFieldsStatus(NiPublishForm form) {
		String msg = new String("Form: <START>");
		if (null==form.getloc())
			msg=msg+"loc=null,";
		else
			msg=msg+"loc=OK,";
		if (null==form.getMsgid())
			msg=msg+"msgid=null,";
		else
			msg=msg+"msgid=OK,";
		if (null==form.getUri())
			msg=msg+"uri=null,";
		else
			msg=msg+"uri=OK,";
		if (null==form.getExt())
			msg=msg+"ext=null,";
		else
			msg=msg+"ext=OK,";
		if (null==form.getFullPut())
			msg=msg+"fullPut=null,";
		else
			msg=msg+"fullPut=OK,";
		msg=msg+"<END>.";
		return msg;
	}

    /**
	 * Checks whether {@link NiPublishForm} has all mandatory fields.
	 * 
	 * @param form
	 *            {@link NiPublishForm} to be inspected.
	 * @param fileIncluded
	 *            the file included
	 * @return <code>true</code> if all mandatory fields exist;
	 *         <code>false</code> otherwise.
	 */
	private boolean haveAllMandatoryFormFields(NiPublishForm form, boolean fileIncluded) {
		if (!fileIncluded && null==form.getloc())
			return false;
		if (null==form.getMsgid())
			return false;
		if (null==form.getUri())
			return false;
		return true;
	}

	/**
	 * Parses message data and fill up a new {@link NiPublishForm} based on the parsed message.
	 * 
	 * @param parts					The message to be parsed is stored in this {@link String} array. 
	 * @param data					Name of the first option.
	 * @param ignoreArrayElement	Indicates which array elements are ignored.
	 * @return						Parsed message data in {@link NiPublishForm}.
	 */
	private NiPublishForm parseMsgData(String[] parts, String data, int ignoreArrayElement) {
		NiPublishForm form = new NiPublishForm();
		String Name=getFieldValue(data, OptName);;
		
		// First header needs a special handing since field header and data are in separare arrays
		if ("ext".equalsIgnoreCase(Name)) 
				form.setExt(getStringData(parts[0]));
		if ("msgid".equalsIgnoreCase(Name)) 
				form.setMsgid(getStringData(parts[0]));
		if ("fullPut".equalsIgnoreCase(Name)) 
				form.setFullPut(getStringData(parts[0]));
		if ("URI".equalsIgnoreCase(Name)) 
				form.setUri(getUri(parts[0]));
		if ((null!=Name) && Name.matches("loc(.*)")) 
				form.setloc(getLoc(parts[0]));
		
		// Continue and process 2-n:th headers
		for (int i=0; i<parts.length; i++) {
			if (i==ignoreArrayElement)
				continue;
			Name=getFieldValue(parts[i], OptName);
			if (null==Name)
				continue;
			if ("URI".equalsIgnoreCase(Name)) {
				form.setUri(getUri(parts[i]));
			}
			if (Name.matches("loc(.*)")) {
				form.setloc(getLoc(parts[i]));
			}
			if ("ext".equalsIgnoreCase(Name)) {
				form.setExt(getStringData(parts[i]));
			}
			if ("msgid".equalsIgnoreCase(Name)) {
				form.setMsgid(getStringData(parts[i]));
			}
			if ("fullPut".equalsIgnoreCase(Name)) {
				form.setFullPut(getStringData(parts[i]));
			}
		}
		return form;
	}

	/**
	 * Gets data from a text option.
	 * 
	 * @param data	{@link String} to be searched.
	 * @return		Data {@link String}.
	 */
	private String getStringData(String data) {
		String retValue=null;
		int startInd=checkDataPositionInBuffer(data);
		int endInd=checkDataLengthInBuffer(data,startInd);
		retValue=new String(data.substring(startInd, endInd));
		return retValue;
	}

	/**
	 * Locates the binary option position.
	 * 
	 * @param parts {@link String} array to be searched.
	 * @return		Array index of the binary option.
	 */
	private int checkBinaryPositionInArray(String[] parts) {
		for (int i=0; i<parts.length; i++) {
			if ("octets".equals(getFieldValue(parts[i], OptName)))  {
				return i;
			}				
		}
		return -1;
	}

	/**
	 * Locates the predefined boundary string after the "filename" string and calculates 
	 * the first position after it.
	 * 
	 * @param data	{@link String} to be searched.
	 * @return		Index of the 1st byte after the boundary string.
	 */
	private int checkFilePositionInBuffer(String data) {
		int filenameInd = data.indexOf("filename");
		int startInd = data.indexOf("\r\n\r\n", filenameInd);
		return startInd+"\r\n\r\n".length();
		
	}

	/**
	 * Locates the predefined boundary string and calculates the first position after it.
	 * 
	 * @param data 	{@link String} to be searched.
	 * @return		Index of the 1st byte after the boundary string.
	 */
	private int checkDataPositionInBuffer(String data) {
		int startInd = data.indexOf("\r\n\r\n");
		return startInd+"\r\n\r\n".length();		
	}
	
	/**
	 * Finds a next boundary string starting from the given offset.
	 * 
	 * @param data	{@link String} to be searched.
	 * @param off	Starting offset.
	 * @return		The offset boundary string if found; otherwise -1.
	 */
	private int checkDataLengthInBuffer(String data, int off) {
		return data.indexOf("\r\n",off);
	}
	
	/**
	 * Reads only a partial part of the {@link InputStream}.
	 * 
	 * @param data	Source {@link InputStream} to be read.
	 * @param len	How many bytes to be read.
	 * @param off	From which position reading starts. 
	 * @return		The requested part of the {@link InputStream}.		
	 */
	private InputStream readPartialInputStream(InputStream data, int len, int off) {
		byte[] b = new byte[len];
		try {
			data.skip(off);
			data.read(b, 0, len);
		} catch (IOException e) {
			e.printStackTrace();
		}
		return new ByteArrayInputStream(b);	
	}
	
	/**
	 * Converts {@link InputStream} to {@link String}.
	 * 
	 * @param is			Source {@link InputStream} to be converted. 
	 * @return				Converted {@link String}.
	 * @throws IOException	If an exception occurred during the {@link InputStream} handling.
	 */
    private static String toString(InputStream is) throws IOException {
        int size = is.available();
        char[] c = new char[size];
        byte[] b    = new byte[size];

        is.read(b, 0, size);
        for (int i = 0; i < size;)
            c[i] = (char)(b[i++]&0xff);
        
        return new String(c);
    }    
	
    /**
     * Gets the field value from the {@link String}.
     * 
     * @param data		{@link String} to be inspected.
     * @param constant	{@link String} defines field name that is searched for.
     * @return			Field value in {@link String} if found; otherwise <code>null</code>.
     */
    private String getFieldValue(String data, String constant) {
    	int i1=data.indexOf(constant);
    	if (-1==i1)
    		return null;
    	i1+=constant.length()+1;
    	int i2=data.indexOf("\"", i1);
    	return data.substring(i1, i2);
    }
    
    /**
     * Gets location from the {@link String}.
     * 
     * @param data					{@link String} to be inspected.
     * @return						Location in {@link String} if found; otherwise <code>null</code>.
     * @throws NullPointerException	If none of the predefined URI formats cannot be found from the input.
     */
	private String getLoc(String data) throws NullPointerException {
    	String tmp=null;
		if (isNiHttp(data)) {
			tmp = data.substring(data.indexOf("nihttp://"), data.indexOf("\r\n",data.indexOf("nihttp://")+1));
			if (null==tmp)
				throw new NullPointerException("Malformed nihttp");
			return tmp;
		}
		if (isNi(data)) {
			tmp = data.substring(data.indexOf("ni://"), data.indexOf("\r\n",data.indexOf("nihttp://")+1));
			if (null==tmp)
				throw new NullPointerException("Malformed ni");
			return tmp;
		}
		if (isWku(data)) {
			tmp = data.substring(data.indexOf("http://"), data.indexOf("\r\n",data.indexOf("nihttp://")+1));
			if (null==tmp)
				throw new NullPointerException("Malformed wku");
			return tmp;
		}		
		return null;
	}
	
	/**
	 * Gets URI from the {@link String}.
	 * 
	 * @param data					{@link String} to be inspected.				
	 * @return						URI in {@link String} if found; otherwise <code>null</code>.
	 * @throws NullPointerException	If none of the predefined URI formats cannot be found from the input.
	 */
	private String getUri(String data) throws NullPointerException {
    	String tmp=null;
		if (isNiHttp(data)) {
			tmp = data.substring(data.indexOf("nihttp://"), data.indexOf("\r\n", data.indexOf("ni://")));
			if (null==tmp)
				throw new NullPointerException("Malformed nihttp");
			return tmp;
		}
		if (isNi(data)) {
			if (data.contains("?")) {
				tmp = data.substring(data.indexOf("ni://"), data.indexOf("?"));
			} else {
				tmp = data.substring(data.indexOf("ni://"), data.indexOf("\r\n", data.indexOf("ni://")));
			}
			if (null==tmp)
				throw new NullPointerException("Malformed ni");
			return tmp;
		}
		if (isWku(data)) {
			tmp = data.substring(0, data.indexOf("\r\n"));
			if (null==tmp)
				throw new NullPointerException("Malformed wku");
			return tmp;
		}		
		return null;
	}
	
	/**
	 * Inspects whether the MIME has textual representation or not.
	 * 
	 * @param mimeType	MIME type to be inspected.
	 * @return			<code>true</code> if the type represents text; 
	 * 					<code>false</code> otherwise.
	 */
	private boolean textType(String mimeType) {
		if (mimeType.contains("text/plain"))
			return true;
		return false;
	}
	
	/**
	 * Inspects whether the MIME has binary representation or not.
	 * 
	 * @param mimeType	MIME type to be inspected. 
	 * @return			<code>true</code> if the type represents binary; 
	 * 					<code>false</code> otherwise.
	 */
	private boolean binaryType(String mimeType) {
		if (mimeType.contains("application/octet-stream"))
			return true;
		return false;
	}
	
	/**
	 * Gets text part of the {@link Entity} and converts it into {@link String}.
	 * 
	 * @param part
	 *            {@link Entity} to be converted.
	 * @return Converted entity in {@link String} format.
	 * @throws IOException
	 *             Signals that an I/O exception has occurred.
	 */
    private String getTxtPart(Entity part) throws IOException {  
        //Get content from body  
        TextBody tb = (TextBody) part.getBody();  
        ByteArrayOutputStream baos = new ByteArrayOutputStream();  
        tb.writeTo(baos);  
        return new String(baos.toByteArray());  
    }  
}