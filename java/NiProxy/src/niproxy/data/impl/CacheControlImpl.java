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

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import org.apache.commons.codec.digest.DigestUtils;
import org.apache.commons.io.FileUtils;
import org.apache.log4j.Logger;

import niproxy.NiProxyConfig;
import niproxy.NiProxyMonitor;
import niproxy.data.CacheControl;
import niproxy.data.InMemoryDB;

/**
 * Cache implementation that provides basic set of file operations via which files can be added and 
 * deleted.
 * 
 */
public class CacheControlImpl implements CacheControl {
	
	/** The logger. */
	private final Logger logger = Logger.getLogger(CacheControlImpl.class);
	
	/** The cache path. */
	private static String cachePath = NiProxyConfig.getCacheRootDir();
	
	/**
	 * Instantiates a new cache control impl.
	 */
	public CacheControlImpl () {
		File file;
		file = new File(cachePath);
		if (!file.exists()) {
			file.mkdir();
		} else {
			try {
				FileUtils.deleteDirectory(file);
			} catch (IOException e) {
				e.printStackTrace();
			}
			file.mkdir();
		}
	}
	
	// Not used right now, but when unpublish() will become supported, then we will need this method.
    /**
	 * Delete cache copy.
	 * 
	 * @param filename
	 *            the filename
	 */
	@SuppressWarnings("unused")
	private void deleteCacheCopy(String filename) {
    	File file;
    	file=new File(filename);
    	if(!file.exists()){
    		logger.error("Cannot delete the cache file, file does not exist");
    		return;
   		} else {
   			file.delete();
   		} 			
    }	
	
    /* (non-Javadoc)
     * @see niproxy.data.CacheControl#writeCacheFile(java.io.InputStream, java.lang.String)
     */
    @Override
	public void writeCacheFile(InputStream data, String filename) throws IOException {
    	File file;
    	file=new File(filename);
    	if(file.exists()){
    		logger.error("Cannot add a new cache file, file exists: "+filename);
    		return;
   		}
    	if (null==data) {
    		logger.error("No data to write to file");
    		return;    		
    	}
    	try {
			file.createNewFile();
		} catch (IOException e1) {
			// TODO Auto-generated catch block
			e1.printStackTrace();
		}
    	
    	OutputStream out=new FileOutputStream(file);
    	byte buf[]=new byte[1024];
    	int len;
    	while((len=data.read(buf))>0) {
    	  out.write(buf,0,len);
    	}
    	data.close();
    	out.close();
    }
		
	/**
	 * Creates the filename from url.
	 * 
	 * @param url
	 *            the url
	 * @return the string
	 */
	private String createFilenameFromUrl(String url) {
	      return cachePath+DigestUtils.md5Hex(url.toString());
	  }
	
	/* (non-Javadoc)
	 * @see niproxy.data.CacheControl#getCacheFileName(java.lang.String)
	 */
	@Override
	public String getCacheFileName(String fName) {
		return createFilenameFromUrl(fName);
	}

}
