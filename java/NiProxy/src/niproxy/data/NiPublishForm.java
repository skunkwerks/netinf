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
 * 
 * Form that is used message parsing. For each parameter in the class, Set() and Get() methods are provided.
 *
 */
public class NiPublishForm {
	
	/** The uri. */
	String uri;
	
	/** The msgid. */
	String msgid;
	
	/** The ext. */
	String ext;
	
	/** The loc. */
	PublishEntryValue loc;
	
	/** The full put. */
	String fullPut;
	
	/**
	 * Sets the uri.
	 * 
	 * @param data
	 *            the new uri
	 */
	public void setUri(String data) {
		if (null==data)
			return;

		if (null==this.uri)
			this.uri = new String(data);
		else
			this.uri=data;
	}

	/**
	 * Gets the uri.
	 * 
	 * @return the uri
	 */
	public String getUri() {
		return this.uri;
	}
	
	/**
	 * Sets the msgid.
	 * 
	 * @param data
	 *            the new msgid
	 */
	public void setMsgid(String data) {
		if (null==data)
			return;

		if (null==this.msgid)
			this.msgid = new String(data);
		else
			this.msgid=data;
	}

	/**
	 * Gets the msgid.
	 * 
	 * @return the msgid
	 */
	public String getMsgid() {
		return this.msgid;
	}

	/**
	 * Sets the ext.
	 * 
	 * @param data
	 *            the new ext
	 */
	public void setExt(String data) {
		if (null==data)
			return;

		if (null==this.ext)
			this.ext = new String(data);
		else
			this.ext=data;
	}

	/**
	 * Gets the ext.
	 * 
	 * @return the ext
	 */
	public String getExt() {
		return this.ext;
	}

	/**
	 * Sets the loc.
	 * 
	 * @param data
	 *            the new loc
	 */
	public void setloc(String data) {
		if (null==data)
			return;

		if (null==this.loc)
			this.loc = new PublishEntryValue(data);
		else
			this.loc.addLocRef(data);
	}

	/**
	 * Gets the loc.
	 * 
	 * @return the loc
	 */
	public PublishEntryValue getloc() {
		return this.loc;
	}
	
	/**
	 * Sets the full put.
	 * 
	 * @param data
	 *            the new full put
	 */
	public void setFullPut(String data) {
		if (null==data)
			return;

		if (null==this.fullPut)
			this.fullPut = new String(data);
		else
			this.fullPut=data;
	}

	/**
	 * Gets the full put.
	 * 
	 * @return the full put
	 */
	public String getFullPut() {
		return this.fullPut;
	}

}
