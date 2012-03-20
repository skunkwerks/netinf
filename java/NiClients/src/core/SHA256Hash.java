/*
 * This Java class implements SHA-256 hash tools for NI use, has been developed
 * as part of the SAIL project. (http://sail-project.eu)
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

package core;

import java.io.FileInputStream;
import java.security.MessageDigest;

import org.apache.commons.codec.binary.Base64;

public class SHA256Hash {

	private static final String SHA256 = "sha-256";
	private static final String SHA256_16 = "sha-256-16";
	
	public static String getHashAlgType(String url) throws Exception {
		if (url.contains(SHA256_16)) {
			return SHA256_16;
		} 
		if (url.contains(SHA256)) {
			return SHA256;
		} 
		throw new Exception("Unknown hash alg type");
	}

	public static String CalculateCheckSumBase64(String FileName, String url) throws Exception
	    {
			MessageDigest md = MessageDigest.getInstance(SHA256);
			FileInputStream fileHandle = new FileInputStream(FileName);	        
	        
	        byte[] dataBytes = new byte[1024];
	        
	        int nread = 0; 
	        while ((nread = fileHandle.read(dataBytes)) != -1) {
	          md.update(dataBytes, 0, nread);
	        };
	        byte[] mdbytes = md.digest();
	 
	        byte[] bytes = null;
	        if (SHA256 == getHashAlgType(url)) {
	        // Do base64 encoding
	        	bytes = Base64.encodeBase64URLSafe(mdbytes);	        
	        } else {
	        	if (SHA256_16 == getHashAlgType(url))
	        		bytes = Base64.encodeBase64(new byte[]{mdbytes[0],mdbytes[1]}, false, true, 4);
	        }
	        
	        // Store byte array as string and return it
	    	String value = new String(bytes);
	    	System.out.println("Base64 encoded "+getHashAlgType(url)+" hash: " + value);
	    	
	    	return value;
	    }
	
	public static String CalculateCheckSum(String FileName, String url) throws Exception
    {
		MessageDigest md = MessageDigest.getInstance(getHashAlgType(url));
		FileInputStream fis = new FileInputStream(FileName);	        
        
        byte[] dataBytes = new byte[1024];
 
        int nread = 0; 
        while ((nread = fis.read(dataBytes)) != -1) {
          md.update(dataBytes, 0, nread);
        };
        byte[] mdbytes = md.digest();
     		 
        // Store byte array as string and return it
    	String value = new String(mdbytes);
    	System.out.println("Encoded "+getHashAlgType(url)+" hash: " + value);
    	
    	return value;
    }

}
