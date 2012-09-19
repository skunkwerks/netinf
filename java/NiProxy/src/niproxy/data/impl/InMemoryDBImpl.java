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
package niproxy.data.impl;

import java.util.HashMap;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

import org.apache.log4j.Logger;

import niproxy.NiProxyConfig;
import niproxy.data.InMemoryDB;
import niproxy.data.NotationUtils;
import niproxy.data.PublishEntryValue;

/**
 * InMemory database implementation for publications of NDOs or their locations.
 * 
 */
public class InMemoryDBImpl implements InMemoryDB {
	
	/** The logger. */
	private final Logger logger = Logger.getLogger(this.getClass());
	
	/** The Constant publicationEntries. */
	private static final HashMap<String, PublishEntryValue> publicationEntries = new HashMap<String, PublishEntryValue>(NiProxyConfig.getMaxSizeOfIMPublishDB());
	
	/** The rwlock publish. */
	private final ReentrantReadWriteLock rwlockPublish = new ReentrantReadWriteLock();
	
	/** The r publish. */
	private final Lock rPublish = rwlockPublish.readLock(); 
	
	/** The w publish. */
	private final Lock wPublish = rwlockPublish.writeLock();
	
	/* (non-Javadoc)
	 * @see niproxy.data.InMemoryDB#AddPublication(java.lang.String, java.lang.String, niproxy.data.PublishEntryValue)
	 */
	@Override
	public void AddPublication(String hType, String hValue, PublishEntryValue locList) {
		try {
			wPublish.lock();
			PublishEntryValue newPEV = locList;
			publicationEntries.put(NotationUtils.compactNotation(hType, hValue), newPEV);
			logger.debug("Successful PUT for "+NotationUtils.compactNotation(hType, hValue)+" key");
		} finally {
			wPublish.unlock();
		}						
	}
	
	/* (non-Javadoc)
	 * @see niproxy.data.InMemoryDB#AddPublication(java.lang.String, java.lang.String, java.lang.String[])
	 */
	@Override
	public void AddPublication(String hType, String hValue, String[] locList) {
		try {
			wPublish.lock();
			PublishEntryValue newPEV = new PublishEntryValue(locList[0]);
			for (int i=1; i<locList.length; i++) {
				newPEV.addLocRef(locList[i]);
			}
			publicationEntries.put(NotationUtils.compactNotation(hType, hValue), newPEV);
			logger.debug("Successful PUT for "+NotationUtils.compactNotation(hType, hValue)+" key");
		} finally {
			wPublish.unlock();
		}				
	}

	/* (non-Javadoc)
	 * @see niproxy.data.InMemoryDB#RemovePublication(java.lang.String, java.lang.String)
	 */
	@Override
	public void RemovePublication(String hType, String hValue) {
		try {			
			wPublish.lock();
			publicationEntries.remove(NotationUtils.compactNotation(hType, hValue));
			logger.debug("Successful REMOVE for "+NotationUtils.compactNotation(hType, hValue)+" key");
		} finally {
			wPublish.unlock();
		}		
	}

	/* (non-Javadoc)
	 * @see niproxy.data.InMemoryDB#GetLocList(java.lang.String, java.lang.String)
	 */
	@Override
	public PublishEntryValue GetLocList(String hType, String hValue) {
		try {
			rPublish.lock();
			return publicationEntries.get(NotationUtils.compactNotation(hType, hValue));
		} finally {
			rPublish.unlock();
		}
	}
}
