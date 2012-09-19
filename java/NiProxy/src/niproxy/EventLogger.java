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
package niproxy;

import java.io.IOException;

import org.apache.http.HttpException;
import org.apache.http.nio.NHttpConnection;
import org.apache.http.nio.protocol.EventListener;
import org.apache.log4j.Logger;

/**
 * Default implementation for logging monitor HTTP connection events.
 */
public class EventLogger implements EventListener {
	
	/** The logger. */
	private final Logger logger;

	/**
	 * Instantiates a new event logger.
	 */
	public EventLogger() {
		logger = Logger.getLogger(this.getClass());
	}

	/* (non-Javadoc)
	 * @see org.apache.http.nio.protocol.EventListener#connectionClosed(org.apache.http.nio.NHttpConnection)
	 */
	@Override
	public void connectionClosed(NHttpConnection arg0) {
		logger.info("Connection closed to " + arg0);
	}

	/* (non-Javadoc)
	 * @see org.apache.http.nio.protocol.EventListener#connectionOpen(org.apache.http.nio.NHttpConnection)
	 */
	@Override
	public void connectionOpen(NHttpConnection arg0) {
		logger.info("Connection opened to " + arg0);
	}

	/* (non-Javadoc)
	 * @see org.apache.http.nio.protocol.EventListener#connectionTimeout(org.apache.http.nio.NHttpConnection)
	 */
	@Override
	public void connectionTimeout(NHttpConnection arg0) {
		logger.info("Connection timed out to " + arg0);
	}

	/* (non-Javadoc)
	 * @see org.apache.http.nio.protocol.EventListener#fatalIOException(java.io.IOException, org.apache.http.nio.NHttpConnection)
	 */
	@Override
	public void fatalIOException(IOException arg0, NHttpConnection arg1) {
		logger.error("Connection I/O exception to " + arg1 + ". Reason: " + arg0.getMessage());
	}

	/* (non-Javadoc)
	 * @see org.apache.http.nio.protocol.EventListener#fatalProtocolException(org.apache.http.HttpException, org.apache.http.nio.NHttpConnection)
	 */
	@Override
	public void fatalProtocolException(HttpException arg0, NHttpConnection arg1) {
		logger.error("Connection protocol exception to " + arg1 + ". Reason: " + arg0.getMessage());
	}

}
