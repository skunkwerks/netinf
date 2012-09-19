/*
 *  Copyright 2012 Janne Tuononen & Petteri Pöyhönen, Nokia Siemens Networks
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
package niproxy.main;

import niproxy.NiProxy;
import niproxy.NiProxyConfig;

// TODO: Auto-generated Javadoc
/**
 * The Class NiProxyLauncher.
 */
public class NiProxyLauncher {

	/**
	 * A launcher for a simple http monitoring utility.
	 * 
	 * @param args	Optional parameters for the configuration file path and name. 
	 */
	public static void main(String[] args) {
		try {
			NiProxyConfig.initialize(args.length > 0 ? args[0] : "configuration/niproxy.config");
		} catch (Exception e) {
			throw new ExceptionInInitializerError(
					"Could not launch NiProxy due to erroneus configuration file. Exception thrown:" + e);
		}
		new NiProxy();

	}
}
