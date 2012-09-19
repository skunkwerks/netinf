/*
 *  
 *  This (runnable) Java class that implements PUBLISH NI (client) method of 
 *  NI protocol, has been developed as part of the SAIL project. 
 *  (http://sail-project.eu)
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
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.UnsupportedEncodingException;
import java.util.Random;

import org.apache.http.HttpResponse;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.mime.MultipartEntity;
import org.apache.http.entity.mime.content.ContentBody;
import org.apache.http.entity.mime.content.FileBody;
import org.apache.http.entity.mime.content.StringBody;
import org.apache.http.impl.client.DefaultHttpClient;

import core.niUtils;

public class pubni {

	private static String arg;
		
	static MultipartEntity reqEntity = new MultipartEntity();
	static String filename = null;
	static String authority = null;
	static String niname = null;	
	static String fqdn = null;	
	static HttpPost post;
	static Random randomGenerator = new Random();
	
	static void usage() {	
		System.out.println("Usage: pubni -f <filename> -a <authority> -l <FQDN> -- publish NI file over HTTP\n");
		System.out.println("       pubni -h -- print usage info\n");
	}
	/**
	 * Command line parser for Publish NI
	 * 
	 * @param args		command line parameters
	 * @return			true in successful parsing, false in failure.
	 */
	static boolean commandparser(String[] args) {
		
		int i = 0;
		
		while (i < args.length && args[i].startsWith("-")) {
            arg = args[i++];
		
            if (arg.equals("-h")) {        
                usage();
                return false;
            }
            
            else if (arg.equals("-f")) {
                if (i < args.length)
                    filename = args[i++];
                else
                    System.err.println("-f requires a filename value");
            }
            
            else if (arg.equals("-w")) {
                if (i < args.length)
                    niname = args[i++];
                else
                    System.err.println("-w requires an uri value");
            }
            
            else if (arg.equals("-a")) {
                if (i < args.length)
                    authority = args[i++];
                else
                    System.err.println("-a requires an authority value");
            }
            
            else if (arg.equals("-l")) {
                if (i < args.length)
                    fqdn = args[i++];
                else
                    System.err.println("-l requires a value (FQDN)");
            }     
		}
				
		if (fqdn == null || authority == null || filename == null)  {
			usage();
			return false;
		} else {
			return true;
		}
	}
	
	/**
	 * Creates NI publish HTTP POST signal.
	 * 
	 * @return 		boolean true/false in success/failure
	 * @throws 		UnsupportedEncodingException
	 */
	static boolean createpub() throws UnsupportedEncodingException {
		
		post = new HttpPost(fqdn+"/.well-known/netinfproto/publish"); 
				
		ContentBody url = new StringBody(niname); 
		ContentBody msgid = new StringBody(Integer.toString(randomGenerator.nextInt(100000000)));
		ContentBody fullPut = new StringBody("yes");
		ContentBody ext = new StringBody("no extension");
		ContentBody bin = new FileBody(new File(filename));
		MultipartEntity reqEntity = new MultipartEntity();
		reqEntity.addPart("octets", bin);
		reqEntity.addPart("URI",url);
		reqEntity.addPart("msgid", msgid);
		reqEntity.addPart("fullPut", fullPut);
		reqEntity.addPart("ext", ext);	
		
		post.setEntity(reqEntity);
		return true;
	}
	/**
	 * Add authority to the NI name
	 * 
	 * @param 		name the niname
	 * @param 		auth the authority
	 * 
	 * @return 		the modified niname
	 */
	private static String addauthorityToNiname(String name, String auth) {
			 
		 return "ni://"+authority+"/sha-256";	
	}	
	
	public static void main(String[] args) throws UnsupportedEncodingException {
		
		HttpClient client = new DefaultHttpClient();

		if (commandparser(args)) {
			
			niname = addauthorityToNiname(niname, authority);
			}
			
		niname = niUtils.makenif(niname,filename);
		if (niname != null) {
			if (createpub()) {
				try {
					
					HttpResponse response = client.execute(post);
					int resp_code = response.getStatusLine().getStatusCode();
					System.err.println("RESP_CODE: "+Integer.toString(resp_code));
					BufferedReader rd = new BufferedReader(new InputStreamReader(
						response.getEntity().getContent()));
					String line = "";
					while ((line = rd.readLine()) != null) {
						System.out.println(line);
					}

				} catch (IOException e) {
					e.printStackTrace();
				}
	
			} else {
				System.out.println("Niname creation failed!\n");
			}	
		} else {
			System.out.println("Command line parsing failed!\n");
		}	
	}
}
