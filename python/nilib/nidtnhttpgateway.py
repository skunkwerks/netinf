#!/usr/bin/python
"""
@package nilib
@file nidtnhttpgateway.py
@brief Driver for NetInf Gateway between DTN and HTTP Convegence Layers
@version $Revision: 0.05 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
      This is an adjunct to the NI URI library developed as
      part of the SAIL project. (http://sail-project.eu)

      Specification(s) - note, versions may change
          - http://tools.ietf.org/html/draft-farrell-decade-ni-10
          - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03
          - http://tools.ietf.org/html/draft-kutscher-icnrg-netinf-proto-00

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
       -http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
===============================================================================#

@details
Controller for NetInf DTN-HTTP Convergence Layer gateway.

The overall handles
(1) incoming DTN bundles with NetInf request  messages and translates them into
requests that can be sent using the HTTP CL to one or more HTTP-based NetInf
cache manager servers that might be able to service the request, deal with the
returned responses and encapsulate them in DTN bundles for dispatch to the
original (DTN) source of the request.
(2) (eventually) incoming HTTP requests, translates them into DTN bundles for
dispatch to likely (DTN) places that might be able to service them and waits
for the responses if any, translates them back to HTTP encapsulation and
passses them back to the HTTP originator.

The gateway controller is a multi-threaded program and also potentially uses
multi-processing to handle individual HTTP requests that need to use a
continuous connection to the HTTP cache server.

The controller threads implement the following functionality:
- DTN Receiver: Class DtnReceive in file nidtnproc.py
  Registers with the dtnd daemon on the node to receive bundles destined for
  dtn://<local eid>/netinf_service/* where * matches with
  get|publish|search|response.
  Bundles are checked for a mandatory BPQ Block and an optional Metadata Block
  with the ontology indicating it carries a JSON string as ontology data.  These
  blocks are decoded and incorporated into a request message structure
  (HTTPRequest).  The type of request is determined and the request is added
  to the list of requests being fed to HTTP cache servers maintained in an
  instance of HTTPAction object and sets an Event to indicate that the HTTP
  Sender has work to do.
  
- HTTP Sender: Class HTTPAction in file nihttpaction.py
  Maintains a list of requests to be dispatched to NetInf cache servers using 
  the HTTP CL.  The HTTP locations to be used are determined by combining the
  list of locators in the metatdata sent with the request, any locator in the
  ni URI to be accessed and any next hops in the internal forwarding database.
  Requests can either be sent in turn to the specified locators or the Python
  multiprocessing module can be used to run several requests in parallel.  The
  results from the various requests are combined and queued for translation
  back into a DTN bundle and despatch back into the DTN network.
  
- HTTP Receiver Callback:  Also in Class HTTPAction in file nihttpaction.py
  When the HTTP Sender thread is using multiprocessing the HTTP responses are
  processed by an asynchronous callback that runs on the multiprocessing
  callback thread.  This has access to the request message list in the
  HTTPAction instance that dispatched the request subject a lock.  The callback
  signals the completion of the process via the Event so that the HTTP Sender
  can determine if there are more locations to send requests to.
  
- DTN Sender: Class DtnSender in file nidtnproc.py
  Processes requests that have been completed by HTTP (or not, if no actual
  responses were received and the request times out).  The response is
  translated back into a DTN bundle with BPQ Block and Metadata Block carrying
  the metadata returned (merged if several responses were processed).  The
  content for GET messages is carried as the payload.  If there is no content
  available the absence is signalled by including a payload placeholder
  Metadata block - this gets round a cirner case where the payload is present
  but of zero length - otherwise you would have to check whether the digest
  was that for a zero length file (???).
  
The driver sets up logging and listens for close down requests.


@code
Revision History
================
Version   Date       Author         Notes
1.0	  30/01/2013 Elwyn Davies   Created.
@endcode
"""
import os
import sys
import time
from Queue import Queue
import logging

from nihttpaction import HTTPAction
from nidtnproc import DtnSend, DtnReceive
#from nidtnevtmsg import MsgDtnEvt

#==============================================================================#
# GLOBAL VARIABLES


#==============================================================================#
class DtnHttpGateway():
    """
    @brief Controller for HTTP<->DTN gateway.

    Records parameters passed on startup.
    Starts up various threads as described above.
    Provides shutdown routine to close down the threads on request. 
    
    """
    #--------------------------------------------------------------------------#
    # CLASS CONSTANTS

    # === Defaults for single/multi-processing setup ===

    ##@var DEFAULT_MPROCS
    # integer number of processes to provide gateway forwarding operations
    #         If 1 (or 0) will run synchronously within the gateway HTTP thread
    DEFAULT_MPROCS = 1

    ##@var DEFAULT_PER_REQ_LIMIT
    # integer number of outstanding forwarded HTTP requests allowed per item
    DEFAULT_PER_REQ_LIMIT = 1
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var redis_conn
    # object StrictRedis instance used for communication between the NRS server
    # and the Redis database.

    ##@var logger
    # object logger instance to output messages

    ##@var ndo_cache
    # object instance of NDO cache handler

    ##@var http_server
    # object instance of NIHTTPServer that created this gateway
    
    #--------------------------------------------------------------------------#
    def __init__(self, config, logger, ndo_cache, redis_conn, http_server):
        """
        @brief Constructor for NetInf HTTP<->DTN gateway component of niserver.
        @param config object ConfigParser instance pointing to config file
        @param logger object logger instance to output messages
        @param ndo_cache object instance of NetInfCache with local (HTTP) NDOs
        @param nrs_redis object StrictRedis instance used for communication
                                between the gateway and the Redis database.
        @param http_server object instance of NIHTTPServer that instantiated
                                  this gateway.
        """

        self.config = config
        self.logger = logger
        self.ndo_cache = ndo_cache
        self.redis_conn = redis_conn
        self.http_server = http_server
        self.mprocs = None
        self.per_req_limit = None

        # Get mprocs and per_req_limit from config if specified
        conf_section = "gateway"
        if ((config is not None) and (config.has_section(conf_section))):
            if (self.mprocs is None):
                conf_option = "mprocs"
                if config.has_option(conf_section, conf_option):
                    try:
                        self.mprocs = config.getint(conf_section,
                                                    conf_option)
                    except ValueError:
                        self.logerror("Value supplied for %s is not an "
                                      "acceptable integer representation - "
                                      "using default %d" %
                                      (conf_option, self.DEFAULT_MPROCS))
                        self.mprocs = None
            if (self.per_req_limit is None):
                conf_option = "per-req-limit"
                if config.has_option(conf_section, conf_option):
                    try:
                        self.per_req_limit = config.getint(conf_section,
                                                           conf_option)
                    except ValueError:
                        self.logerror("Value supplied for %s is not an "
                                      "acceptable integer representation - "
                                      "using default %d" %
                                      (conf_option, self.DEFAULT_PER_REQ_LIMIT))
                        self.per_req_limit = None

        # Use defaults if not in configuration
        if self.mprocs is None:
            self.mprocs = self.DEFAULT_MPROCS
        if self.per_req_limit is None:
            self.per_req_limit = self.DEFAULT_PER_REQ_LIMIT

        # Create Queue for requests to be sent into DTN network
        self.response_q = Queue()

        # Create HTTP action thread
        self.http_action = HTTPAction(self.response_q,
                                      ndo_cache.get_temp_path(), logger,
                                      redis_conn, ndo_cache,
                                      mprocs=self.mprocs,
                                      per_req_limit=self.per_req_limit)
        self.http_action.setDaemon(True)

        # Create DTN send and receive threads
        self.dtn_send = DtnSend(self.response_q, logger)
        self.dtn_send.setDaemon(True)
        self.dtn_receive = DtnReceive(self.http_action, logger)
        self.dtn_receive.setDaemon(True)
        
        return
    
    #--------------------------------------------------------------------------#
    def start_gateway(self):
        """
        @brief start the threads running HTTP actions plus DTN send and receive
        """
        self.http_action.start()
        self.dtn_send.start()
        self.dtn_receive.start()
        return
    
    #--------------------------------------------------------------------------#
    def shutdown_gateway(self):
        """
        @brief terminate the threads running DTN receive and the HTTP
               action routine

        @detail Terminating the HTTP action thread will automatically terminate
        the DTN recive thread by sending it an 'end' message.
        """
        self.dtn_receive.end_run()
        self.http_action.end_run()
        return
    
#==============================================================================#
if __name__ == "__main__":
    from redis import StrictRedis
    from threading import Timer
    class TestCache():
        def __init(self):
            return
        def get_temp_path(self):
            return "/tmp"
        def cache_get(self, ni_name):
            raise NoCacheEntry("Test cache")
        # Normally returns 2-tuple (metadata, content file name)
            
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Clear existing next hop key in Redis
    redis_conn = StrictRedis()
    nh_key = "NIROUTER/GET_FWD/nh"
    redis_conn.delete(nh_key)
    
    # Put some entries in the next hop database
    nhl = {}
    nhl[0] = "tcd.netinf.eu"
    nhl[1] = "dtn://mightyatom.dtn"
    nhl[2] = "tcd-nrs.netinf.eu"
    redis_conn.hmset(nh_key, nhl)

    ndo_cache = TestCache()
    gw = DtnHttpGateway( None, logger, ndo_cache, redis_conn, None)
    gw.start_gateway()

    time.sleep(0.1)
    test_run_length = 30.0
    logger.info("Gateway running - will run for %f secs or until Ctrl/C" %
                test_run_length)

    test_run = True
    def end_test():
        global test_run
        test_run = False
        gw.shutdown_gateway()
        logger.info("finished gateway shutdown")
    t = Timer(test_run_length, end_test)
    t.start()
    
    while test_run:
        time.sleep(3)
        logger.debug("...%s running ..." % ("" if test_run else "no longer",))
                     
    logger.info("End of test")
    time.sleep(4)
    logger.info("Exiting")
 
  
