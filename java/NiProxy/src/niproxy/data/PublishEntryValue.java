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

import java.io.Serializable;
import java.util.HashSet;
import java.util.Set;

// TODO: Auto-generated Javadoc
/**
 * Implements the 'value' part of the publication <key,value> database.
 *
 */
public class PublishEntryValue implements Serializable {
	
	/** The Constant serialVersionUID. */
	private static final long serialVersionUID = 2894907974137929251L;
	
	/** The loc list. */
	Set<String> locList;

	/**
	 * Instantiates a new publish entry value.
	 * 
	 * @param data
	 *            the data
	 */
	public PublishEntryValue(String data) {
		addLocRef(data);
	}

	/**
	 * Adds the loc ref.
	 * 
	 * @param loc
	 *            the loc
	 */
	public void addLocRef(String loc) {
		if (null == this.locList) {
			this.locList = new HashSet<String>();
			this.locList.add(loc);
		} else {
			this.locList.add(loc);
		}
	}

	/**
	 * Del loc ref.
	 * 
	 * @param loc
	 *            the loc
	 */
	public void delLocRef(String loc) {
		this.locList.remove(loc);
	}

	/**
	 * Gets the size.
	 * 
	 * @return the size
	 */
	public int getSize() {
		return locList.size();
	}

	/**
	 * Gets the loc list.
	 * 
	 * @return the loc list
	 */
	public Set<String> getLocList() {
		return locList;
	}
}
