/**
 * This Java class implement NI Utility tools,
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

/**
 * The Class niUtils.
 */
public class niUtils {
	
	/** The hash. */
	static String hash = null;
	
	/** The new ni. */
	static String newNi;
	
	/**
	 * makenif makes a new NI name from the niname and filename
	 * by calculating a hash value over the file pointed by filename
	 * and inserting that value to the niname. 
	 * 
	 * @param niname	base NI name string
	 * @param filename	file name of the file to be added
	 * 
	 * @return			created NI name string or null in hash 
	 * 					calculation failure
	 */
	public static String makenif(String niname, String filename) {
		try {
			hash = SHA256Hash.CalculateCheckSumBase64(filename, niname);
		} catch (Exception e) {
			e.printStackTrace();
			return(null);
		}
		
		newNi=niURLUtils.insertHashToNi(hash,niname);
		
		System.out.println("new ni: "+newNi);
		
		System.out.println("Hash: "+niURLUtils.getHashFromNi(newNi));
		
		System.out.println("Ni without hash: "+niURLUtils.removeHashFromNi(newNi));
		
		return(newNi);
	}
	
	/**
	 * manNiHttpToWKU transform "nihttp://" format url to well-known url format.
	 *
	 * @param niname 	nihttp:// url to be transformed
	 * @return 		transformed string
	 */
	public static String mapNiHttpToWKU(String niname) {
		String newWKU = new String();
		
		if (!niURLUtils.isNiHttp(niname)) 
			return null;
		int start = 9;
		int end = niname.indexOf("/", 9);
		
		if (end == -1)
			end = niname.length();
		
		String fqdn=niname.substring(start, end); 			
		
		try {
			newWKU="http://"+fqdn+"/.well-known/netinfproto/get"; 
		} catch (Exception e) {
			e.printStackTrace();
			return null;
		}
		return newWKU;
	}
	
	/**
	 * mapNiToWKU transforms "ni://" format url to well-known url format.
	 *
	 * @param niname 	"ni://" format url to be transformed
	 * @return 		transformed string
	 */
	public static String mapNiToWKU(String niname) {
		String newWKU = new String();
		
		if (!niURLUtils.isNi(niname)) 
			return null;
		
		String fqdn=niname.substring(5+1, niname.indexOf("/", 5+1));
				
		String rest=niname.substring(niURLUtils.getHashNameEndIndex(niname),niname.length());
		
		try {
			newWKU="http://"+fqdn+"/.well-known/ni/"+SHA256Hash.getHashAlgType(niname)+"/"+rest;
		} catch (Exception e) {
			e.printStackTrace();
			return null;
		}
		return newWKU;
	}

}
