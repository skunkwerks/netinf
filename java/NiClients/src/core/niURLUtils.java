/*
 * This Java class that implements NI URL Utility tools,
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
 */

package core;

public class niURLUtils {
	/**
	 *  isNi checks whether given string contains substring "ni://"
	 *  
	 * @param name	the string	
	 * @return		true/false, if yes/no
	 */
	public static boolean isNi(String name) {
		if (name.contains("ni://"))
			return true;
		return false;
	}
	
	/**
	 * isNiHttp checks whether string contains substring "nihttp://"
	 * 
	 * @param name	the string
	 * @return		true/false, if yes/no
	 */
	public static boolean isNiHttp(String name) {
		if (name.contains("nihttp://"))
			return true;
		return false;
	}
	
	/**
	 * getHashNameStartIndex gets start index of substring "sha-"
	 * in url string.
	 * 
	 * @param name	the url string
	 * @return		start index as integer
	 */
	private static int getHashNameStartIndex(String url) {
		int hashOffset=url.indexOf("sha-");
		return hashOffset;
	}
	/**
	 * getHashNameLen gets hash name length from the url string
	 * 
	 * @param url	the url string
	 * @return		hash length as integer
	 */
	private static int getHashNameLen(String url) {		
		int hashLen = 0;
		try {
			hashLen = SHA256Hash.getHashAlgType(url).length();
		} catch (Exception e) {
			e.printStackTrace();
		}
		return hashLen;
	}
	
	/**
	 * getHashNameEndindez gets end index from the url string
	 * 
	 * @param url	the url string
	 * @return		end index as integer
	 */
	public static int getHashNameEndIndex(String url) {
		int startIndex=getHashNameStartIndex(url);
		int len=getHashNameLen(url);
		return startIndex+len;
	}
	
	/**
	 * getHashNameEndindez gets insert index from the url string
	 * 
	 * @param url	the url string
	 * @return		the insert index as integer
	 */
	private static int getHashInsertIndex(String url) {
		int splitOff=0;
		
		int off=getHashNameStartIndex(url);
		splitOff=off+getHashNameLen(url);	
		return splitOff;
	}
	
	/**
	 * inseetHashToWKU inserts hash string to well-known url string
	 * 
	 * @param hash	the hash string
	 * @param url	the url string
	 * 
	 * @return		the result string
	 */
	public static String insertHashToWKU(String hash, String url) {
		String newUrl = new String();
		
		// Get the split point to where hash in inserted
		int insertIndex=getHashInsertIndex(url);
		// Lets construct a new url
		newUrl=url.substring(0, insertIndex)+"/"+hash+url.substring(insertIndex, url.length());
		return newUrl;
	}
	
	/**
	 * inseetHashToNi inserts hash string to NI url string
	 * 
	 * @param hash	the hash string
	 * @param url	the url string
	 * 
	 * @return		the result string
	 */
	public static String insertHashToNi(String hash, String url) {
		String newUrl = new String();
		
		// Get the split point to where hash in inserted
		int insertIndex=getHashInsertIndex(url);
		// Lets construct a new url
		newUrl=url.substring(0, insertIndex)+";"+hash+url.substring(insertIndex, url.length());
		return newUrl;
	}
	/**
	 * hetHashFromWKU gets hash string from the well-known url
	 * 
	 * @param url 	the well-known url string
	 * @return		the hash string
	 */
	public static String getHashFromWKU(String url) {
		int startIndex=getHashNameEndIndex(url);
		int endIndex=url.indexOf("/", startIndex+1);
		String hash=url.substring(startIndex+1, endIndex);
		return hash;
	}

	/**
	 * hetHashFromNi gets hash string from the NI url string
	 * 
	 * @param url 	the well-known url string
	 * @return		the hash string
	 */
	public static String getHashFromNi(String url) {
		int startIndex=getHashNameEndIndex(url);
		int endIndex=0;
		if (url.contains("?")) 
			endIndex=url.indexOf("?", startIndex+1);
		else 
			endIndex=url.length();
		
		String hash=url.substring(startIndex+1, endIndex);
		return hash;
	}

	/**
	 * removeHashFromWKU removes hash from the well-known url string
	 * 
	 * @param url the url string
	 * @return	the remaining WKU
	 */
	public static String removeHashFromWKU(String url) {
		int startIndex=getHashNameEndIndex(url);
		int endIndex=url.indexOf("/", startIndex+1);
		String newUrl=url.substring(0, startIndex)+url.substring(endIndex, url.length());
		return newUrl;
	}
	
	/**
	 * removeHashFromNi removes hash from the NI url string
	 * 
	 * @param url the url string
	 * @return	the remaining NI url string
	 */
	public static String removeHashFromNi(String url) {
		int startIndex=getHashNameEndIndex(url);
		int endIndex=url.indexOf(";", startIndex+1);
		
		if (endIndex == -1)
				endIndex = url.length();
		
		String newUrl=url.substring(0, startIndex)+url.substring(endIndex, url.length());		
		return newUrl;
	}
}
