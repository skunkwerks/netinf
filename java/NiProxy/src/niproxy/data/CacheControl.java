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
package niproxy.data;

import java.io.IOException;
import java.io.InputStream;
/**
 * The Interface CacheControl.
 */
public interface CacheControl {
	/**
	 * Gets the full filename for a new file to be added to the file system cache.
	 * 
	 * @param fName	Filename excluding its path.
	 * @return		The full filename taking into account also the root directory of the cache.
	 */
	String getCacheFileName(String fName);
	
	/**
	 * Writes a new file to the file system cache.
	 * 
	 * @param data			File content to be written to the disk.
	 * @param filename		Full filename.
	 * @throws IOException	An error occurred during file operations.
	 */
	public void writeCacheFile(InputStream data, String filename) throws IOException;

}
