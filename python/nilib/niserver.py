#!/usr/bin/python
"""
@package nilib
@file niserver.py
@brief Lightweight dedicated NI NetInf HTTP convergence layer (CL) server and NRS server.
@version $Revision: 1.01 $ $Author: elwynd $
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
   
       - http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

================================================================================

@details
niserver.py overview

Provides a server managing a cache of Named Data Objects (NDOs) named with
URIs from the ni scheme (ni://.. or nih:/...) allowing clients to access,
publish or search these NDOs using the NetInf protocol over the HTTP CL.

Implements
- NetInf proto GET, PUBLISH and SEARCH with HTTP convergence layer
  including handling metadata
- Direct GETs of Named Data Objects via HTTP URL translations of ni: names.
- Various support functions including listing the cache, delivering a form
  to generate the POST functions and returning a favicon.ico
- Optionally, provision of Name Resolution Server (NRS) support, controlled by
  configuration file option.

Creates a threaded HTTP server that responds to a limited set of URLs

- GET/HEAD on paths:
                 - /.well-known/ni[h]/<digest algorithm id>/<digest>,
                 - /ni_cache/<digest algorithm id>;<digest>,
                 - /ni_meta/<digest algorithm id>;<digest>,
                 - /getputform.html,
                 - /nrsconfig.html, (when running NRS server)
                 - /favicon.ico, and<
                 - /netinfproto/list
- POST on paths (basic system):
                 - /netinfproto/get,
                 - /netinfproto/publish,
                 - /netinfproto/put, and
                 - /netinf/search
- POST on paths (when running NRS server):
                 - /netinfproto/nrsconf,
                 - /netinfproto/nrslookup,
                 - /netinfproto/nrsdelete, and
                 - /netinfproto/nrsvals

A new thread is created for each incoming request.  Most of the work is done
by HTTP Server (effectively TCPServer) and BaseHTTPRequestHandler from the
standard Python module BaseHTTPServer.  The actual handler can be found in
nihandler.py.

The logging and thread management was inspired by the PyMail program from the
N4C project.

Should be used with Python 2.x where x is 6 or greater (the TCP socket
server up to version 2.5 is badly flawed (euphemism)).

The server uses a configuration file to specify various items (see
niserver_main.py) and set up logging.  The items that are significant
for the operation of the server are:

- server_port     the TCP port used by the HTTP server listener (default 8080)
- authority       the hostname part of the address of the HTTP server
- storage_root    the base directory where the content cache is stored
- logger          a logger to be used by the server (uses Python logging module)
- provide-nrs     flag indicating if NRS operations should be supported by
                  this server

TO DO: Add configuration to connect to non-default Redis server. 

The server manages a local cache of published information.  In the storage_root
directory there are two parallel sub-directories: an ni_ndo and and an ni_meta
sub-directory where the content and affiliated data of the content, respectively,
are stored. In this program, the file storing the affiliated data is called
the 'metadata file'. See the draft-kutscher-icnrg-netinfproto specification for the
relationship between the terms 'affiliated data' and 'metadata': broadly, the
affiliated data represents all the extra attributes that need to be maintained
in association with the NDO.

In each sub-directory there is a sub-directory for each digest algorithm.  Each of
these directories contains the file names are the digest of the content (i.e., the
digest in the ni: or nih: name).  These directories are set up by niserver_main.py
when the server is first started based on the list of available digest algorithms
supplied by the ni.py library.

Entries are inserted into the cache by the  NetInf 'publish' (or 'put') function
or can be generated externally and tied into the cache.

For a given entry (i.e., unique digest) it is generally assumed that there will
be at least a metadata file.  The corresponding content may or may not be present
depending on whether it was published (or whether the server decides to delete
the file because of policy constraints - such as space limits or DoS avoidance
by deleting files after a certain length of time - note that these are not currently
implemented but may be in future).

Metadata files contain a string emcoded JSON object.  When this is loaded into
memory, it is managed as a Python dictionary (to which it bears an uncanny
resemblance!).  This is encapsulated in an instance of the niserver::NetInfMetaData
class.

The vast majority of the code is contained in the NIHTTPRequestHandler class
which was originally designed as a subclass of the standard
BaseHTTPRequestHandler but can now also be used in conjunction with the Python
WSGI Web Server interface.

If specified in the configuration file (provide_nrs = yes), the server will also
provide NetInf Name Resolution Service support.  A database is set up using the
Redis name-value server (http://redis.io/) accessed via the Python binding 'redis-py'
(https://github.com/andymccurdy/redis-py/).  The NRS makes use of the hash mechanism
provided by Redis.  The database is keyed by either ni[h]: names or any other form of
locator.  Stored in the value are hash fields labelled 'loc1', 'loc2', 'hint1', 'hint2'
and 'meta' containing strings.  Currently, entries can be inserted via a form accessed
via the URL http://<server netloc>/nrsconfig.html.

TO DO: Connect NRS to NetInf operations.

Uses:
- the ni.py library of code that implements functionality handling the ni URI scheme.

@code
Revision History
================
Version   Date       Author         Notes
1.11      26/01/2013 Elwyn Davies   Add HTTP<->DTN gateway functionality..
1.10      26/01/2013 Elwyn Davies   Allow for Redis database selection.
1.9       13/12/2012 Elwyn Davies   Allow for Redis storage_root check.
1.8       11/12/2012 Elwyn Davies   Add check for Redis server actually running.
1.7       10/12/2012 Elwyn Davies   Select Redis or filesystem cache.
1.6       04/12/2012 Elwyn Davies   Use check_cache_dirs from cache module.
1.5       30/11/2012 Elwyn Davies   Update testing code
1.4       17/11/2012 Elwyn Davies   Prepare for alternative use of WSGI framework:
                                    Copy items accessed by self.server in NIHTTPRequestHandler
                                    into this class in 'handle' so that self.server is not
                                    used in actual processing of requests.
                                    Fix bug in nrsconfig check_form_data call.
1.3       01/11/2012 Elwyn Davies   Fixed bug in send_get_header - remove leading \n from final_mb
1.2       16/10/2012 Elwyn Davies   Fixed bug in netinf_publish - em_str -> ext_str
                                    Changed various logerror to loginfo/logwarn 'cos
                                    they are user errors rather than program problems.
1.1       13/10/2012 Elwyn Davies   Added size to metadata. Added limited check for
                                    consistent metadata (just written by same server).
1.0       13/10/2012 Elwyn Davies   Added QR code display screen.
0.9       11/10/2012 Elwyn Davies   Fixed few minor bugs resulting from code cleanup.
0.8       10/10/2012 Elwyn Davies   Fixed bug in conversion between ni_cache names and file names
                                    (need to substitute ';' by '/'). Added favicon config variable.
                                    Major updates to comments. Routines reordered.
                                    Code cleaned up and common parts factored out.
0.7       06/10/2012 Elwyn Davies   Added NRS form implementation code.  Added NRS delete
                                    and pattern matching for NRS listing.
0.6       06/10/2012 Elwyn Davies   Moved form HTML code to separate file accessed via config variable.
                                    Added NRS setup from code and initial access to Redis database.
0.5       05/10/2012 Elwyn Davies   Added metadata to listing and improved sorting and format
                                    Fixed expiry time for search listing.
                                    Corrected bug with search info that wasn't ascii.
0.4       04/10/2012 Elwyn Davies   Search completed.  Handling of nih using .well-known
                                    added.
0.3       03/10/2012 Elwyn Davies   Response format handling modified. Search added.
0.2       01/09/2012 Elwyn Davies   Metadata handling added.
0.1       11/07/2012 Elwyn Davies   Added 307 redirect for get from .well_known.
0.0       12/02/2012 Elwyn Davies   Created for SAIL codesprint.
@endcode
"""

#==============================================================================#
#=== Standard modules for Python 2.[567].x distributions ===
import os
import stat
import sys
import socket
import threading
import itertools
import logging
import shutil
import json
import re
import time
import datetime
import textwrap
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from BaseHTTPServer import HTTPServer
from SocketServer import ThreadingMixIn

import cgi
import urllib
import urllib2
import hashlib
import xml.etree.ElementTree as ET
import base64

#=== Modules needing special downloading
import magic
import DNS
import qrcode

try:
    import redis
    redis_loaded = True
except ImportError:
    redis_loaded = False

#=== Local package modules ===

import netinf_ver
import ni
from nihandler import NIHTTPRequestHandler
from nidtnhttpgateway import DtnHttpGateway

# Load either filesystem or Redis cache module depending on
# whether redis_store or file_store was imported.  Must have
# Redis module if using Redis cache.
if "redis_store" in sys.modules:
    if not redis_loaded:
        raise ImportError("Need Redis module if using Redis-based cache")
    from cache_redis import RedisNetInfCache as NetInfCache
    use_redis_cache = True
else:
    from cache_single import SingleNetInfCache as NetInfCache
    use_redis_cache = False

#==============================================================================#
# List of classes/global functions in file
__all__ = ['NetInfMetaData', 'NIHTTPServer', 'ni_http_server'] 
#==============================================================================#
# GLOBAL VARIABLES

##@var redis_loaded
# Flag indicating if it was possible to load the Redis module.
# The program can do without Redis if not providing NRS services
# and using filesystem cache.

##@var use_redis_cache
# Flag indicating if the cache is using the Redis database mmechanism.
# This is is true if the redis_store module had been loaded.

#==============================================================================#

class NIHTTPServer(ThreadingMixIn, HTTPServer):
    """
    @brief Provide a class that provides a threaded HTTP server.

    @details
    The HTTPServer class which is a subclass of TCPServer and in turn a subclass
    of SocketServer opens a socket that is bound to the specified port passed in
    the addr parameter to the constructor.  The server then sets up a listener
    waiting for connection requests arriving at this socket.
    
    The ThreadingMixIn from the SocketServer module overrides the process_request
    method in the HTTP/TCP/SocketServer so that it creates a new thread whenever
    a new connection is made and accepted.  Each thread creates an instance of
    the NIHTTPRequestHandler class that processes the requests that come in on
    this connection.

    This wrapper provides additional management for keeping track of what threads
    are in use and naming them for convenience in identifying logging messages,
    and helping with shutting down the server.  It also holds a number of pieces of
    information as instance variables derived from the configuration file and
    command line arguments that will be needed by all request handler threads.
    """

    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var storage_root
    # string pathname for root of cache directory tree
    
    ##@var server_name
    # string FQDN of server
    
    ##@var server_port
    # integer server port number used
    
    ##@var authority
    # string combination of server FQDN and server port as URL 'netloc'
    
    ##@var logger
    # object logger instance to output messages
    
    ##@var getputform
    # string pathname of GET/PUBLISH/SEARCH form HTML file
    
    ##@var nrsform
    # string pathname of NRS configuration form HTML file
    
    ##@var provide_nrs
    # boolean True if server is to offer NRS server function
    
    ##@var favicon
    # string pathname for browser favicon.ico icon file
    
    ##@var nrs_redis
    # object StrictRedis instance used for communication between the NRS server
    # and the Redis database.

    ##@var dtn_gateway_enabled
    # boolean True if run_gateway is True and the gateway was started
    #              successfully.

    ##@var dtn_gateway
    # object instance of gateway HTTP<->DTN controller.
    #                    Needed when shutting down.

    ##@var cache
    # object instance of NetInfCache interface to cache storage
    
    ##@var thread_running_lock
    # object Lock instance used to serialize access to running_threads and
    # next_handler_num
    
    ##@var running_threads
    # set contains NIHTTPRequestHandler instances that are associated with the
    # current running threads.
    
    ##@var next_handler_num
    # integer initialized to 0, incremented by one whenever a handler thread is created,
    # and the previous value used as part of the name for the thread.
    
    ##@var allow_reuse_address
    # boolean (from TCPServer) if set, when the listener socket is bound to the
    #         server address, the ioctl SO_REUSEADDR is called on the socket
    #         before being bound.  This is handy especially during development
    #         as otherwise you have to wait for a significant period (typically
    #         at least 4 minutes) while the TIME_WAIT state on the socket from
    #         a previous instance terminates before the server can be restarted
    #         using the same (address, port) pair.
    
    ##@var daemon_threads
    # boolean set to make sure all the spawned handler threads are made daemon
    #         threads. This means that the handler threads are terminated when
    #         the main thread terminates.

    #--------------------------------------------------------------------------#
    def __init__(self, addr, storage_root, authority_name, server_port,
                 logger, getputform, nrsform, provide_nrs, favicon,
                 redis_db=0, run_gateway=False):
        """
        @brief Constructor for the NI HTTP threaded server.
        @param addr tuple two elements (<IP address>, <TCP port>) where server listens
        @param storage_root string pathname for root of cache directory tree
        @param authority_name string server FQDN
        @param server_port integer server port used 
        @param logger object logger instance to output messages
        @param getputform string pathname of GET/PUBLISH/SEARCH form HTML file
        @param nrsform string pathname of NRS configuration form HTML file
        @param provide_nrs boolean True if server is to offer NRS server function
        @param favicon string pathname for browser favicon.ico icon file
        @param redis_db integer number of Redis database to use
                                (if provide_nrs True or using Redis NDO cache)
        @param run_gateway boolean True if DTN<->HTTP functionality is enabled.
        @return (none)

        Save the parameters (except for addr) as instance variables.
        These values can be accessed from the directHTTPRequestShim class
        instance that is created as a superclass of the NIHTTPRequestHandler
        class that is created to handle each incoming connection to the
        server. These handler instances run in separate threads on account of
        the ThreadingMixIn.  The server maintains a list of active threads
        managed by the add_thread and remove_thread routines. Note that a
        thread may actually handle a number of separate requests if a
        sequence of requests is marked with 'Connection: keep-alive' rather
        than 'Connection: close'. When the server run is ended any remaining
        active threads are shut down (see 'end_run').

        Call the constructor of the superclass HTTPServer but hold off
        binding the address and activating the server until the flag
        indicating that the IP address can be reused.  Set the HTTPServer
        to generate daemon thread so that they die when the main thread
        dies.

        Depending on the value of the 'Connection' header in the request, the
        thread may remain active to receive additional requests ('keep-alive'
        value) or close and terminate the thread after processing the request
        ('close' value).

        When the HTTPServer listener receives a connection request, and  creates
        a new thread to handle the request(s) that is(are) passed over the
        connection, it calls the overridden 'handle' method in the shim class.

        If run_gateway is True, the DTN connection threads are started and
        linked to the cache. 
        """
        # These are used  by individual requests
        # accessed via self.server in the handle function
        self.storage_root = storage_root
        self.server_name = authority_name
        self.server_port = server_port
        self.authority = "%s:%d" % (authority_name, server_port)
        self.logger = logger
        self.getputform = getputform
        self.nrsform = nrsform
        self.provide_nrs = provide_nrs
        self.favicon = favicon
        self.dtn_gateway_enabled = False
        self.dtn_gateway = None

        # Initialize cache
        self.cache = NetInfCache(self.storage_root, self.logger)

        # If any of:
        #  - an NRS server is wanted,
        #  - the NDO cache is using Redis, or
        #  - the HTTP<->DTN gateway is enabled,
        # create a Redis client instance
        # Assume it is the default local_host, port 6379 for the time being
        if provide_nrs or use_redis_cache or run_gateway:
            try:
                self.nrs_redis = redis.StrictRedis(db=redis_db)
            except Exception, e:
                logger.error("Unable to connect to Redis server: %s" % str(e))
                sys.exit(-1)
            # Check there is actually a server there - the connection object
            # is instantiated without complaint whether or not
            try:
                redis_info = self.nrs_redis.info()
            except Exception, e:
                logger.error("Unable to connect to Redis server - probably not running: %s" % str(e))
                sys.exit(-1)
        else:
            self.nrs_redis = None

        # If cache is using Redis, tell cache what the Redis connection is
        if hasattr(self.cache, "set_redis_conn"):
            if not self.cache.set_redis_conn(self.nrs_redis):
                sys.exit(-1)

        # Check cache is prepared
        if not self.cache.check_cache_dirs():
            sys.exit(-1)

        # If requested try to start HTTP<->DTN gateway
        if run_gateway:
            self.dtn_gateway = DtnHttpGateway(logger, self.cache, self.nrs_redis, self)
            if self.dtn_gateway is None:
                logger.error("Unable to start HTTP<->DTN gateway as requested")
                self.dtn_gateway_enabled = False
            else:
                logger.info("HTTP<->DTN gateway started")
                self.drn_gateway_enabled = True
        
        self.running_threads = set()
        self.next_handler_num = 1
        # Lock for serializing access to running_threads and next_handler_num
        self.thread_running_lock = threading.Lock()

        # Setup to produce a daemon thread for each incoming request
        # and be able to reuse address
        HTTPServer.__init__(self, addr, NIHTTPRequestHandler,
                            bind_and_activate=False)
        self.allow_reuse_address = True
        self.server_bind()
        self.server_activate()
                         
        self.daemon_threads = True
        return

    #--------------------------------------------------------------------------#
    def start(self):
        if self.dtn_gateway_enabled:
            self.dtn_gateway.start_gateway()
        HTTPServer.start(self)
        return
    
    #--------------------------------------------------------------------------#
    def add_thread(self, thread):
        """
        @brief Record a new handler thread resulting from a server connection.
        @param thread object NIHTTPRequestHandler instance instantiated to
                             handle connection.
        @return (none)

        Add the new thread to the running_threads set.  Need to grab the
        thread_running_lock before doing the addition to serialize access.
        """
        self.logger.debug("New thread added")
        with self.thread_running_lock:
            self.running_threads.add(thread)

    #--------------------------------------------------------------------------#
    def remove_thread(self, thread):
        """
        @brief Remove a handler thread from the set of running threads.
        @param thread object NIHTTPRequestHandler instance instantiated to
                             handle this connection.
        @return (none)

        Remove the thread from the running_threads set just before the thread dies.
        Need to grab the thread_running_lock before doing the addition to
        serialize access.
        """
        with self.thread_running_lock:
            if thread in self.running_threads:
                self.running_threads.remove(thread)

    #--------------------------------------------------------------------------#
    def end_run(self):
        """
        @brief Shutdown the niserver. *** Must not be called from handler threads!
        @return (none)

        Calling this method from a handler thread will result in deadlock.
        Currently called from the (separate) main thread in niserver_main.py
        
        If there are any threads in the running_threads set, request their closure.
        This closes the read and write file objects used by the handler.

        Finally shutdown the server.
        """
        for thread in self.running_threads:
            if thread.request_thread.isAlive():
                thread.request.close()
        del self.running_threads
        if dtn_gateway_enabled:
            dtn_gateway.shutdown_gateway()
        self.shutdown()

#==============================================================================#
# EXPORTED GLOBAL FUNCTIONS
#==============================================================================#
#------------------------------------------------------------------------------#
def ni_http_server(storage_root, authority, server_port, logger,
                   getputform, nrsform, provide_nrs, favicon,
                   redis_db=0, run_gateway = False):
    """
    @brief Set up the NI HTTP threaded server.
    @param storage_root string pathname for root of cache directory tree
    @param authority string FQDN for machine on which server is running
    @param server_port integer TCP port number on which service is set up
    @param logger object logger instance to output messages
    @param getputform string pathname of GET/PUBLISH/SEARCH form HTML file
    @param nrsform string pathname of NRS configuration form HTML file
    @param provide_nrs boolean True if server is to offer NRS server function
    @param favicon string pathname for browser favicon.ico icon file
    @param redis_db integer number of Redis database to use
    @param run_gateway boolean True if DTN<->HTTP functionality is enabled.
    @return threaded HTTP server instance object ready for use
    
    Before creating the server:
    - Get an honest-to-goodness routable IP address for authority using DNS
      - Python tends to give you the loopback address which
        means the server cannot be accessed from elsewhere
      - However if the authority is localhost (mainly for testing)
        just use gethostbyname.
      - If providing NRS server, check that Redis module was successfully loaded

    Create a threaded HTTP server instance and record the various parameter
    values from the server configuration in the server instance so that the
    handler can get at them

    TO DO: Handle IPv6 addresses 
    """
    if authority == "localhost":
        ipaddr = socket.gethostbyname(authority)
    else:
        try:
            ipaddr = DNS.dnslookup(authority, "A")[0]
        except:
            logger.warn("Cannot get IP address for authority from DNS")
            ipaddr = socket.gethostbyname(authority)
    logger.info("Setting up for %s at %s on port %d" % (authority,
                                                        str(ipaddr),
                                                        server_port))

    if provide_nrs or run_gateway:
        if not redis_loaded:
            logger.error("Unable to import redis module needed for NRS server and/or DTN gateway")
            sys.exit(-1)
        logger.info("Successfully loaded redis module for NRS server and/or DTN gateway")

    # Pass the parameters and the derived IP address to the constructor
    return NIHTTPServer((ipaddr, server_port), storage_root,
                        authority, server_port,
                        logger, getputform, nrsform,
                        provide_nrs, favicon,
                        redis_db, run_gateway)

#==============================================================================#

#==============================================================================#
# TESTING CODE
#==============================================================================#
if __name__ == "__main__":

    from nihandler import NDO_DIR, META_DIR
    from metadata import NetInfMetaData
    #==== TEST FUNCTIONS ====
    def test_client(my_host, my_port, ip, port, message):
        """
        @brief Simulate an HTTP client - push message to niserver
        @param my_host string hostname where client is running
        @param my_port integer port to use for client
        @param ip string IP address being used by server
        @param port integer port on which server is listening
        @param message string message to send
        @return message string received

        Opens TCP connection from(my_host, my_port) to (ip, port)

        Sends message across connection

        Reads socket until it closes, close down connection from this end
        and return message received.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((my_host, my_port))
        sock.connect((ip, port))
        sock.send(message)
        time.sleep(1)
        m = sock.recv(4096)
        sock.close()
        return m

    def test_main():
        """
        @brief Perform some very limited local tests

        A small file is inserted into the cache other than via publish

        A simulated form string is provided.

        Six tests are performed using test_client. They are not exhaustive
        but serve to show the basic functionality is working:
        - Test that GET is rejecting unknown URLs
        - Test GET is rejecting URLs with fragment parts
        - Test server is rejecting unrecognized request types
        - Test valid .well-known URL getting back redirect
        - Test redirected URL from previous case and check content returned
        - Test POST can read a simple form and detect that it doesn't have the file.

        TO DO: More sophisticated tests can be carried out on the full server using curl.
        """

        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#

        # This string is a very simple example of what is sent from client to
        # server when the client is using a 'form' to send various data items.
        
        fd="""Content-Type: multipart/form-data; boundary="--aea19b03abac"
Connection: close

----aea19b03abac
Content-Disposition: form-data; name="URI"

ni:///sha-256-32;gf2yhA
----aea19b03abac
Content-Disposition: form-data; name="msgid"

aaabbb
----aea19b03abac--


"""

        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#

        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        # Port 0 means to select an arbitrary unused port
        HOST, PORT = "localhost", 0

        # Temporary storage root
        sd = "/tmp/niserver_test"

        server = NIHTTPServer((HOST, PORT), sd, "example.com", PORT, logger,
                              "./data/getputform.html", "./data/nrsconfig.html",
                              False, "./data/favicon.ico")

        # Create a dummy file to get
        shutil.rmtree(sd, ignore_errors=True)
        os.mkdir(sd)
        os.mkdir(sd+NDO_DIR)
        os.mkdir(sd+NDO_DIR+"sha-256")
        os.mkdir(sd+META_DIR)
        os.mkdir(sd+META_DIR+"sha-256")
        content_str = "The quick yellow fox burrowed under the twisting worm.\n"
        ni_name = ni.NIname("ni:///sha-256")
        uri = ni.NIproc.makenib(ni_name, content_str)
        dgst = ni_name.get_digest()
        ndo_fn = sd+NDO_DIR+"sha-256"+"/"+dgst
        meta_fn = sd+META_DIR+"sha-256"+"/"+dgst
        logger.info("NDO path: %s" % ndo_fn)
        logger.info("META path: %s" % meta_fn)
        fn = "/sha-256/"+dgst
        f = open(ndo_fn, "wb")
        f.write("The quick yellow fox burrowed under the twisting worm.\n")
        f.close()
        timestamp = datetime.datetime.utcnow().strftime("%y-%m-%dT%H:%M:%S+00:00")
        extrameta = {}
        extrameta["publish"] = "test"
        md = NetInfMetaData(ni_name.get_url(), timestamp, "text/plain", "localhost",
                            None, None, extrameta)
        print md
        f = open(meta_fn, "w")
        json.dump(md.json_val(), f)
        f.close()


        ip, port = server.server_address

        # Start a thread with the server -- that thread will then start one
        # more thread for each request
        server_thread = threading.Thread(target=server.serve_forever,
                                         name="Niserver Listener")
        # Exit the server thread when the main thread terminates
        server_thread.setDaemon(True)
        server_thread.start()
        logger.info("Server loop running in thread:%s" % server_thread.getName())

        # Note server will hang if sent message with just one \r\n on the end
        # Needs to be thought about (timeouts!)
        logger.info(test_client(HOST, PORT, ip, port, "GET /some/path HTTP/1.0\r\n\r\n"))
        logger.info(test_client(HOST, PORT, ip, port, "GET /other/path;digest?q=d#dfgg HTTP/1.0\r\n\r\n"))
        logger.info(test_client(HOST, PORT, ip, port, "BURP /other/path HTTP/1.0\r\n\r\n"))
        logger.info(test_client(HOST, PORT, ip, port, "GET %s HTTP/1.0\r\n\r\n" % ("/.well-known/ni"+fn)))
        logger.info(test_client(HOST, PORT, ip, port, "GET %s HTTP/1.0\r\n\r\n" %
                                ("/ni_cache/sha-256;"+dgst)))
        logger.info(test_client(HOST, PORT, ip, port, "POST %s HTTP/1.0\r\n%s" % ("/netinfproto/get", fd)))
        server.end_run()
        logger.info("Server shutdown")

        return

    #==== Run tests ====
    print "Testing niserver - no NRS server"
    test_main()
        
