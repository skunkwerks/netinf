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

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;
import java.util.Properties;

import org.apache.log4j.PropertyConfigurator;
import org.apache.log4j.xml.DOMConfigurator;

/**
 * Provides methods to read needed configuration parameters from the config file.
 *
 */
public class NiProxyConfig {

	/** The con timeout. */
	private static Integer conTimeout;
	
	/** The properties. */
	private static Properties properties;
	
	/** The max sizeof im publish db. */
	private static Integer maxSizeofIMPublishDB;
	
	/** The cache root dir. */
	private static String cacheRootDir;
	
	/** The reactor workers. */
	private static Integer reactorWorkers;

	/**
	 * Gets the cache root dir.
	 * 
	 * @return the cache root dir
	 */
	public static String getCacheRootDir() {
		if (null == cacheRootDir) {
			cacheRootDir = properties.getProperty("cache_root_dir", "/tmp/nicache/");
		}
		return cacheRootDir;
	}
		
	/**
	 * Gets the http connection timeout.
	 * 
	 * @return the http connection timeout
	 */
	public static int getHttpConnectionTimeout() {
		if (conTimeout == null) {
			conTimeout = Integer.parseInt(properties.getProperty("http_connection_timeout", "0"));
		}
		return conTimeout;
	}

	/**
	 * Gets the iO reactor workers count.
	 * 
	 * @return the iO reactor workers count
	 */
	public static int getIOReactorWorkersCount() {
		if (reactorWorkers == null) {
			reactorWorkers = Integer.parseInt(properties.getProperty("ioreactor_workers", "2"));
		}
		return reactorWorkers;
	}

	/**
	 * Gets the ni proxy host.
	 * 
	 * @return the ni proxy host
	 */
	public static String getNiProxyHost() {
		return properties.getProperty("niproxy_host", "localhost");
	}

	/**
	 * Gets the ni proxy port.
	 * 
	 * @return the ni proxy port
	 */
	public static int getNiProxyPort() {
		return Integer.parseInt(properties.getProperty("niproxy_port", "8082"));
	}

	/**
	 * Gets the max size of im publish db.
	 * 
	 * @return the max size of im publish db
	 */
	public static int getMaxSizeOfIMPublishDB() {
		if (null == maxSizeofIMPublishDB) {
			maxSizeofIMPublishDB = Integer.parseInt(properties.getProperty("max_size_of_im_publish_db", "1000"));
		}
		return maxSizeofIMPublishDB;
	}
		
	/**
	 * Initialize.
	 * 
	 * @param configFile
	 *            the config file
	 * @throws FileNotFoundException
	 *             the file not found exception
	 * @throws IOException
	 *             Signals that an I/O exception has occurred.
	 */
	public static void initialize(String configFile) throws FileNotFoundException, IOException {
		properties = new Properties();
		properties.load(new FileReader(new File(configFile)));
		configureLogging(properties.getProperty("log4j_config_file", "configuration/log4j.xml"));
	}

	/**
	 * Configure logging.
	 * 
	 * @param configFile
	 *            the config file
	 */
	private static void configureLogging(String configFile) {
		if (configFile.endsWith(".xml")) {
			DOMConfigurator.configure(configFile);
		} else {
			PropertyConfigurator.configure(configFile);
		}
	}
}
