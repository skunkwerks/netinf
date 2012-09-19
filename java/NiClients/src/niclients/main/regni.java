/*
 * This (runnable) Java class that implements REGISTER NI (client)method of 
 * NI protocol, has been developed as part of the SAIL project. 
 * (http://sail-project.eu)
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
 */

package niclients.main;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.UnsupportedEncodingException;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

import org.apache.http.HttpResponse;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.mime.MultipartEntity;
import org.apache.http.entity.mime.content.StringBody;
import org.apache.http.impl.client.DefaultHttpClient;

public class regni { 

	private static String arg;
	static MultipartEntity reqEntity = new MultipartEntity();
	static String niname = null;
	static String fqdn = null;
	private static List<String> loc = new ArrayList<String>();
	static HttpPost post;
	static Random randomGenerator = new Random();
	
	static void usage() {
		System.out.println("Usage: regni -n <name> -u <loclist> -l <FQDN> -- publish NI file over HTTP\n");
		System.out.println("regni -h -- print usage info\n");
	}
	
	static boolean createpub() throws UnsupportedEncodingException {
		
		post = new HttpPost(fqdn+"/.well-known/netinfproto/publish"); // -l
		int i = 0;
				
		StringBody url = new StringBody(niname); // -n
		reqEntity.addPart("URI",url);
		
		StringBody msgid = new StringBody(Integer.toString(randomGenerator.nextInt(100000000))); // generate
		reqEntity.addPart("msgid", msgid);
		
		for (i=0;i<loc.size(); i++) {
			try {
				StringBody l = new StringBody(loc.get(i));
				reqEntity.addPart("loc"+i, l);
				
			} catch (UnsupportedEncodingException e) {
				e.printStackTrace();
			}
		}

		post.setEntity(reqEntity);
		return true;
	}
	/**
	 * Register NI command parser.
	 * 
	 * @param args		command line parameters.
	 * 
	 * @return			true in successful parsing, false in case of error.
	 */
	static boolean commandparser(String[] args) {
		
		int i = 0;
		
		while (i < args.length && args[i].startsWith("-")) {
            arg = args[i++];
		
            if (arg.equals("-h")) {        
                usage();
                return false;
            }
            
            else if (arg.equals("-n")) {
                if (i < args.length)
                    niname = args[i++];
                else
                    System.err.println("-name requires a ni value");
            }
            
            else if (arg.equals("-l")) {
                if (i < args.length)
                    fqdn = args[i++];
                else
                    System.err.println("-l requires a value (FQDN)");
            }
            
            else if (arg.equals("-u")) {
            	
            	if (i < args.length)
            		while (i < args.length && !args[i].startsWith("-")) 
            			loc.add(args[i++]);
                else
                   System.err.println("-u requires a value (location list)");
                }
            }
				
		if (fqdn == null || niname == null || loc == null) {
			usage();
			return false;
		} else {
			return true;
		}
	}
	
	public static void main(String[] args) throws UnsupportedEncodingException {
		HttpClient client = new DefaultHttpClient();
		
		if (commandparser(args)) {
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
			System.err.println("Publish creation failed!");
			}
		
		} else {
			System.err.println("Command line parsing failed!");
		}
	}
}
