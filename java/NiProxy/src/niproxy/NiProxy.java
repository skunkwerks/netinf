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

import java.net.InetSocketAddress;
import org.apache.http.HttpResponseInterceptor;
import org.apache.http.impl.DefaultConnectionReuseStrategy;
import org.apache.http.impl.DefaultHttpResponseFactory;
import org.apache.http.impl.nio.DefaultServerIOEventDispatch;
import org.apache.http.impl.nio.reactor.DefaultListeningIOReactor;
import org.apache.http.nio.protocol.AsyncNHttpServiceHandler;
import org.apache.http.nio.protocol.NHttpRequestHandlerRegistry;
import org.apache.http.nio.reactor.IOEventDispatch;
import org.apache.http.nio.reactor.ListeningIOReactor;
import org.apache.http.params.CoreConnectionPNames;
import org.apache.http.params.HttpParams;
import org.apache.http.params.SyncBasicHttpParams;
import org.apache.http.protocol.HttpProcessor;
import org.apache.http.protocol.ImmutableHttpProcessor;
import org.apache.http.protocol.ResponseConnControl;
import org.apache.http.protocol.ResponseContent;
import org.apache.http.protocol.ResponseDate;
import org.apache.http.protocol.ResponseServer;
import org.apache.log4j.Logger;

/**
 * Implementation of the NiProxy.
 */
public class NiProxy {
	
	/** The logger. */
	private static Logger logger = Logger.getLogger(NiProxy.class);

	/**
	 * Setups a monitoring http proxy and starts a non blocking listening
	 * service based on a {@link NiProxyConfig}. This is based on the Apache 
	 * Software Foundation's example code "Basic non-blocking HTTP server" that 
	 * can be found from http://hc.apache.org/httpcomponents-core-ga/examples.html. 
	 */
	public NiProxy() {
		HttpParams params = new SyncBasicHttpParams();
		params.setIntParameter(CoreConnectionPNames.SO_TIMEOUT, NiProxyConfig.getHttpConnectionTimeout())
				.setIntParameter(CoreConnectionPNames.SOCKET_BUFFER_SIZE, 8 * 1024)
				.setBooleanParameter(CoreConnectionPNames.STALE_CONNECTION_CHECK, false)
				.setBooleanParameter(CoreConnectionPNames.TCP_NODELAY, true);

		HttpProcessor httpproc = new ImmutableHttpProcessor(new HttpResponseInterceptor[] { new ResponseDate(),
				new ResponseServer(), new ResponseContent(), new ResponseConnControl() });

		AsyncNHttpServiceHandler handler = new AsyncNHttpServiceHandler(httpproc, new DefaultHttpResponseFactory(),
				new DefaultConnectionReuseStrategy(), params);

		// Set up request handlers
		NHttpRequestHandlerRegistry registry = new NHttpRequestHandlerRegistry();
		registry.register("*", NiProxyMonitor.get());

		handler.setHandlerResolver(registry);

		// Provide an event logger
		handler.setEventListener(new EventLogger());

		IOEventDispatch ioEventDispatch = new DefaultServerIOEventDispatch(handler, params);
		try {
			logger.info("Setting up "+NiProxyConfig.getIOReactorWorkersCount()+" IOReactor workers");
			ListeningIOReactor ioReactor = new DefaultListeningIOReactor(NiProxyConfig.getIOReactorWorkersCount(), params);
			String host = NiProxyConfig.getNiProxyHost();
			int port = NiProxyConfig.getNiProxyPort();
			logger.info("Listening for connections at " + host + ":" + port);
			ioReactor.listen(new InetSocketAddress(host, port));
			logger.info("NiProxy set up done. Launching event dispatch...");
			ioReactor.execute(ioEventDispatch);
		} catch (Exception e) {
			logger.error("I/O reactor was interrupted. Exception: " + e);
			e.printStackTrace();
		}
		logger.info("NiProxy server shutdown.");
	}

}
