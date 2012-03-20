/*
 *  This (runnable) Java class that implements GET NI (client) method of NI protocol,
 * 	has been developed as part of the SAIL project. (http://sail-project.eu)
 * 	
 *  Specification(s) - note, versions may change::
 * 	-	http://tools.ietf.org/html/farrell-decade-ni-00
 * 	-	http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00
 * 
 * 	Authors: 	Janne Tuonnonen <janne.tuononen@nsn.com>
 * 				Petteri Pöyhönen <petteri.poyhonen@nsn.com>
 * 
 *  Copyright: 	Copyright 2012 Janne Tuonnonen <janne.tuononen@nsn.com> and
 * 				Petteri Pöyhönen <petteri.poyhonen@nsn.com>, Nokia Siemens Networks
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
 *  
 */

package niclients.main;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.Reader;
import java.io.StringWriter;
import java.io.UnsupportedEncodingException;
import java.io.Writer;
import java.net.URLEncoder;
import java.util.Random;

import org.apache.http.HttpEntity;
import org.apache.http.HttpResponse;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.InputStreamEntity;
import org.apache.http.impl.client.DefaultHttpClient;

import core.niUtils;

import org.json.simple.JSONArray;
import org.json.simple.JSONValue;

public class getni {

	private static String arg;
	static String output_filename = null;
	static String niname = null;
	static String fqdn = null;
	static HttpPost post;
	static Random randomGenerator = new Random();
	
	static void usage() {	
		
		System.out.println("Usage: getni -n ni-url -l <FQDN> [-o outputfile+path] -- publish NI file over HTTP\n");
		System.out.println("       getni -h -- print usage info\n");
	}
	
	/**
	 * Command parser parses the niget parameter
	 * 
	 * @param args 		command line parameters
	 * @return boolean 	true/false in success/failure
	 */
	static boolean commandparser(String[] args) {
		
		int i = 0;
		
		while (i < args.length && args[i].startsWith("-")) {
            arg = args[i++];
		
            if (arg.equals("-h")) {        
                usage();
                return false;
            }
            
            else if (arg.equals("-o")) {
                if (i < args.length)
                    output_filename = args[i++];
                else
                    System.err.println("-f requires a filename value");
            }
            
            else if (arg.equals("-n")) {
                if (i < args.length)
                    niname = args[i++];
                else
                    System.err.println("-n requires an ni value");
            }
                      
            else if (arg.equals("-l")) {
                if (i < args.length)
                    fqdn = args[i++];
                else
                    System.err.println("-l requires a value (FQDN)");
            }     
		}
				
		if (fqdn == null || niname == null)  {
			usage();
			return false;
		} else {
			if (output_filename == null) 
				System.out.println("Command parser: -o missing. Content will be printed to STDOUT.");
			return true;
		}
	}
		
	/**
	 *  Writes a copy of the content received in inputStream to a file.
	 *  
	 * @param data the inoutStream
	 * @param filename the file where content is stored in success
	 * 
	 * @return void (currently)
	 * 
	 * @throws IOException
	 */
	public static void writeCacheCopy(InputStream data, String filename) throws IOException {
    	File file;
    	file=new File(filename);
    	    	
    	if(file.exists()){
    		System.err.println("Cannot add a new file, file exists: "+filename);
    		return;
   		}
    	if (null==data) {
    		System.err.println("No data to write to file");
    		return;    		
    	}
    	try {
			file.createNewFile();
		} catch (IOException e1) {
			e1.printStackTrace();
		}
    	
    	OutputStream out=new FileOutputStream(file);
    	byte buf[]=new byte[1024];
    	int len;
    	while((len=data.read(buf))>0) {
    	  out.write(buf,0,len);
    	}
    	data.close();
    	out.close();
    }
	
	/**
	 * Writes a copy of the content to STDOUT received in inputStream.
	 * 
	 * @param data the inputStream
	 * 
	 * @throws IOException
	 */
	public static void writeCacheCopyToStdOut(InputStream data) throws IOException {
		
		OutputStream out = System.out;
		
		int nextChar;
		System.out.println("Content =>");
		while ( ( nextChar = data.read() ) != -1  )
			out.write((char) nextChar);
		 out.write( '\n' );
		 out.flush();
		 System.out.println("<= Content");
		 	
    }    
	/**
	 * Converts a string to a type ByteArrayInputStream
	 * 
	 * @param str string to be converted
	 * 
	 * @return ByteArrayInputStream
	 */
	public static InputStream fromString(String str)
	{
	byte[] bytes = str.getBytes();
	return new ByteArrayInputStream(bytes);
	}
	
	/**
	 * Creates NI get HTTP POST signal.
	 * 
	 * @param dst destination (fqdn for now) of the signal destination
	 * @param name name of the content in NI format
	 * 
	 * @return boolean true (currently always).
	 * 
	 * @throws UnsupportedEncodingException
	 */
	static boolean createget(String dst, String name) throws UnsupportedEncodingException {
		
		post = new HttpPost(dst+"/.well-known/netinfproto/get"); 
		
		String msgid = Integer.toString(randomGenerator.nextInt(100000000));
		String ext = "no extension";

		String uri= "URI="+name+"&msgid="+msgid+"&ext="+ext;
		
		String myEncodedUrl= URLEncoder.encode(uri, "UTF-8");

		HttpEntity newEntity = new InputStreamEntity(fromString(myEncodedUrl), myEncodedUrl.getBytes().length);
		
		post.addHeader("Content-Type","application/x-www-form-urlencoded");
		post.setEntity(newEntity);
		return true;
	}
	
	/**
	* To convert the InputStream to String we use the
	* Reader.read(char[] buffer) method. We iterate until the
	* Reader return -1 which means there's no more data to
	* read. We use the StringWriter class to produce the string.
	* 
	* @param is inputStream from where content to be converted is read
	*
	* @exception throws IOException
	*
	* @return converted stream string (null if stream is empty)
	*/
	public static String convertStreamToString(InputStream is) throws IOException {
	
		if (is != null) {
			Writer writer = new StringWriter();
	
			char[] buffer = new char[1024];
			try {
				Reader reader = new BufferedReader(
					new InputStreamReader(is, "UTF-8"));
				int n;
				while ((n = reader.read(buffer)) != -1) {
					writer.write(buffer, 0, n);
				}
			} finally {
				is.close();
			}
			return writer.toString();
		} else {       
			return "";
		}
	}

	
	/**
	 * Main of the GET NI.
	 */ 
	@SuppressWarnings("unchecked")
	public static void main(String[] args) throws UnsupportedEncodingException {
		HttpClient client = new DefaultHttpClient();
		boolean done;
		String dst=null;
		JSONArray loc_array = new JSONArray();
		String c_type;
		HttpResponse response;
		int resp_code=0;
		
		if (commandparser(args)) {
		
			dst = fqdn;
			done = false;
			
			try {
				while (!done) {
					if (createget(dst, niname)) {
									
						response = client.execute(post);
						resp_code = response.getStatusLine().getStatusCode();		
													
						if (200 == resp_code) {
							// Get content type
							c_type = response.getEntity().getContentType().getValue();
							
							if ("application/json".equalsIgnoreCase(c_type)) {
								// Response is location list
								InputStream content = response.getEntity().getContent();														
								String resp = convertStreamToString(content);
							
								// String to JSONArray
								Object obj=JSONValue.parse(resp);
								JSONArray array=(JSONArray)obj;
								
								// add new locations to loc_array	
								for (int i=0; i<array.size(); i++) {
									loc_array.add(array.get(i));
								}
								// Get next location from the loc_array and remove it from the loc_array
								if (!loc_array.isEmpty()) {
									
									// Check if new dst is type ni://
									String tmp_dst = loc_array.get(0).toString();
									tmp_dst = niUtils.mapNiToWKU(loc_array.get(0).toString());
									
									if (tmp_dst == null) {
										//Check id new dst is type nihttp://
										tmp_dst = niUtils.mapNiHttpToWKU(loc_array.get(0).toString());
										if (tmp_dst != null) 
											// is nihttp://
											dst = tmp_dst;
										else
											// is http://
											dst = loc_array.get(0).toString();
									} else {
										// is ni://
										dst = tmp_dst;
									}
									loc_array.remove(0);
								}
							} else if ("application/octet-stream".equalsIgnoreCase(c_type)) {
								// Response is content
								InputStream content = response.getEntity().getContent();
								if (output_filename == null)
									writeCacheCopyToStdOut(content);
								else {
										writeCacheCopy(content, output_filename);
										System.err.println("Content was stored to '"+output_filename+"'");
								}
								// so we can end the while
								done = true;
							} else {
								// Response content type is not something we expected
								System.err.println("Unsupported Content type = "+ c_type);
							}
						} else {
							// Response codetype is not success (we expected that)
							System.err.println("RESP_CODE: "+Integer.toString(resp_code));
						}	
				} else {
					System.err.println("Command parse failed!");
				}
			}
			} catch (IOException e) {
				e.printStackTrace();
			}
		}
	}
}
	
