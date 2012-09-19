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

/**
 * The Interface InMemoryDB.
 */
public interface InMemoryDB {
	/**
	 * Adds new publication to the <key,value> publication database.
	 * 
	 * @param hType		Hash type.
	 * @param hValue	Hash value.
	 * @param locList	List of locations in {@link String} array.
	 */
	void AddPublication(String hType, String hValue, String[] locList);
	
	/**
	 * Adds new publication to the <key,value> publication database.
	 * 
	 * @param hType		Hash type.
	 * @param hValue	Hash value.
	 * @param locList	List of locations in {@link PublishEntryValue}.
	 */
	void AddPublication(String hType, String hValue, PublishEntryValue locList);
	
	/**
	 * Removes the publication from database.
	 * 
	 * @param hType		Hash type.
	 * @param hValue	Hash value.
	 */
	void RemovePublication(String hType, String hValue);
	
	/**
	 * Gets the {@link PublishEntryValue} for the given <hType,hValue> pair from the database.
	 * @param hType		Hash type.
	 * @param hValue	Hash value.
	 * @return 			{@link PublishEntryValue} if found; otherwise <code>null</code>.
	 */
	PublishEntryValue GetLocList(String hType, String hValue);
	
}
