#!/usr/bin/python
"""
@package nilib
@file nihandler.py
@brief Request handler for  NI NetInf HTTP convergence layer (CL) server and
@brief NRS server.  Designed to be used either via WSGI or BaseHTTPRequestHandler
@brief by importing appropriate shim.
@version $Revision: 1.03 $ $Author: elwynd $
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
nihandler.py overview

Provides the core HTTP request handler for a server managing a cache of Named
Data Objects (NDOs) named with URIs from the ni scheme (ni://.. or nih:/...)
allowing clients to access, publish or search these NDOs using the NetInf
protocol over the HTTP CL.

Implements
- NetInf proto GET, PUBLISH and SEARCH with HTTP convergence layer
  including handling metadata
- Direct GETs of Named Data Objects via HTTP URL translations of ni: names.
- Various support functions including listing the cache, delivering a form
  to generate the POST functions and returning a favicon.ico
- Optionally, provision of Name Resolution Server (NRS) support, controlled by
  configuration file option.

The handler deals with a limited set of URLs

- GET/HEAD on paths:
                 - /.well-known/ni[h]/<digest algorithm id>/<digest>,
                 - /ni_cache/<digest algorithm id>;<digest>,
                 - /ni_meta/<digest algorithm id>;<digest>,
                 - /getputform.html,
                 - /nrsconfig.html, (when running NRS server)
                 - /favicon.ico, and<
                 - /netinfproto/list
                 - /netinfproto/checkcache
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

The basic GET and POST handlers are inspired by Doug Hellmann's writing on
on BaseHTTPServer in his Python Module of the Week series at
http://www.doughellmann.com/PyMOTW/BaseHTTPServer/index.html

The handler expects to have the following instance variables set up:

- server_port     the TCP port used by the HTTP server listener (default 8080)
- server_name     the hostname part of the address of the HTTP server
- authority       Combination of server_name and server_port as expected in netloc
- storage_root    the base directory where the content cache is stored
- provide_nrs     flag indicating if NRS operations should be supported by
                  this server
- redis_nrs       REDIS server connection (None if provide_nrs is False)
- getputform      pathname for a file containing the HTML code uploaded to show
                  the NetInf GET/PUBLISH/SEARCH forms in a browser
- nrsform         pathname for file containing the HTML code uploaded to show
                  the NetInf NRS configuration forms in a browser
- favicon         pathname for favicon file sent to browsers for display.

Also instance variables must be set up to provide logging functions at various
levels (each takes a string to be logged):
- logdebug
- logerror
- logwarn
- loginfo

TO DO: Add configuration to connect to non-default Redis server.

The handler is designed so that it can be used from
- an Apache 2 mod_wsgi 'application' function,
- any other WSGI server framework (a simple example using the standard Python
  wsgiref simple_server reference implementation can be found in
  nilib/test/test_wsgi_server.py), or
- via a standalone server based on the HTTPServer/BaseHTTPRequestHandler
  paradigm as implemented in niserver_main.py and niserver.py.

The adaptation is handled by inheriting HTTPRequestShim from an appropriate
shim module.  The shim is selected at run time depending on which
module imports the handler.

In either case the server manages a local cache of published information.
The cache is encapsulated in the NetInfCache class.  Various implementations
of the class are provided:
- cache_single.py: File system storage appropriate for single-process/multi-
  threaded server.  Integrity is maintained by a threading Lock and a in-memory
  cache is maintained.
- cache_multi.py: File system storage approproiate for multi-process and
  possibly multi-threadee servers such as an Apache server with mod_wsgi.
  Integrity is maintained by operating system file locks.
- cache_redis: Cache using the Redis NoSQL database for metadata with the
  content in the filesystem.

The cache contains connected entries for entries partitioned according to the
digest algorithm used.  Each entry contains metadata about the NDO (in  all
cases) and, if it is known, the content octets of the NDO>

See the draft-kutscher-icnrg-netinfproto specification for the relationship
between the terms 'affiliated data' and 'metadata': broadly, the affiliated
data represents all the extra attributes that need to be maintained in
association with the NDO.

The entries are indexed by the ni format of the digest but may be published
or retrieved using the nih format of the digest if required.

Entries are inserted into the cache by the  NetInf 'publish' (or 'put') function
or can be generated externally and tied into the cache.

For a given entry (i.e., unique digest) it is required that there will be at
least a metadata entry.  The corresponding content may or may not be present
depending on whether it was published (or whether the server decides to delete
the file because of policy constraints - such as space limits or DoS avoidance
by deleting files after a certain length of time - note that deletion is not
currently implemented but may be in future).

Metadata entries contain a string encoded JSON object.  When this is loaded into
memory, it is managed as a Python dictionary (to which it bears an uncanny
resemblance!).  This is encapsulated in an instance of the niserver::NetInfMetaData
class.

A large majority of the code of the server is contained in the
NIHTTPRequestHandler class in this module.  This was originally a subclass of
the standard BaseHTTPequestHandler.  To allow alternative use via the WSGI
Python web server interface, the 'handle' initializer routine that sets up
instance variables is moved to the shim for the BaseHTTPRequestHandler case -
all references to the link to the (NI)HTTPServer through self.server are
confined to the shim.  The alternative WSGI shim takes values from the WSGI
environment and emulates the BaseHTTPRequestHandler interface.  The only extra
routines needed are to handle the writing of files and multiple sections of
output to the 'response' stream - this has to be organized as an iterable for
WSGI.

If specified in the configuration (provide_nrs is True), the handler will also
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
1.3       06/12/2012 Elwyn Davies   Corrected interface to check_cache_dirs.
1.2       04/12/2012 Elwyn Davies   Major surgery to manage the NDO cache through
                                    a separate class (which of course should have
                                    been done to start with).  Also improved the
                                    oranization of the send_head routine to use
                                    common code and a dictionary.  This class
                                    no longer knows anything about how the cache
                                    is stored.
1.1       30/11/2012 Elwyn Davies   Split out metadata class.  Manage loading correct
                                    shim when testing niserver.py and export
                                    NDO_DIR and META_DIR.
1.0       24/11/2012 Elwyn Davies   Updated header comments.  Changed shim imports
                                    to alias HTTPRequestShim so that Doxygen
                                    doesn't get confused. Add GET request to
                                    check cache dirs (convenience for WSGI case).
0.0       17/11/2012 Elwyn Davies   Split out from niserver.py and adapted to
                                    allow use with either WSGI or
                                    BaseHTTPRequestHandler.
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

#=== Local package modules ===

from netinf_ver import NETINF_VER, NISERVER_VER
from ni import NIname, NIdigester, NIproc, NI_SCHEME, NIH_SCHEME, ni_errs, ni_errs_txt

# See if this run is either testing niserver.py or running standalone server
# If either is true then use the HTTPRequestShim in httpshim.py
try:
    main_mod_file = sys.modules["__main__"].__file__
except:
    main_mod_file = ""

if main_mod_file.find("niserver.py") >= 0:
    from httpshim import directHTTPRequestShim as HTTPRequestShim
    from cache_single import SingleNetInfCache as NetInfCache
elif "niserver" in sys.modules:
    from httpshim import directHTTPRequestShim as HTTPRequestShim
    from cache_multi import MultiNetInfCache as NetInfCache
else:
    # Assume we are running under mod_wsgi - use the shim in wsgishim.py
    from wsgishim import wsgiHTTPRequestShim as HTTPRequestShim
    
from  metadata import NetInfMetaData

    
#==============================================================================#
# List of classes/global functions in file
__all__ = ['NIHTTPRequestHandler']

#==============================================================================#
#=== Exceptions ===
#------------------------------------------------------------------------------#
from ni_exception import InconsistentParams, InvalidMetaData, \
                         CacheEntryExists, NoCacheEntry

#==============================================================================#

class NIHTTPRequestHandler(HTTPRequestShim):
    """
    @brief Action routines for all requests handled by niserver.

    @details

    This class provides methods for processing HTTP requests according to the
    request received which may be HEAD, GET or POST.

    The shim superclass from which this is derived sets up the instance
    variables form the information it receives when setup and called to process
    an HTTP request that has been received.

    Depending on the request, one of do_HEAD, do_GET or do_POST will be called.

    These routines examine the request, determine if it is one which they
    are setup to process and then either use send_error to respond with an error
    code or use a combination of send_request, send_header and end_headerss to set up
    the response preamble and a combination of send_string and send_file calls to
    cobfigure the response body.
    
    Note: Many instance variables are defined in the superclass(es).
    """

    #--------------------------------------------------------------------------#
    # CONSTANT VALUES USED BY CLASS
    
    ##@var PUBLISH_REF
    # Publisher version string
    PUBLISH_REF     = ("Python niserver.py %s" % NISERVER_VER)
    
    # === Fixed strings used in NI HTTP translations and requests ===
    ##@var WKN
    # Start of path for http://<netloc>/.well_known/ni[h]/<alg name>/digest
    WKN             = "/.well-known/"
    
    ##@var CONT_PRF
    # Start of path for http://<netloc>/ni_cache/<alg name>;<digest>
    # for accessing content files directly
    CONT_PRF        = "/ni_cache/"
    
    ##@var META_PRF
    # Start of path for http://<netloc>/ni_meta/<alg name>;<digest>
    # for accessing metadata files directly
    META_PRF        = "/ni_meta/"
    
    ##@var QRCODE_PRF
    # Start of path for http://<netloc>/ni_qrcode/<alg name>;<digest>
    # for accessing QRcode image encoding an ni[h] URI 
    QRCODE_PRF      = "/ni_qrcode/"
    
    ##@var NI_HTTP
    # Path prefix for /.well-known/ni/ 
    NI_HTTP         = WKN + "ni/"
    
    ##@var NIH_HTTP
    # Path prefix for /.well-known/nih/ 
    NIH_HTTP        = WKN + "nih/"
    
    ##@var FAVICON_FILE
    # Path value for accessing favicon file
    FAVICON_FILE    = "/favicon.ico"
    
    ##@var METADATA_TIMESTAMP_TEMPLATE
    # Template as used by datetime strftime for timestanps in metadata files
    METADATA_TIMESTAMP_TEMPLATE = "%y-%m-%dT%H:%M:%S+00:00"
    
    # === Content Type related items ===
    ##@var DFLT_MIME_TYPE
    # Default mimetype to use when we don't know.
    DFLT_MIME_TYPE  = "application/octet-stream"
    
    ##@var TI
    # Type introducer string for query string in cached file names
    # not currently used - should be specified as RE
    TI              = "?ct="

    # === NetInf NDO Cache listing and checking ===
    ##@var NETINF_LIST
    # URL path to invoke return of cache list via GET
    NETINF_LIST     = "/netinfproto/list"
    
    ##@var ALG_QUERY
    # Query string item for selecting the digest algorithm when listing the cache.
    ALG_QUERY       = "alg"
    
    ##@var NETINF_CHECK
    # URL path to invoke check/creation of cache directory tree via GET
    NETINF_CHECK   = "/netinfproto/checkcache"

    # === NetInf GET/PUBLISH/SEARCH form names used from the getputform ===
    ##@var NI_ACCESS_FORM
    # Path value for accessing GET/PUBLISH/SEARCH form
    NI_ACCESS_FORM  = "/getputform.html"
    
    ##@var NETINF_GET
    # Path to which to send form for NetInf GET operation
    NETINF_GET      = "/netinfproto/get"
    
    ##@var NETINF_PUBLISH
    # Path to which to send form for NetInf PUBLISH operation
    NETINF_PUBLISH  = "/netinfproto/publish"
    
    ##@var NETINF_PUT
    # Alternative path to which to send form for NetInf PUBLISH operation
    NETINF_PUT      = "/netinfproto/put"
    
    ##@var NETINF_SEARCH
    # Path to which to send form for NetInf SEARCH operation
    NETINF_SEARCH   = "/netinfproto/search"

    # === Search related info ===
    ##@var WIKI_LOC
    # Server name for Wikipedia searches
    WIKI_LOC        = "en.wikipedia.org"
    
    ##@var WIKI_SRCH_API
    # Template for OpenSearch interface to Wikipedia
    WIKI_SRCH_API   = ("http://%s/w/api.php?action=opensearch&search=%s&" + \
                       "limit=10&namespace=0&format=xml")
    
    ##@var SRCH_NAMESPACE
    # XML namespace used by OpenSearch suggestions returned from Wikipedia
    SRCH_NAMESPACE  = "http://opensearch.org/searchsuggest2"
    
    ##@var SEARCH_REF
    # String recorded in 'searcher' field of NDO metadata after a search done
    # by this program.
    SEARCH_REF      = ("Python niserver.py %s" % NISERVER_VER)
    
    ##@var SRCH_CACHE_SCHM
    # URL scheme for names constructed for NDOs created from search responses
    # flagged by Wikipedia.
    SRCH_CACHE_SCHM = "ni"
    
    ##@var SRCH_CACHE_DGST
    # Digest algorithm used for NDOs created from search responses flagged by
    # Wikipedia.
    SRCH_CACHE_DGST = "sha-256"

    # === NRS server related info ===
    ##@var NRS_CONF_FORM
    # Path value for accessing NRS configuration form
    NRS_CONF_FORM   = "/nrsconfig.html"
    
    ##@var NRS_CONF
    # Path to which to send form for NetInf GET operation
    NRS_CONF        = "/netinfproto/nrsconf"
    
    ##@var NRS_LOOKUP
    # Path to which to send form for NetInf GET operation
    NRS_LOOKUP      = "/netinfproto/nrslookup"
    
    ##@var NRS_DELETE
    # Path to which to send form for NetInf GET operation
    NRS_DELETE      = "/netinfproto/nrsdelete"
    
    ##@var NRS_VALS
    # Path to which to send form for NetInf GET operation
    NRS_VALS        = "/netinfproto/nrsvals"

    ##@var CHECK_CACHE_REPORT
    # string template used after successful cache check
    CHECK_CACHE_REPORT = """\
    <head>
    <title>NetInf Cache Check</title>
    </head>
    <body>
    <h1>NetInf Cache Check</h1>
    <p>NetInf Named Data Object cache at %(server)s is correctly configured.
    </body>
    """
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    # === Application Variables ===
    ##@var storage_root
    # string pathname for base directory of storage cache
    
    ##@var getputform
    # string pathname for file containing HTML form template for netinfproto
    
    ##@var nrsform
    # string pathname for file containing HTML form template for nrsconf
    
    ##@var favicon
    # string pathname for favicon for NetInf operations
    
    ##@var provide_nrs
    # boolean if True server supports NRS operations and needs Redis interface
    
    ##@var server_name
    # string FQDN of server hosting this program
    
    ##@var server_port
    # integer port number on which server is listening
    
    ##@var authority
    # string combination of server_name and server_port as used for netloc
    # of URLs
    
    ##@var nrs_redis
    # object instance of Redis database interface (or None if provide_nrs False)

    ##@var cache
    # object instance of NetInfCache interface to cache storage
    
    # === Logging convenience functions ===
    ##@var loginfo
    # Convenience function for logging informational messages
    
    ##@var logdebug
    # Convenience function for logging debugging messages
    
    ##@var logwarn
    # Convenience function for logging warning messages
    
    ##@var logerror
    # Convenience function for logging error reporting messages
    
    #--------------------------------------------------------------------------#
    def do_GET(self):
        """
        @brief Serve a GET request.

        Processing is performed by send_head which will send the HTTP headers
        and generally leave a file descriptor ready to read with the body
        unless there is an error.
        If send_head returns a file object, pass it to send_file for dispatch
        as response.

        @return (none)
        """
        f = self.send_head()
        if f:
            self.send_file(f)
        return

    #--------------------------------------------------------------------------#
    def do_HEAD(self):
        """
        @brief Serve a HEAD request.

        Processing is performed by send_head which will send the HTTP headers
        and generally leave a file descriptor ready to read with the body
        unless there is an error.
        If send_head returns a file object, just close the file as the HEAD
        request just wants the HTTP headers.

        @return (none)
        """
        f = self.send_head()
        if f:
            f.close()
        return

    #--------------------------------------------------------------------------#
    def send_head(self):
        """
        @brief Common code for GET and HEAD commands.
        @return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        None of the URLs recognized by niserver for GET use fragments.
        Immediately reject requests that have fragment modifiers.
        
        Only the cache listing URL for GET request uses a query string
        Reject any requests other than for cache listing that have a
        query string.

        There are five special cases:
        - 1. Getting a listing of the cache
        - 2. Returning the form code for GET/PUT/SEARCH form
        - 3. If running NRS server, return the form code for NRS configuration 
        - 4. Returning the NETINF favicon
          5. Running the cache check/create function (check_cache_dirs)

        Otherwise, we expect one of
        - 5. a path that starts with the CONT_PRF prefix
             which is a direct access for the combined metadata and content of
             one of the cached NDO files if both are available, or just the
             metadata if the content file is not currently cached.
        - 6. a path that starts with the META_PRF prefix
             which is a direct access for the metadata of one of the
             cached files, or
        - 7. a path that starts with the QRCODE_PRF prefix
             which is a direct access for an image of QRcode for the ni[h]
             URI of one of the cached files, or
        - 8. a path that starts /.well-known/ni[h]/ that sends a redirect
             for the equivalent ni_cache URL (see 5 above). The redirect
             is required by standards that recommend that URLS containing
             .well-known should not generate a large amount of return traffic.

        Case 5 - 8 use the alg_digest_get_dict (see the end of this file) to
        allow the use of common code to generate a suitable NIname instance
        that can be passed to the appropriate function that generates the
        HTTP response for the case.  With this technique, the cehcking of
        the path can be common and the generation code does not require
        any further error checking.
        
        @return Readable file-like object from which the response body
                can be read or None if the response body has already been
                transferred (using send_string or send_file).
        """ 
        self.loginfo("start,req,%s,from,%s,path,%s" % (self.command,
                                                       self.client_address,
                                                       self.path))

        # Record presence or absence of query string and fragments
        has_query_string, has_fragments = \
                          self.check_path_for_query_and_fragments(self.path)

        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
        # Deal with 'special cases'

        # Of the GET URLs recognized by niserver, only the cache listing
        # uses the query string, but doesn't want fragments
        if has_fragments:
            self.loginfo("Received GET/HEAD with unwanted fragment part: '%s'" %
                         self.path)
            self.send_error(400, "Fragment modifiers not allowed")
            return None
            
        # Display a cache listing
        if self.path.lower().startswith(self.NETINF_LIST):
            return self.showcache(self.path.lower())

        # None of the other GET URLs recognized by niserver wants a query string.
        if has_query_string:
            self.loginfo("Received GET/HEAD with unwanted query string: '%s'" %
                         self.path)
            self.send_error(400, "Query string not allowed")
            return None
        
        # Display the PUBLISH/GET/SEARCH form for this server.
        # The HTML code is in a file with pathname configured and
        # passed to server.
        if (self.path.lower() == self.NI_ACCESS_FORM):
            return self.send_fixed_file( self.getputform,
                                         "text/html",
                                         "form definition")

        # Display the NRS form for this server, if running NRS server.
        # The HTML code is in a file with pathname configured and
        # passed to server.
        if (self.path.lower() == self.NRS_CONF_FORM):
            if not self.provide_nrs:
                self.loginfo("Request for NRS configuration form when not running NRS server")
                self.send_error(404, "NRS server not running at this location")
                return None
            # Display the form
            return self.send_fixed_file( self.nrsform,
                                         "text/html",
                                         "form definition")

        # Return the 'favicon' usually displayed in browser headers
        # Filename is configured and stored in self.favicon
        if (self.path.lower() == self.FAVICON_FILE) :
            self.logdebug("Getting favicon")
            return self.send_fixed_file( self.favicon,
                                         "image/x-icon",
                                         "form definition")

        # Eun the check_cache_dirs function
        if (self.path.lower() == self.NETINF_CHECK):
            self.logdebug("Running check_cache_dirs")
            try:
                # Returns temporary directory in use if successful
                td = self.cache.check_cache_dirs()
            except IOError, e:
                self.logerror("Cache tree check failed: %s" % str(e))
                self.send_error(500, "Named Data Object cache check failed")
            else:
                # Cache is in good shape - report this
                content = self.CHECK_CACHE_REPORT % { "server": self.server_name}
                self.send_response(200, "OK")
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.send_string(content)
            return None          
                        
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
        # Deal with operations that retrieve cached NDO content, metadata files
        # or a QRcode image for the ni scheme URI for the NDO.

        # In all these cases the path that is passed in consists of a fixed
        # prefix in the form "/.*/" followed by either:
        #       <alg>;<digest> possibly with a query string ?<query string>
        #  or
        #       <alg>/<digest> possibly with a query string ?<query string>
        #
        prefix_end = -1
        for alg_prefix in NIname.hash_alg_prefixes:
            prefix_end = self.path.rfind(alg_prefix)
            if prefix_end >= 0:
                break
        if prefix_end < 0:
            self.loginfo("No recognized algorithm specifier in path: %s" % self.path)
            self.send_error(400, "Path does not contain a recognized algorithm specifier")
            return None
        # Character after / at beginning of alg_prefix string
        prefix_end += 1
        url_path_prefix = self.path[:prefix_end]

        # Look up the prefix in the alg_digest_get_dict
        # If there is an entry then the value is used to guide the rest of the
        # method.
        if not url_path_prefix in alg_digest_get_dict:
            self.loginfo("Path does start with recognized prefix: %s" % self.path)
            self.send_error(400, "Path prefix is not recognized by this server")
            return None
        prefix_op = alg_digest_get_dict[url_path_prefix]

        # Turn the path into an NIname instance and validate it
        rv, ni_name = self.path_to_ni_name(self.path[prefix_end:], prefix_op.sep)
        if rv != ni_errs.niSUCCESS:
            self.loginfo("Path format for %s inappropriate: %s" % (self.path,
                                                                   ni_errs_txt[rv]))
            self.send_error(400, prefix_op.errmsg % ni_errs_txt[rv])
            return None

        # Access the cache for the ni_name
        try:
            metadata, content_file = self.cache.cache_get(ni_name)
        except NoCacheEntry:
            self.loginfo("Named Data Object not in cache: %s" % self.path)
            self.send_error(404, "Named Data Object not in cache")
            return None
        except Exception, e:
            self.logerror(str(e))
            self.send_error(500, str(e))
            return None

        self.loginfo("%s,uri,%s,ctype,%s,size,%s" % (prefix_op.op_name,
                                                     ni_name.get_canonical_ni_url(),
                                                     metadata.get_ctype(),
                                                     metadata.get_size()))

        # The send_op item in the dictionary is an NIHTTPRequestHandler
        # unbound function instance - so give it the self parameter here
        return prefix_op.send_op(self, ni_name, metadata, content_file, None)

    #--------------------------------------------------------------------------#
    def showcache(self, path):
        """
        @brief Code to generate a cache listing for some or all of the NDO cache.
        @param path string path from original HTTP request (forced to lower case)
        @return Pseudo-file object containing the HTML to display listing

        This function is invoked for GET requests when the path is
        /netinfproto/list optionally qualified by a query string of the
        form ?alg=<hash algorithm name>.

        If there is no query string directory listings for all available
        hash algorithms are displayed.  Otherwise a listing for just one
        algorithm is displayed.  The set of available algorithms is defined by
        NIname.get_all_algs() which returns a list of the textual names of
        the possible algorithms.

        This method passes the list of algorithms for which listings are
        required to the cache_list method in the cache.  The format of
        the response is an array of dictionaries for each algorithm
        This code dynamically builds some HTTP to display the selected
        directory listing(s).  The entries for each algorithm are displayed with
        the digest strings sorted insensitively.

        If the content file is present the displayed ni URI is a link
        to the .well-known HTTP URL that would retrieve the content.
        If there is metadata for the ni[h] URI, the word 'meta' is displayed
        after the URI giving a link to just the metadata.
        In addition, the word 'QRcode' is displayed with a link that will
        display a QRcode image for the ni name for the item. 
        """
        # Determine which directories to list - assume all by default
        algs_list = NIname.get_all_algs()
        query_dict = {}
        rform = "html"
        ql = len(self.NETINF_LIST)
        if (len(path) > ql):
            # Note: the caller has already checked there is no fragment part
            # Check if there is a query string
            if (path[ql] != '?'):
                self.loginfo("Unimplemented request: %s" % path) 
                self.send_error(404, "Unimplemented request %s" % path)
                return None
            if (len(path) == (ql + 1)):
                self.loginfo("Empty query string: %s" % path)
                self.send_error(400, "Empty query string: %s" % path)
                return None
            # Turn the query string into a dictionary
            qi = path[(ql + 1):].split("&")
            for i in qi:
                if len(i) == 0:
                    self.loginfo("Empty query item in query string: %s" % path)
                    self.send_error(400, "Empty query item in query string: %s" %
                                    path)
                    return
                qp = i.split("=")
                if len(qp) == 1:
                    query_dict[qp[0]] = ""
                elif len(qp) > 2:
                    self.loginfo("Bad query item in query string: %s" % path)
                    self.send_error(400, "Bad query item in query string: %s" %
                                    path)
                    return
                else:
                    query_dict[qp[0]] = qp[1] 
                    
            if (self.ALG_QUERY in query_dict):
                if (query_dict[self.ALG_QUERY] not in algs_list):
                    self.send_error(404, "Cache for unknown algorithm requested")
                    return
                else:
                    algs_list = [ query_dict[self.ALG_QUERY]]

            rform = query_dict.get("rform", "html")
            if not ((rform == "html") or (rform == "plain")): 
                self.loginfo("Unrecognized response format for showcache: %s" % path)
                self.send_error(400, "Unrecognized response format: %s" % path)
                return

        # Server access netloc
        if (self.server_port == 80):
            # Can omit the default HTTP port
            netloc = self.server_name
        else:
            netloc = "%s:%d" % (self.server_name, self.server_port)

        # Get the cache listing as a dictionary
        cache_list = self.cache.cache_list(algs_list)
        if cache_list is None:
            self.send_error(500, "Unable to list Named Data Object cache.")
            return None
        
        self.loginfo("showcache,algs,%s,rform,%s" % (";".join(algs_list), rform))

        # Do simple plain output if requested
        if rform == "plain":
            # Set up a StringIO buffer to gather the text
            f = StringIO()
            os = "Named Data Object Cache Listing for server %s\n" % netloc
            f.write(os)
            f.write("=" * (len(os) - 1))
            f.write("\n\n")

            for alg in algs_list:
                all_ordered = sorted(cache_list[alg],
                                     key = lambda k: k["dgst"].lower())
            
                os = "Cache Listing for Algorithm %s\n" % alg
                f.write(os)
                f.write("-" * (len(os) - 1))
                f.write("\n\n")

                for name in sorted(cache_list[alg],
                                   key = lambda k: k["dgst"].lower()):
                    dgst = name["dgst"]
                    # Indicate what is available
                    if name["ce"]:
                        f.write('Metadata and content: %s;%s\n' % (alg, dgst))
                    else:
                        f.write('Metadata only:        %s;%s\n' % (alg, dgst))
                                        
                f.write("\n")
                
            length = f.tell()
            f.seek(0)
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Content-Disposition", "inline")
            self.send_header("Content-Length", str(length))
            self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
            self.send_header("Last-Modified", self.date_time_string())
            self.end_headers()
            return f

        # Otherwise do HTML output
                                          
        # Set up a StringIO buffer to gather the HTML
        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Named Data Object Cache Listing for server %s</title>\n" % self.server_name)
        f.write("<body>\n<h1>Named Data Object Cache Listing for server %s</h1>\n" % self.server_name)
        f.write("<hr>\n<ul>")

        for alg in algs_list:
            all_ordered = sorted(cache_list[alg],
                                 key = lambda k: k["dgst"].lower())
            
            f.write("</ul>\n<h2>Cache Listing for Algorithm %s</h2>\n<ul>\n" % alg)
            ni_http_prefix   = "http://%s%s%s/" % (netloc, self.NI_HTTP, alg)
            meta_http_prefix = "http://%s%s%s;" % (netloc, self.META_PRF, alg)
            qrcode_http_prefix = "http://%s%s%s;" % (netloc, self.QRCODE_PRF, alg)
            ni_prefix        = "ni:///%s;" % alg
            nih_prefix       = "nih:/%s;" % alg
            for name in sorted(cache_list[alg], key = lambda k: k["dgst"].lower()):
                dgst = name["dgst"]
                # Link or ni URL for content file
                if name["ce"]:
                    f.write('<li><a href="%s%s">%s%s</a> ' %
                            (ni_http_prefix, dgst, ni_prefix, dgst))
                else:
                    # No link if content file is not present 
                    f.write('<li>%s%s ' % (ni_prefix, dgst))
                
                f.write('(<a href="%s%s">meta</a>)' % (meta_http_prefix, dgst))
                f.write('(<a href="%s%s">QRcode</a>)</li>\n' %
                        (qrcode_http_prefix, dgst))
                
            f.write("\n")
        f.write("</ul>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
        self.send_header("Last-Modified", self.date_time_string())
        self.end_headers()
        return f              

    #--------------------------------------------------------------------------#
    def send_fixed_file(self, pathname, content_type, err_string):
        """
        @brief Send the contents of a fixed file back to the client
        @param pathname string Full pathname for file to be sent
        @param content_type string MIME type for file to be sent
        @param err_string string kind of file description used in error messages
        @return file object opened for reading of file or None if error
        """
        try:
            f = open(pathname, 'rb')
        except Exception:
            self.logerror("Cannot open %s file '%s'" %
                          (err_string, pathname))
            self.send_error(404, "File for %s not available" % err_string)
            return None
        try:
            f.seek(0, os.SEEK_END)
            file_len = f.tell()
            f.seek(0, os.SEEK_SET)
            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", str(file_len))
            self.end_headers()
        except:
            self.logerror("Unable to read %s file '%s'" %
                          (err_string, pathname))
            self.send_error(404, "Cannot read %s file" % err_string)
            f.close()
            f = None

        self.loginfo("file,%s,length,%d" % (pathname, file_len))
                     
        return f

    #--------------------------------------------------------------------------#
    def send_get_header(self, ni_name, metadata, content_file, msgid):           
        """
        @brief Send headers and data for the response to a get request.
        @param ni_name NIname instance  representing alg-name/digest received
                                        with HTTP GET request
        @param metadata NetInfMetadata instance holds metadata for ni_name
        @param content_file string pathname to content file if present or None
        @param msgid string or None (for direct ni_cache accesses)
        @return None - see below for explanation.

        This function is used both to handle
        - direct GET requests of HTTP URLS http://<netloc>/ni_cache/<alg>;<digest>, and
        - PUBLISH requests of ni scheme URIs using the NetInf GET form 
        
        The cache of Named Data Objects contains files that have the
        digest as file name.  This makes it impossible to guess
        what the content type of the file is from the name.
        The content type of the file is stored in the metadata for the
        NDO. If we weren't told what sort of file it was when the file
        was published or we can't deduce it from the contents then it
        defaults to application/octet-stream.

        On entry the alg-name and digest have been incorporated into a
        validated NIname instance (ni_name). The ni_name has been used to
        determine there is a cache entry for the ni_name.  The metadata for
        the entry and (if present) the file name of the content_file are
        passed in as parameters.

        Note: The ni_name and content_file are not used in this method but
        the interface is common for various GET patterns that result in
        various send_xx_header methods called via the alg_digest_get_dict.

        The parameters are all nominally validated and the cache entry
        checked for existence and correctness.  All that is necessary is to
        generate the HTTP response.
        For this routine:
        - Check the meta_path corresponds to a real file
            - send 404 error if not
        - Read in the metadata and decode JSON
            - send 500 error if file is unreadable or mangled
        - check if content file exists:
            - if not, just send metadata as JSON string (with added status)
            - if so, then
                - open the file and find out how large it is
                    - send 404 error if opening for reading fails
        - send 200 OK and appropriate headers (application/json if only metadata,
          multipart/mixed if both metadata and NDO content)
        - send MIME boundary if sending both JSON and content
        - send the JSON
        - if sending content send MIME boundaries and content file.

        Note that because of the MIME possible boundaries and sending from
        several sources, for this case the sending of the HTTP body is
        handled in this routine instead of passing a file object back to
        top level of handler.
        """
        f = None
        self.logdebug("send_get_header for path %s" % ni_name.get_url())

        # Check if content is present
        if content_file is not None:
            try:
                cf = open(content_file, "rb")
            except IOError, e:
                self.logerror("Unable to open file %s for reading: %s" %
                              (content_file, str(e)))
                self.send_error(500, "Unable to open content file")
                return None
            fs = os.fstat(cf.fileno())
            ct_length = fs[stat.ST_SIZE]
            have_content = True
        else:
            have_content = False
            
        if have_content:
            # Return two part multipart/mixed MIME message
            # Part 1 - application/json encoded metadata
            # Part 2 - content according to type

            # Assemble body for message and calculate length
            # Put together the part before the content file in a StringIO
            mb = self.mime_boundary()
            final_mb = "--" + mb + "--"
            f = StringIO()
            # Initial MIME boundary
            f.write("--" + mb + "\n")
            # Part 0 - Metadata as JSON string
            f.write("Content-Type: application/json\nMIME-Version: 1.0\n\n")
            # Add the locator of this node to the locator list in the summary
            json_obj = metadata.summary(self.authority)
            json_obj["status"] = 200
            if msgid is not None:
                json_obj["msgid"] = msgid
            json.dump(json_obj, f)
            # MIME boundary
            f.write("\n\n--" + mb + "\n")
            # Headers for NDO content file
            f.write("Content-Type: %s\nMIME-Version: 1.0\n" % metadata.get_ctype())
            f.write("Content-Disposition: inline\n")
            f.write("Content-Length: %d\n\n" % ct_length)
            # Complete data to be returned consists of three parts
            # - data now in StringIO object
            # - data in content file
            # - final MIME boundary
            # Calculate total length to go in HTTP header and reset pointer in StringIO
            length = f.tell() + ct_length +len(final_mb)
            f.seek(0)
            
            # Now generate the top level HTTP headers
            self.send_response(200, "Returning content and metadata")
            self.send_header("MIME-Version", "1.0")
            self.send_header("Content-Type", "multipart/mixed; boundary=%s" % mb)
            self.send_header("Content-Disposition", "inline")
            self.send_header("Content-Length", str(length))
            # Ensure response not cached
            self.send_header("Expires", "Thu, 01-Jan-70 00:00:01 GMT")
            self.send_header("Last-Modified", str(metadata.get_timestamp()))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            # IE extensions - extra header
            self.send_header("Cache-Control", "post-check=0, pre-check=0")
            # This seems irrelevant to a response
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            # Copy the three chunks of data to the output stream
            self.send_string(f.getvalue())
            self.send_file(cf)
            self.send_string(final_mb)
            f.close()
            return None
        else:
            # No content so just send the metadata as an application/json object
            f = StringIO()
            # Add the locator of this node to the locator list in the summary
            json_obj = metadata.summary(self.authority)
            json_obj["status"] = 203
            if msgid is not None:
                json_obj["msgid"] = msgid
            json.dump(json_obj, f)
            length = f.tell()
            f.seek(0)
            
            # Now generate the top level HTTP headers
            self.send_response(200, "Returning metadata only")
            self.send_header("MIME-Version", "1.0")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", "inline")
            self.send_header("Content-Length", str(length))
            # Ensure response not cached
            self.send_header("Expires", "Thu, 01-Jan-70 00:00:01 GMT")
            self.send_header("Last-Modified", metadata.get_timestamp())
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            # IE extensions - extra header
            self.send_header("Cache-Control", "post-check=0, pre-check=0")
            # This seems irrelevant to a response
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            return f
            
    #--------------------------------------------------------------------------#
    def send_meta_header(self, ni_name, metadata, content_file, msgid):
        """
        @brief Send HTTP headers and set up for sending metadata file for GET
        request access to an HTTP URL starting ni_meta.
        @param ni_name NIname instance  representing alg-name/digest received
                                        with HTTP GET request
        @param metadata NetInfMetadata instance holds metadata for ni_name
        @param content_file string pathname to content file if present or None
        @param msgid None (not used in this method)
        @return file object pointing to metadata file content as JSON string or
                     None
        
        On entry the incoming path has been parsed into the ni_meta prefix
        (which results in this method being called) and the alg-name and digest
        have been incorporated into a validated NIname instance (ni_name).
        The ni_name has been used to determine there is a cache entry for the
        ni_name.  The metadata for the entry and (if present) the file name
        of the content_file are passed in as parameters.

        Note: The ni_name, content_file and msgid are not used in this method 
        but the interface is common for various GET patterns that result in
        various send_xx_header methods called via the alg_digest_get_dict.

        The parameters are all nominally validated and the cache entry
        checked for existence and correctness.  All that is necessary is to
        generate the HTTP response.
        """
        assert(ni_name.url_validated())
        
        # Generate metadata JSON string in compact form
        metadata_str = json.dumps(metadata.json_val(), separators=(',',':'))
        # Find out how big it is and generate headers
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(metadata_str)))
        self.end_headers()
        self.send_string(metadata_str)
        return None

    #--------------------------------------------------------------------------#
    def send_qrcode_header(self, ni_name, metadata, content_file, msgid):
        """
        @brief Send HTTP headers and set up for sending metadata file for GET
        request access to an HTTP URL starting ni_qrcode.
        @param ni_name NIname instance  representing alg-name/digest received
                                        with HTTP GET request
        @param metadata NetInfMetadata instance holds metadata for ni_name
        @param content_file string pathname to content file if present or None
        @param msgid None (not used in this method)
        @return file object pointing to StringIO containing image page with
                            embedded QRcode image data or None
        
        On entry the incoming path has been parsed into the ni_qrcode prefix
        (which results in this method being called) and the alg-name and digest
        have been incorporated into a validated NIname instance (ni_name).
        The ni_name has been used to determine there is a cache entry for the
        ni_name.  The metadata for the entry and (if present) the file name
        of the content_file are passed in as parameters.

        Note: The metadata, content_file and msgid are not used in this method
        but the interface is common for various GET patterns that result in
        various send_xx_header methods called via the alg_digest_get_dict.

        The parameters are all nominally validated and the cache entry
        checked for existence and correctness.  All that is necessary is to
        generate the HTTP response.
        """

        # Retrieve canonical form of ni: URI from ni_name
        try:
            ni_string = ni_name.get_canonical_ni_url()
        except Exception, e:
            self.logerror("Bad ni_name supplied to send_qrcode_header for %s: %s" %
                          ( self.path, str(e)))
            self.send_error(500, "Problem in send_qrcode_header")
            return None

        # Make a Base64urlencoded string of a png image of QR code
        f = StringIO()
        qrcode.make(ni_string).save(f)
        f.seek(0)
        qrstr = base64.b64encode(f.getvalue())
        f.seek(0)

        # Construct HTML document
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n')
        f.write("<html>\n<body>\n<title>NetInf QRcode Image</title>\n")
        f.write("<h1>NetInf QRcode Image for ni Scheme URI </h1>\n")
        f.write("<h2>URI: %s</h2>" % ni_string)
        f.write("\n<br/>\n<center>")

        f.write('<img src="data:image/png;base64,%s" alt="QRcode" />' % qrstr)
        f.write('</center>\n<</body></html>')
        file_len = f.tell()
        f.seek(0, os.SEEK_SET)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(file_len))
        self.send_header("Content-Disposition", "inline")
        self.end_headers()
        return f

    #--------------------------------------------------------------------------#
    def send_get_redirect(self, ni_name, metadata, content_file, msgid):
        """
        @brief Redirect HTTP GET requests for URL http//<netloc>/.well-known/ni...
        @param ni_name NIname object corresponding to .well-known URL
        @param metadata NetInfMetadata instance holds metadata for ni_name
        @param content_file string pathname to content file if present or None
        @param msgid None (not used in this method)
        @return None (only headers are sent for redirect)

        Send a Temporary Redirect (HTTP response code 307) when a GET request
        for an HTTP URL with a path starting /.well-known/ni[h]/ is received.

        This is done because .well-known URLs are not supposed to return large
        amounts of data.

        On entry the incoming path has been parsed into the .well_known prefix
        (which results in this method being called) and the alg-name and digest
        have been incorporated into a validated NIname instance (ni_name).
        The ni_name has been used to determine there is a cache entry for the
        ni_name.  The metadata for the entry and (if present) the file name
        of the content_file are passed in as parameters.

        Note: The metadata and content_file are not used in this method but
        the interface is common for various GET patterns that result in
        various send_xx_header methods called via the alg_digest_get_dict.

        The parameters are all nominally validated and the cache entry
        checked for existence and correctness.  All that is necessary is to
        generate the HTTP response.
        """
        # Get the digest in ni form (in case the path was nih)
        try:
            ni_digest = ni_name.trans_nih_to_ni()
        except Exception, e:
            self.logerror("Violated assumption in send_redirect_header for %s: %s" %
                          (ni_name.get_url(), str(e)))
            self.send_error(500, "NI URL not validated when processing .well_known")
            return
        
        self.send_response(307, "Redirect for .well-known version of '%s'" %
                           ni_name.get_url())
        self.send_header("Location", "http://%s%s%s;%s" % (self.authority,
                                                            self.CONT_PRF,
                                                            ni_name.get_alg_name(),
                                                            ni_digest))
        self.end_headers()
        
        return None

    #--------------------------------------------------------------------------#
    def do_POST(self):
        """
        @brief Process NetInf POST requests.
        @return None
        
        NetInf uses a set of forms POSTed to URLs to transmit NetInf
        messages on the HTTP convergence layer.
        The URLS are of the form
        http://<destination netloc>/netinfproto/<msg type>
        where <msg_type> is:
            For the basic NetInf protocol:
                'get', 'publish' (alias 'put'), 'search'
            Only if functioning as an NRS server:
                'nrsconf', 'nrslookup', 'nrsdelete', 'nrsvals'

        For the basic NetInf protocol, this routine processes the form data
        ready to do one of:
        - get: retrieve a Named Data Object (NDO) from the local cache,
        - publish: insert a (new) NDO into the local cache, or
        - search: Carry out a search and report NDOs that meet the search criteria.
          Currently, this search is carried out, not in the existing NDOs in the
          cache, but by using the OpenSearch interface to Wikipedia. The search
          criteria are passed to interface and the top ten results are accessed,
          turning them into new NDOs and reporting the NDOs to the searcher.

        If an NRS is being run, the form data is processed ready to do one of:
        - nrsconf: add a new entry in the NRS database with an ni name or locator as key
        - nrslookup: retrieve the NRS entry indexed by an ni name or locator key
        - nrsdelete: delete an NRS entry given the key
        - nrsvals: retrieve all the NRS entries with keys matching a pattern
       
        When an NDO is published at least the metadata is provided.
        The associated content may be published either at the same time or later.
        Also the metadata may be updated later. Internally, the program maintains a
        stack of changes made to the metadata which is summarized when the NDO is
        retrieved using a get operation and returned with the content if available.
        The metadata is stored as a JSON object in the metadata file and transferred
        in the protocol in this form.  The metadata is managed internally as an instance
        of the NetInfMetaData class.  There is a very close mapping between JSON
        objects and Python dictionaries. 

        The NRS database is held in a Redis database.  The values associated with a
        key (either a URI from the ni:scheme or a locator, for example a (part of)
        an HTTP scheme URI such as http://example.com or a (similar part of) a DTN
        scheme such as dtn://north.pole.  The values associated with the key are stored
        using the hash mechanism provided by Redis that allows values for multiple
        (sub-)keys to be stored efficiently indexed by each master key.  Currently
        the sub-keys used are for two locators (loc1, loc), two routing hints (hint1,
        hint2) and metadata (meta).

        Each request is handled by a specific processing routine.

        The paths derived from the HTTP PUBLISH requests should not have any
        fragment components (fragments are supposed to be used in the client
        and not sent to the server), and only the NetInf publish operation
        might need a query string (for optional content type specification).
        The paths are checked before being passed to the processing routines.
        
        """
        
        self.loginfo("start,req,%s,from,%s,path,%s" % (self.command,
                                                       self.client_address,
                                                       self.path))

        # Record presence or absence of query string and fragments
        has_query_string, has_fragments = \
                          self.check_path_for_query_and_fragments(self.path)

        # Of the POST URLs recognized by niserver, only the NetInf publish request
        # uses the query string, but none want fragments
        if has_fragments:
            self.loginfo("Received POST with unwanted fragment part: '%s'" %
                         self.path)
            self.send_error(400, "Fragment modifiers not allowed")
            return None
            
        # Only the NetInf publish/put POST URL recognized by niserver wants a
        # query string.
        if has_query_string and not (self.path.startswith(self.NETINF_PUBLISH) or
                                     self.path.startswith(self.NETINF_PUT)):
            self.loginfo("Received POST with unwanted query string: '%s'" %
                         self.path)
            self.send_error(400, "Query string not allowed")
            return None
        
        # The NetInf proto uses a very limited set of requests..
        if (self.path not in [ self.NETINF_GET, self.NETINF_SEARCH,
                               self.NRS_CONF,   self.NRS_LOOKUP,
                               self.NRS_DELETE, self.NRS_VALS ]) and \
                               not (self.path.startswith(self.NETINF_PUBLISH) or
                                    self.path.startswith(self.NETINF_PUT)):
            self.logdebug("Unrecognized POST request: %s" % self.path)
            self.send_error(404, "POST %s is not used by NetInf" % self.path)
            return
        
        # Parse the form data posted
        self.logdebug("Headers: %s" % str(self.headers))
        form = cgi.FieldStorage(
            fp=self.rfile, 
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })
        self.logdebug("POST Form parsed")
        
        # Call subsidiary routines to do the work
        if (self.path == self.NETINF_GET):
            self.netinf_get(form)
        elif (self.path.startswith(self.NETINF_PUBLISH) or
              self.path.startswith(self.NETINF_PUT)):
            self.netinf_publish(form)
        elif (self.path == self.NETINF_SEARCH):
            self.netinf_search(form)
        elif self.provide_nrs:
            if (self.path == self.NRS_CONF):
                self.nrs_conf(form)
            elif (self.path == self.NRS_LOOKUP):
                self.nrs_lookup(form)
            elif (self.path == self.NRS_DELETE):
                self.nrs_delete(form)
            elif (self.path == self.NRS_VALS):
                self.nrs_vals(form)
            else:
                # A value that isn't one of the above shouldn't have got past
                # previous checks
                raise ValueError("NRS path value is inappropriate")
        elif self.path in [ self.NRS_CONF, self.NRS_LOOKUP,
                            self.NRS_DELETE, self.NRS_VALS ]:
            self.logerror("NRS request '%s' sent to server not providing NRS" %
                          self.path)
            self.send_error(404, "NetInf server is not providing NRS services")
            return
        else:
            # ... as above
            raise ValueError("POST path value is inappropriate")

        return

    #--------------------------------------------------------------------------#
    def netinf_get(self, form):
        """
        @brief Process the decoded form sent with a POST NetInf get request
        @param form cgi.FieldStorage object with processed form data
        @return (none)

        The form sent with a NetInf get request to
        http://<netloc>/.well-known/netinfproto/get
        must contain the following fields:
        - URI:    the ni: name for the NDO to be retrieved
        - msgid:  an identifier used by the source to correlate replies

        It may optionally contain the following field:
        - ext:    placeholder for extension fields (no values currently defined)

        The routine
        - checks the relevant fields are present (and no more)
            - sends a 412 error if validation fails
        - turns the URI into a NIname instance and validates it
            - sends a 406 error if the validation fails
        - maps the ni: URI into a file name
            - sends a 404  error if the file does not exist
        - constructs headers and sends back the data (see do_GET).
        """
        # Validate form data
        # Check only expected keys and no more
        # NOTE: 'stage' is unused and is a hangover from testing - left in for consistency with PHP
        mandatory = ["URI", "msgid"]
        optional = ["ext", "stage"]
        form_ok, fov = self.check_form_data(form, mandatory, optional, "netinfproto/get")
        if not form_ok:
            return

        self.msgid = fov["msgid"]

        self.logdebug("/netinfproto/get: URI: '%s', msgid: '%s', 'ext': '%s'" %
                      (fov["URI"], fov["msgid"], fov["ext"]))

        # Generate NIname and validate it (it should have a Params field).
        ni_name = NIname(form["URI"].value)
        rv = ni_name.validate_ni_url()
        if rv is not ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni_errs_txt[rv])
            return

        # Get the cache entry for this ni_name (if any)
        try:
            metadata, content_file = self.cache.cache_get(ni_name)
        except NoCacheEntry:
            self.loginfo("Named Data Object not in cache: %s" % self.path)
            self.send_error(404, "Named Data Object not in cache")
            return None
        except Exception, e:
            self.logerror(str(e))
            self.send_error(500, str(e))
            return None
            
        self.loginfo("form_get,uri,%s,ctype,%s,size,%s" % (ni_name.get_canonical_ni_url(),
                                                           metadata.get_ctype(),
                                                           metadata.get_size()))

        # Record size for higher level logging
        self.req_size = int(metadata.get_size())

        # send_get_header returns open file pointer to file to be returned
        # (or None)
        f = self.send_get_header(ni_name, metadata, content_file,
                                 form["msgid"].value)
        if f:
            self.send_file(f)
        return

    #--------------------------------------------------------------------------#
    def netinf_publish(self, form):
        """
        @brief Process the decoded form sent with a POST NetInf publish request
        @param form cgi.FieldStorage object with processed form data
        @return (none)

        The form sent with a NetInf publish request to
        http://<netloc>/netinfproto/publish (or .../put)
        must contain at least the following fields:
        URI:    the ni: name for the NDO to be published
        msgid:  an identifier used by the source to correlate replies

        It may also contain
        - rform:  Value indicating the form of the response (html, json or plain)
        - fullPut:boolean value indicating if octets should be expected
        - octets: the file to be published (with a filename attribute)
        - ext:    placeholder for extension fields (only 'meta' defined at present)
        - loc1:   a location (FQDN) where the file might be found
        - loc2:   another location (FQDN) where the file might be found

        A request must contain either fullPut and the octets or, loc1 and/or
        loc2.  It may contain both types of information.

        There may also be a content type for the file in the query string
        part of the URI (path) in the form ?ct="<mimetype>".  Should be
        accessible from ni name structure. 

        The routine
        - checks the relevant fields are present (and no more)
            - sends a 412 error if validation fails
        - turns the URI into a NIname instance and validates it
            - sends a 406 error if the validation fails
        - maps the ni: URI into file names (for content and metadata)
            - if the content file already exists updates the metadata
            - if the metadata update succeeds send a 204 response(with the
              mod time here)
            - if the metadata update fails send a 401 error 
        - if fullPut is set saves the file using the filetype and creating the file
          with the digest name; updates/creates the metadata file
            - sends a 401 error if either of the files cannot be written
        - sends a publish report with HTTP response 200-OK if caching succeeded
        """
        # Validate form data
        # Check only expected keys and no more
        mandatory = ["URI",  "msgid"]
        optional = ["ext", "loc2", "fullPut", "octets", "loc1", "rform"]
        form_ok, fov = self.check_form_data(form, mandatory, optional, self.path)
        if not form_ok:
            return

        self.msgid = fov["msgid"]

        # Record timestamp for this operation
        timestamp = self.metadata_timestamp_for_now()
        
        self.logdebug("NetInf publish for "
                      "URI %s, fullPut %s octets %s, msgid %s, rform %s, ext %s,"
                      "loc1 %s, loc2 %s at %s" % (form["URI"].value,
                                                  fov["fullPut"],
                                                  fov["octets"],
                                                  form["msgid"].value,
                                                  fov["rform"],
                                                  fov["ext"],
                                                  fov["loc1"],
                                                  fov["loc2"],
                                                  timestamp))
        
        # Convert textual fullPut value to boolean
        if "fullPut" in form.keys():
            fp_val = form["fullPut"].value.lower()
            self.logdebug("fullPut: %s" % fp_val)
            if fp_val in ["true", "yes", "on", "1"]:
                full_put = True
            else:
                full_put = False
                if not (fp_val in ["false", "no", "off", "0"]):
                    self.logwarn("fullPut has value '%s'which is not a good boolean representation." % fp_val)
        else:
            full_put = False

        # If fullPut is supplied and equivalent to True then
        # there must be an octets option which references a file
        file_uploaded = False
        if full_put:
            if not "octets" in form.keys():
                self.loginfo("Expected 'octets' form field to be present with 'fullPut' set")
                self.send_error(412, "Form field 'octets' not present when 'fullPut' set.")
                return
            if form["octets"].filename is None:
                self.loginfo("Expected 'octets' form field to be a file but has no filename attribute")
                self.send_error(412, "Form field 'octets' does not contain an uploaded file")
                return
            # Record that there is a file ready
            file_uploaded = True
            fov["octets"] = form["octets"].filename            
        elif "octets" in form.keys():
            self.logwarn("Unexpected 'octets' form field present with 'fullPut' is not set")

        # Extract extra metadata if present
        # The metadata is to be held in a JSON object labelled "meta" in the "ext"
        # form field.  The following code extracts this object which is represented
        # by a Python dictionary, checking that it is a dictionary (object) in case
        # the user has supplied a garbled piece of JSON.
        extrameta = {}
        extrameta["publish"] = self.PUBLISH_REF
        if "ext" in form.keys():
            ext_str = form["ext"].value
            if ext_str != "":
                try:
                    ext_json = json.loads(ext_str)
                    if "meta" in ext_json.keys():
                        extrameta = ext_json["meta"]
                        if type(extrameta) is not dict:
                            self.loginfo("Value of 'meta' item in JSON form field "
                                         "'ext' '%s' is not a JSON object." % str(extrameta))
                            self.send_error(412, "'meta' item in form field 'ext' "
                                                 "is not a JSON object")
                            return                        
                        self.logdebug("Metadata: %s" % json.dumps(extrameta))
                except Exception, e:
                    self.loginfo("Value of form field 'ext' '%s' is not a valid JSON string." %
                                 ext_str)
                    self.send_error(412, "Form field 'ext' does not contain a valid JSON string")
                    return

        # Check that the response type is one we expect - default is JSON if not explicitly requested
        if "rform" in form.keys():
            rform = fov["rform"].lower()
            if not((rform == "json") or (rform == "html") or (rform == "plain")):
                self.loginfo("Unhandled publish response format requested '%s'." % rform)
                self.send_error(412, "Response format '%s' not available." % rform)
                return
        else:
            # Default of json
            rform = "json"
            self.logdebug("Using default rform - json")                
        
        # Extract the locators from the form
        (loc1, loc2) = self.form_to_locs(form)
        
        # Generate NIname and validate it (it should have a Params field).
        ni_name = NIname(form["URI"].value)
        rv = ni_name.validate_ni_url(has_params=True)
        if rv is not ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni_errs_txt[rv])
            return

        # Retrieve netloc and query string (if any) 
        netloc = ni_name.get_netloc()
        qs = ni_name.get_query_string()

        # We don't know what the content type or the length are yet
        ctype = None
        file_len = -1

        # If the form data contains an uploaded file...
        temp_name = None
        if file_uploaded:
            # Copy the file from the network to a temporary name in the right
            # subdirectory of the storage_root.  This makes it trivial to rename it
            # once the digest has been verified.
            temp_fd, temp_name = self.cache.cache_mktemp()
            # Convert file descriptor to file object
            f = os.fdopen(temp_fd, "w")

            self.logdebug("Copying and digesting to temporary file %s" %
                          temp_name)

            # Prepare hashing mechanisms
            hash_function = ni_name.get_hash_function()()

            # Copy file from incoming stream and generate digest
            file_len = 0
            g = form["octets"].file
            while True:
                buf = g.read(16 * 1024)
                if not buf:
                    break
                f.write(buf)
                hash_function.update(buf)
                file_len += len(buf)
            f.close()

            # Record for logging at higher level
            self.req_size = file_len
            self.logdebug("Finished copying")

            # Check the file was completely sent (not interrupted or cancelled by user
            if form["octets"].done == -1:
                self.loginfo("File referenced by 'octets' form field incompletely uploaded")
                self.send_error(412, "Upload of file referenced by 'octets' form field cancelled or interrupted by user")
                return
         
            # Get binary digest and convert to urlsafe base64 or hex
            # encoding depending on URI scheme
            bin_dgst = hash_function.digest()
            if (len(bin_dgst) != ni_name.get_digest_length()):
                self.logerror("Binary digest has unexpected length")
                self.send_error(500, "Calculated binary digest has wrong length")
                os.remove(temp_name)
                return
            if ni_name.get_scheme() == "ni":
                digest = NIproc.make_b64_urldigest(bin_dgst[:ni_name.get_truncated_length()])
                if digest is None:
                    self.logerror("Failed to create urlsafe base64 encoded digest")
                    self.send_error(500, "Failed to create urlsafe base64 encoded digest")
                    os.remove(temp_name)
                    return
            else:
                digest = NIproc.make_human_digest(bin_dgst[:ni_name.get_truncated_length()])
                if digest is None:
                    self.logerror("Failed to create human readable encoded digest")
                    self.send_error(500, "Failed to create human readable encoded digest")
                    os.remove(temp_name)
                    return

            # Check digest matches with digest in ni name in URI field
            if (digest != ni_name.get_digest()):
                self.logwarn("Digest calculated from incoming file does not match digest in URI: %s" % form["URI"].value)
                self.send_error(401, "Digest of incoming file does not match digest in URI: %s" % form["URI"].value)
                os.remove(temp_name)
                return

            # Work out content type for received file
            ctype = form["octets"].type

            if ((ctype is None) or (ctype == self.DFLT_MIME_TYPE)):
                ctype = magic.from_file(temp_name, mime=True)
                self.logdebug("Guessed content type from file is %s" % ctype)
            else:
                self.logdebug("Supplied content type from form is %s" % ctype)

        # If ct= query string supplied in URL field..
        #   Override type got via received file if there was one but log warning if different
        if not (qs == ""):
            ct = re.search(r'ct=([^&]+)', qs)
            if not (ct is  None or ct.group(1) == ""):
                if not (ctype is None or ctype == ct.group(1)):
                    self.logwarn("Inconsistent content types detected: %s and %s" % \
                                 (ctype, ct.group(1)))
                ctype = ct.group(1)

        # Set the default content type if we haven't been able to set it so far but have got a file
        # If we haven't got a file then we just leave it unassigned
        if ctype is None and file_uploaded:
            # Default..
            ctype = self.DFLT_MIME_TYPE
        
            
        # Do initial store or update of metadata and add content file if
        # available and needed
        canonical_url = ni_name.get_canonical_ni_url()
        # Create metadata instance for current information
        md = NetInfMetaData(canonical_url, timestamp, ctype, file_len,
                            loc1, loc2, extrameta)

        try:
            md_out, cfn, new_entry, ignore_upload = \
                            self.cache.cache_put(ni_name, md, temp_name)
        except Exception, e:
            self.send_error(500, str(e))
            return
        ndo_in_cache = (cfn is not None)

        # Generate publish report
        self.send_publish_report(rform, ndo_in_cache, ignore_upload,
                                 new_entry, form, md_out, ni_name.get_url())

        return

    #--------------------------------------------------------------------------#
    def netinf_search(self, form):
        """
        @brief Process the decoded form sent with a POST NetInf publish request
        @param form cgi.FieldStorage object with processed form data
        @return (none)

        The form sent with a NetInf publish request to
        http://<netloc>/netinfproto/search
        must contain at least the following fields:
        - tokens: the search query
        - msgid:  an identifier used by the source to correlate replies

        It may also contain
        - rform:  Value indicating the form of the response (html, json or plain)
        - ext:    placeholder for extension fields (only 'meta' defined at present)

        The search that is implemented currently sends the tokens string to the
        OpenSearch interface for Wikipedia, asking for the response in the
        SearchSuggestion2 XML format with up to 10 items flagged.

        The response (if any) is parsed and the items returned processed.

        The Url, Text and Description fields are extracted.  An HTTP GET request
        is sent for the (Wikipedia) entry referenced by the Url and the result (if
        one is returned) saved, a digest using the sha-256 algorithm calculated,
        the data cached as an NDO using the digest as name. The corresponding
        metadata is constructed including a 'search' element in the 'metadata'
        object in 'details' (see NetInfMetaData class for more information) and the
        Wikipedia Url as a locator.
        
        If the requested response format is HTML:
        An HTML results report document is then built consisting of a list of items
        referring to the successfully retrieved flagged items with:
        - the ni name as a hyperlink with the http:///ni_cache URL as address
        - a hyperlink named 'meta' with the http:///ni_meta URL as address
        - a hyperlink named 'QRcode' with the http:///ni_qrcode URL as address
        - a block containing
           - the Text field from the Wikipedia response
           - the Description field from the Wikipedia response

        If the requested format is plain text:
        An equivalent report written in plain text

        If the requested format is JSON:
        A JSON object containing 'NetInf', 'status', 'msgid', 'ts', and
        'search' fields and a 'results' firld with an array of the ni URIs
        of thecached results. 
        """
        # Validate form data
        # Check only expected keys and no more
        mandatory = ["tokens",  "msgid"]
        # stage is left over from earlier versions - left in for consistency
        optional = ["ext", "rform", "stage"]
        form_ok, fov = self.check_form_data(form, mandatory, optional,
                                            "netinfproto/search")
        if not form_ok:
            return

        self.msgid = fov["msgid"]

        # Check that the response type is one we expect - default is JSON if not explicitly requested
        if "rform" in form.keys():
            rform = fov["rform"].lower()
            if not((rform == "json") or (rform == "html") or (rform == "plain")):
                self.loginfo("Unhandled search response format requested '%s'." % rform)
                self.send_error(412, "Response format '%s' not available." % rform)
                return
        else:
            # Default of json
            rform = "json"
            self.logdebug("Using default rform - json")                
        
        # Record timestamp for this operation
        op_timestamp = self.metadata_timestamp_for_now()

        self.logdebug("NetInf search for "
                      "tokens %s, msgid %s, rform %s, ext %s at %s" % (form["tokens"].value,
                                                                       form["msgid"].value,
                                                                       fov["rform"],
                                                                       fov["ext"],
                                                                       op_timestamp))

        # Formulate request for Wikipedia
        tokens = form["tokens"].value
        self.logdebug("Search token string: |%s|" % tokens)
        if tokens == "":
            self.logwarn("Empty search token string received.")
            self.send_error(418, "Empty search token string received.")
            return
            
        wikireq=self.WIKI_SRCH_API % (self.WIKI_LOC, urllib.quote(tokens, safe=""))    

        # Send GET request to Wikipedia server
        try:
            http_object = urllib2.urlopen(wikireq)
        except Exception, e:
            self.logwarn("Error: Unable to access Wikipedia URL %s: %s" % (wikireq, str(e)))
            self.send_error(404, "Unable to access Wikipedia URL: %s" % str(e))
            return

        # Get HTTP result code
        http_result = http_object.getcode()

        # Get message headers - an instance of email.Message
        http_info = http_object.info()
        self.logdebug("Response type: %s" % http_info.gettype())
        self.logdebug("Response info:\n%s" % http_info)

        obj_length_str = http_info.getheader("Content-Length")
        if (obj_length_str != None):
            obj_length = int(obj_length_str)
        else:
            obj_length = None

        # Read results into buffer
        # Would be good to try and do this better...
        # if the object is large we will run into problems here
        payload = http_object.read()
        http_object.close()
        self.logdebug("Wikipedia: result string: %s" % payload)

        # The results are expected to be a single object with MIME type text/xml

        # Verify length and digest if HTTP result code was 200 - Success
        if (http_result != 200):
                self.logwarn("Wikipedia request returned HTTP code %d" % http_result)
                self.send_error(http_result, "Wikipedia non-success response")
                return

        if ((obj_length != None) and (len(payload) != obj_length)):
            self.logwarn("Warning: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))

        # Check returned results are in appropriate form
        ct = http_info.getheader("Content-Type").lower()
        if not ct.startswith("text/xml"):
            self.logerror("Wikipedia returned document that was of type '%s' rather than 'text/xml'" %
                          ct)
            self.send_error(415, "Wikipedia returned results in a form '%s' other than 'text/xml'" % ct)
            return

        # Try to decode results - expect that there should be an array of up to ten result 'Item'
        # elements inside a 'Section' element.  Extract text part of 'Url' (where to get document),
        # 'Text' (matched text in item) and 'Description' (header of article).
        # The results should be a single root element specifying almost everything to be in the
        # XML namespace 'http://opensearch.org/searchsuggest2'
        try:
            root = ET.fromstring(payload)
        except Exception, e:
            self.logerror("Unable to parse returned Wikipedia document as XML element: %s" % str(e))
            self.send_error(422, "Unable to parse returned Wikpaedia document: %s" % str(e))
            return

        # Set up qualified names for elements we are interested in
        section_name = str(ET.QName(self.SRCH_NAMESPACE, "Section"))
        item_name    = str(ET.QName(self.SRCH_NAMESPACE, "Item"))
        url_name     = str(ET.QName(self.SRCH_NAMESPACE, "Url"))
        text_name    = str(ET.QName(self.SRCH_NAMESPACE, "Text"))
        desc_name    = str(ET.QName(self.SRCH_NAMESPACE, "Description"))

        # Extract interesting parts of results - these are bodies (.text value) of
        # Url, Text and Description elements
        results = []
        try:
            if hasattr(root, "iter"):
                for sect in root.iter(tag=section_name):
                    for item in sect.iter(tag=item_name):
                        r = {}
                        r["url"] = item.find(url_name).text
                        r["text"] = item.find(text_name).text.encode('ascii','replace')
                        r["desc"] = item.find(desc_name).text.encode('ascii','replace')
                        results.append(r)
            else:
                # Python 2.6/ElementTree 1.2
                for sect in root.getiterator(tag=section_name):
                    for item in sect.getiterator(tag=item_name):
                        r = {}
                        r["url"] = item.find(url_name).text
                        r["text"] = item.find(text_name).text.encode('ascii','replace')
                        r["desc"] = item.find(desc_name).text.encode('ascii','replace')
                        results.append(r)
                
        except Exception, e:
            self.logerror("Extraction of elements from Wikipedia results failed: %s" % str(e))
            self.send_error(422, "Extraction of elements from Wikipedia results failed: %s" % str(e))
            return

        # Record the tokens for placing in the metadata of items found as a result
        srch_dict = {}
        srch_dict["searcher"] = self.SEARCH_REF
        srch_dict["engine"]   = self.WIKI_LOC
        srch_dict["tokens"]   = tokens
        extrameta = { "search": srch_dict }

        # Retrieve the results and cache them
        # If retrieval fails discard the result
        cached_results = []
        for item in results:
            # Construct a template canonicalized ni name for this result
            # => No authority; No query string
            ni_name = NIname((self.SRCH_CACHE_SCHM, "", self.SRCH_CACHE_DGST))
            # The validation should be a formality but has to be done
            # otherwise can't get hash function...
            rv = ni_name.validate_ni_url(has_params = False)
            if rv != ni_errs.niSUCCESS:
                self.logerror("Validation of ni_name failed after setting digest: %s" %
                              ni_errs_txt[rv])
                continue

            # Record timestamp for this get operation
            timestamp = self.metadata_timestamp_for_now()

            # Access the item and get the data - this might be a bit slow.. live with it for now
            url = item["url"]
            try:
                http_req = urllib2.Request(url, headers={'User-Agent' : "NetInf Browser"})
                http_object = urllib2.urlopen(http_req)
            except Exception, e:
                self.logwarn("Warning: Unable to access results URL %s - ignoring: %s" %
                             (url, str(e)))
                continue

            http_info = http_object.info()

            self.logdebug("Response type: %s" % http_info.gettype())
            self.logdebug("Response info:\n%s" % http_info)

            # Verify access was successful and ignore result if not
            if (http_result != 200):
                    self.logwarn("Result access request returned HTTP code %d - ignoring result" % http_result)
                    # Flush any octets that came with the failed request and close the http request object
                    payload = http_object.read()
                    http_object.close()
                    continue

            # Get content type for received object
            ctype = http_info.gettype()

            # Get content length for received object
            obj_length_str = http_info.getheader("Content-Length")
            if (obj_length_str != None):
                obj_length = int(obj_length_str)
            else:
                obj_length = None

            # The results are expected to be a single object with MIME as announced in headers

            # Copy the file from the network to a temporary name in the right
            # subdirectory of the storage_root.  This makes it trivial to rename it
            # once the digest has been verified.
            # This file name is unique to this thread and because it has # in it
            # should never conflict with a digested file name which doesn't use #.
            temp_fd, temp_name = self.cache.cache_mktemp()
            # Convert file descriptor to file object
            f = os.fdopen(temp_fd, "w")
            
            self.logdebug("Copying and digesting to temporary file %s" % temp_name)

            # Prepare hashing mechanisms
            hash_function = ni_name.get_hash_function()()

            # Copy file from incoming stream and generate digest
            try:
                f = open(temp_name, "wb");
            except Exception, e:
                self.logerror("Failed to open temp file %s for writing: %s)" % (temp_name, str(e)))
                continue
            file_len = 0
            try:
                while 1:
                    buf = http_object.read(16 * 1024)
                    if not buf:
                        break
                    f.write(buf)
                    hash_function.update(buf)
                    file_len += len(buf)
            except Exception, e:
                self.logerror("Error while reading returned data for URL '%s' - ignoring result: %s" %
                              (url, str(e)))
                f.close()
                http_object.close()
                continue
            f.close()
            http_object.close()
            self.logdebug("Finished copying")

            # Check length read and length in HTTP header, if any, match
            # (warning only if they don't)
            if not ((obj_length is None) or (file_len == obj_length)):
                self.logwarn(("Warning: Length of data read from network (%d) does not match " + \
                              "length in HTTP header (%d) for URL '%s'") % (read_length, obj_length,
                                                                            url))
         
            # Get binary digest and convert to urlsafe base64 or
            # hex encoding depending on URI scheme
            bin_dgst = hash_function.digest()
            if (len(bin_dgst) != ni_name.get_digest_length()):
                self.logerror("Binary digest for '%s' has unexpected length" % url)
                os.remove(temp_name)
                continue
            if ni_name.get_scheme() == "ni":
                digest = NIproc.make_b64_urldigest(bin_dgst[:ni_name.get_truncated_length()])
                if digest is None:
                    self.logerror("Failed to create urlsafe base64 encoded digest for URL '%s'")
                    os.remove(temp_name)
                    continue
            else:
                digest = NIproc.make_human_digest(bin_dgst[:ni_name.get_truncated_length()])
                if digest is None:
                    self.logerror("Failed to create human readable encoded digest for URL '%s'")
                    os.remove(temp_name)
                    continue

            # Guess the content type if the header didn't say
            if ((ctype is None) or (ctype == "") or(ctype == self.DFLT_MIME_TYPE)):
                ctype = magic.from_file(temp_name, mime=True)
                self.logdebug("Guessed content type from file for URL '%s' is %s" %
                              (url, ctype))
            else:
                self.logdebug("Supplied content type from HTTP header for URL '%s' is %s" %
                              (url, ctype))

            # Synthesize the ni URL name for the URL
            ni_name.set_params(digest)
            # The validation should be a formality...
            rv = ni_name.validate_ni_url(has_params = True)
            if rv != ni_errs.niSUCCESS:
                self.logerror("Validation of ni_name failed after setting digest: %s" %
                              ni_errs_txt[rv])
                continue

            # Do initial store or update of metadata and add content file if
            # available and needed
            canonical_url = ni_name.get_canonical_ni_url()
            # Create metadata instance for current information
            md = NetInfMetaData(canonical_url, timestamp, ctype, file_len,
                                url, None, extrameta)

            try:
                md_out, cfn, new_entry, ignore_upload = \
                                self.cache.cache_put(ni_name, md, temp_name)
            except Exception, e:
                self.send_error(500, str(e))
                return
            ndo_in_cache = (cfn is not None)
                
            # FINALLY... record cached item ready to generate response
            item["ni_obj"]    = ni_name
            item["metadata"]  = md_out
            cached_results.append(item)
            self.logdebug("Successfully cached URL '%s' as '%s'" % (url, ni_name.get_url()))

        self.loginfo("search,tokens,%s,results,%d" % (tokens,
                                                      len(cached_results)))
            
        # Construct response
        f = StringIO()
        # Select response format
        if rform == "json":
            # JSON format: add basic items         
            ct = "application/json"
            rd = {}
            rd["NetInf"] = NETINF_VER
            rd["status"]  = 200
            rd["msgid"] = form["msgid"].value
            rd["ts"] = op_timestamp
            rd["search"] = srch_dict

            # Iterate through cached results
            sr_list = []
            for item in cached_results:
                sr_list.append( { "ni" : item["ni_obj"].get_url() } )
            rd["results"] = sr_list
            
            json.dump(rd, f)
            
        elif rform == "plain":
            # Textual form report (useful for publish command line applications)
            ct = "text/plain"
            f.write("=== NetInf Search Results ===\n")
            f.write("Search query: |%s|\n\n" % tokens)

            # Iterate through cached results outputting link and information
            for item in cached_results:
                ni_name = item["ni_obj"]
                ni_name.set_netloc(self.authority)
                cl = "http://%s%s%s/%s/%s" % (self.authority,
                                              self.WKN,
                                              ni_name.get_scheme(),
                                              ni_name.get_alg_name(),
                                              ni_name.get_digest())
                ml = "http://%s%s%s;%s" % (self.authority,
                                             self.META_PRF,
                                             ni_name.get_alg_name(),
                                             ni_name.get_digest())
                ql = "http://%s%s%s;%s" % (self.authority,
                                             self.QRCODE_PRF,
                                             ni_name.get_alg_name(),
                                             ni_name.get_digest())
                f.write("Title: %s\n" % item["text"])
                f.write("  NI:     %s\n" % ni_name.get_url())
                f.write("  HTTP:   %s\n" % cl)
                f.write("  META:   %s\n" % ml)
                f.write("  QRCODE: %s\n" % ql)
                f.write("    Description:\n")
                f.write(textwrap.fill(item["desc"], width=80,
                                      initial_indent="        ",
                                      subsequent_indent="        "))
                f.write("\n\n")

        elif rform == "html":
            # HTML formatted report intended to be outputted by web browsers
            # Output header
            ct = "text/html"
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n')
            f.write("<html>\n<body>\n<title>NetInf Search Results</title>\n")
            f.write("<h1>NetInf Search Results</h1>\n")
            f.write("<h2>Search query: |%s|</h2>" % tokens)
            f.write("\n<br/>\n<ul>\n")

            # Iterate through cached results outputting link and information
            for item in cached_results:
                f.write("<li>\n")
                ni_name = item["ni_obj"]
                ni_name.set_netloc(self.authority)
                cl = "http://%s%s%s/%s/%s" % (self.authority,
                                              self.WKN,
                                              ni_name.get_scheme(),
                                              ni_name.get_alg_name(),
                                              ni_name.get_digest())
                ml = "http://%s%s%s;%s" % (self.authority,
                                             self.META_PRF,
                                             ni_name.get_alg_name(),
                                             ni_name.get_digest())
                ql = "http://%s%s%s;%s" % (self.authority,
                                             self.QRCODE_PRF,
                                             ni_name.get_alg_name(),
                                             ni_name.get_digest())
                f.write('<a href="%s">%s</a> ' % (cl, ni_name.get_url()))
                f.write('(<a href="%s">meta</a>)\n' % ml)
                f.write('(<a href="%s">QRcode</a>)\n' % ql)
                f.write("<blockquote>\n<b>%s</b>\n<br/>\n" % item["text"])
                f.write("%s\n</blockquote>\n" % item["desc"])
                f.write("</li>\n")
                    
            f.write("</ul>\n<br/>\n<t>Generated at %s</t>" % self.date_time_string())
            f.write("\n</body>\n</html>\n")
                
        length = f.tell()
        f.seek(0)
        
        self.send_response(200, "Search for |%s| successful" % tokens)
        self.send_header("MIME-Version", "1.0")
        self.send_header("Content-Type", ct)
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
        self.send_header("Last-Modified", self.date_time_string())
        self.end_headers()
        self.send_string(f.getvalue())
        f.close

        return
        
    #--------------------------------------------------------------------------#
    def nrs_conf(self, form):
        """
        @brief Process the decoded form sent with a POST NRS nrsconf request
        @param form cgi.FieldStorage object with processed form data
        @return (none)

        The form sent with a NRS entry create/update request to
        http://<netloc>/netinfproto/nrsconf
        must contain at least the following fields:
        - URI: key for the entry - either an ni: scheme URI or locator of any kind

        It may also contain
        - hint1:    routing hint #1
        - hint2:    routing hint #2
        - loc1:     locator #1
        - loc2:     locator #2
        - meta:     metadata

        Create or update a Redis database entry keyed by the URI.
        Set hash keys for the optional fields to the supplied values, replacing
        any previously supplied values.

        Send a response consisting of a JSON string representing the currently
        stored entry (post-update) for the URI key.
        """

        # Validate form data
        # Check only expected keys and no more
        mandatory = ["URI"]
        optional = ["hint1", "hint2", "loc1", "loc2", "meta"]
        form_ok, fov =  self.check_form_data(form, mandatory, optional, "nrsconf")
        if not form_ok:
            return

        # Make Redis entry
        redis_key = fov["URI"]
        redis_vals = {}
        for field in optional:
            if field in form.keys():
                redis_vals[field] = fov[field]
        # Check there were some fields non-empty
        if len(redis_vals.keys()) == 0:
            self.logerror("No values given when entering key '%s' in Redis" % redis_key)
            self.send_error(412, "Must have at least one value field non-empty")
            return

        # Do the database entry
        try:
            if not self.nrs_redis.hmset(redis_key, redis_vals):
                self.logerror("Failed to update Redis entry for '%s' - vals |%s|" %
                              (redis_key, str(redis_vals)))
                self.send_error(412, "Unable to update NRS database entry")
                return
        except Exception, e:
            self.logerror("Updating Redis entry for '%s' caused exception %s - vals |%s|" %
                          (redis_key, str(e), str(redis_vals)))
            self.send_error(412, "Updating NRS database entry caused exception: %s" % str(e))
            return
        
        # Written successfully - send response
        val_dict = self.read_nrs_entry(redis_key, optional)
        if val_dict is None:
            
            self.logerror("Reading Redis entry for '%s' failed" % redis_key)
            self.send_error(412, "Reading NRS database entry failed")
            return

        self.loginfo("nrs_put,key,%s,value,%s" % (redis_key, redis_vals))

        # Generate successful response output
        f = StringIO()
        f.write(json.dumps(val_dict))
        length = f.tell()
        f.seek(0)
        
        self.send_response(200, "NRS Entry for '%s' successful" % redis_key)
        self.send_header("MIME-Version", "1.0")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
        self.send_header("Last-Modified", self.date_time_string())
        self.end_headers()
        self.send_string(f.getvalue())
        f.close
          
        return

    #--------------------------------------------------------------------------#
    def nrs_lookup(self, form):
        """
        @brief Process the decoded form sent with a POST NRS nrslookup request
        @param form cgi.FieldStorage object with processed form data
        @return (none)

        The form sent with a NRS entry create/update request to
        http://<netloc>/netinfproto/nrsconf
        must contain just the following field:
        - URI: key for the entry - either an ni: scheme URI or locator of any kind

        Lookup a Redis database entry if any) keyed by the URI.
        It is expected to contain a subset of the following hash keys with values:
        - hint1:    routing hint #1
        - hint2:    routing hint #2
        - loc1:     locator #1
        - loc2:     locator #2
        - meta:     metadata

        If there is an entry corresponding to the key, send a response consisting
        of a JSON string representing the currently stored entry for the URI key.
        """
        # Validate form data
        # Check only expected keys and no more
        mandatory = ["URI"]
        optional = []
        expected = ["hint1", "hint2", "loc1", "loc2", "meta"]
        form_ok, fov = self.check_form_data(form, mandatory, optional, "nrslookup")
        if not form_ok:
            return

        # Lookup up URI value
        redis_key = fov["URI"]
        val_dict = self.read_nrs_entry(redis_key, expected)
        if val_dict is None:
            
            self.loginfo("No Redis entry for '%s' looked up" % redis_key)
            self.send_error(404, "No entry for key '%s'" % redis_key)
            return

        # Generate successful response output
        f = StringIO()
        f.write(json.dumps(val_dict))
        length = f.tell()
        f.seek(0)
        
        self.loginfo("nrs_get,key,%s,value,%s" % (redis_key, f.getvalue()))

        self.send_response(200, "NRS Entry lookup for '%s' successful" % redis_key)
        self.send_header("MIME-Version", "1.0")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
        self.send_header("Last-Modified", self.date_time_string())
        self.end_headers()
        self.send_string(f.getvalue())
        f.close
          
        return

    #--------------------------------------------------------------------------#
    def nrs_delete(self, form):
        """
        @brief Process the decoded form sent with a POST NRS nrsdelete request
        @param form cgi.FieldStorage object with processed form data
        @return (none)

        The form sent with a NRS entry create/update request to
        http://<netloc>/netinfproto/nrsdelete
        must contain just the following field:
        - URI: key for the entry - either an ni: scheme URI or locator of any kind

        Lookup a Redis database entry if any) keyed by the URI.
        It is expected to contain a subset of the following hash keys with values:
        - hint1:    routing hint #1
        - hint2:    routing hint #2
        - loc1:     locator #1
        - loc2:     locator #2
        - meta:     metadata

        If there is an entry recover the data corresponding to the key before
        deleting the entry. Then send a response documenting the deletion, if it
        succeeded, or otherwise, if it failed.
        """

        # Validate form data
        # Check only expected keys and no more
        mandatory = ["URI"]
        optional = []
        expected = ["hint1", "hint2", "loc1", "loc2", "meta"]
        form_ok, fov = self.check_form_data(form, mandatory, optional, "nrsdelete")
        if not form_ok:
            return

        # Lookup up URI value
        redis_key = fov["URI"]
        val_dict = self.read_nrs_entry(redis_key, expected)
        if val_dict is None:            
            self.loginfo("No Redis entry for '%s' to be deleted" % redis_key)
            self.send_error(404, "No entry for key '%s'" % redis_key)
            return

        try:
            if not self.nrs_redis.delete(redis_key):
                self.loginfo("Deleting Redis entry for '%s' failed" % redis_key)
                self.send_error(404, "Deleting entry for key '%s' failed" % redis_key)
                return
        except Exception, e:
            self.logerror("Deleting Redis key '%s' caused exception %s" %
                          (redis_key, str(e)))
            self.send_error(412, "Deleting key in NRS database caused exception: %s" %
                            str(e))
            return

        self.loginfo("nrs_delete,key,%s" % redis_key)

        # Generate successful response output
        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n')
        f.write("<html>\n<body>\n<title>NetInf NRS Deletion Report</title>\n")
        f.write("<h2>NetInf NRS Deletion Report</h2>\n")
        f.write("\n<p>Item with NI name or authority '%s' deleted.</p>" % redis_key)
        f.write("\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        
        self.send_response(200, "NRS Entry lookup for '%s' successful" % redis_key)
        self.send_header("MIME-Version", "1.0")
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
        self.send_header("Last-Modified", self.date_time_string())
        self.end_headers()
        self.send_string(f.getvalue())
        f.close
          
        return

    #--------------------------------------------------------------------------#
    def nrs_vals(self, form):
        """
        @brief Process the decoded form sent with a POST NRS nrsvals request
        @param form cgi.FieldStorage object with processed form data
        @return (none)

        The form sent with a NRS entry create/update request to
        http://<netloc>/netinfproto/nrsconf
        may contain just the following optional field:
        - pattern: a string acceptable as a parameter to the Redis keys API function.

        See the Redis documentation for acceptable patterns.

        If the pattern is missing, default to using the wildcard "*" pattern.

        Lookup all Redis entries with keys matching the pattern.
        It is expected each will contain a subset of the following hash keys
        with values:
        - hint1:    routing hint #1
        - hint2:    routing hint #2
        - loc1:     locator #1
        - loc2:     locator #2
        - meta:     metadata

        Construct a response as a JSON object containing two main fields:
        - pattern:  The pattern used for the key matching
        - results:  An array of JSON objects in the format of the
                    return from the nrslookup form. 
        """

        # Validate form data
        # Check only expected keys and no more
        mandatory = []
        optional = ["pattern"]
        expected = ["hint1", "hint2", "loc1", "loc2", "meta"]
        form_ok, fov = self.check_form_data(form, mandatory, optional, "nrsvals")
        if not form_ok:
            return

        # Set up pattern 
        if "pattern" not in form.keys():
            redis_patt = "*"
        else:
            redis_patt = fov["pattern"]

        # Find keys matching pattern
        try:
            key_list = self.nrs_redis.keys(redis_patt)
        except Exception, e:
            self.logerror("Reading Redis keys for pattern '%s' caused exception %s" %
                          (redis_patt, str(e)))
            self.send_error(412, "Reading key list in NRS database caused exception: %s" %
                            str(e))
            return

        # Make a dictionary with all keys
        results = {}
        for redis_key in key_list:
            val_dict = self.read_nrs_entry(redis_key, expected)
            if val_dict is not None:
                results[redis_key] = val_dict

        response = {}
        response["pattern"] = redis_patt
        response["results"] = results

        self.loginfo("nrs_vals,pattern,%s,num_results,%d" % (redis_patt,
                                                             len(results)))

        # Generate successful response output
        f = StringIO()
        f.write(json.dumps(response))
        length = f.tell()
        f.seek(0)
        
        self.send_response(200, "NRS Entry lookup for pattern '%s' successful" % redis_patt)
        self.send_header("MIME-Version", "1.0")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
        self.send_header("Last-Modified", self.date_time_string())
        self.end_headers()
        self.send_string(f.getvalue())
        f.close
          
        return

    #--------------------------------------------------------------------------#
    def send_publish_report(self, rform, ndo_in_cache, ignored_upload,
                            first_store, form, metadata, ni_uri):
        """
        @brief Create and send report of a successful publication of an NDO
        @param rform string format for report ('json', 'html' or 'plain')
        @param ndo_in_cache boolean indicating if the content is in the cache
        @param ignored_upload boolean indicating if the upload had duplicated content
                                      file that checked but ignored
        @param first_store boolean indicating if this was a new NDO in this cache
        @param form cgi.FieldStorage object with processed form data from publish request
        @param metadata NetInfMetaData object instance containing current metadata for NDO
        @param ni_uri string canonicalized ni scheme URI for object being stored
        @return (none)

        Construct a report indicating what has been cached as a result of a
        publish operation and send it as an HTTP response.  Client can ask
        for various report response formats:
        - json   send a JSON object string describing the operation performed
                 and a summary of the metadata now held about the NDO
                 (content-type: application/json).
        - html   send an HTML with a human readable report of what has been done
                 (content-type: text/html)
        - plain  send a plain text report of what has been done
                 (content-type:  text/plain)

        The status code returned in the JSON data when 'json' format response is
        requested is as follows:
        - 201 First store of content and metadata stored or updated
        - 202 Duplicate content ignored (already in cache), metadata updated
        - 204 No content in store or supplied with request; metadata stored
        - 205 No content in store or supplied with request; metadata updated

        The usage approximates to (but is not exactly equivalent to the
        corresponding HTTP 2xx response codes.
        """
        # Content file length
        file_len = metadata.get_size()
        file_len_str = str(file_len) + " octets" \
                       if (file_len >= 0) else "unknown"
            
        # Format information strings to be used in report and set status
        # info1 is used in the HTML and plain text report bodies
        # info2 is the message send with the HTTP response type message
        if ndo_in_cache and ignored_upload:
            info1 = ("File %s is already in cache as '%s' (%s);" + \
                    " metadata updated.") % (form["octets"].filename,
                                             ni_uri,
                                             file_len_str)
            info2 = "Object already in cache; metadata updated."
            status = 202
        elif ndo_in_cache and first_store:
            info1 = ("File %s and metadata stored in new cache entry" + \
                     " as '%s' (%s)") % (form["octets"].filename,
                                         ni_uri,
                                         file_len_str)
            info2 = "Object and metadata cached."
            status = 201
        elif ndo_in_cache:
            info1 = ("File %s stored in cache and metadata updated" + \
                     " as '%s' (%s)") % (form["octets"].filename,
                                         ni_uri,
                                         file_len_str)
            info2 = "Object cached and metadata updated."
            status = 201
        elif first_store:
            info1 = "Metadata only for '%s' stored in cache" % ni_uri
            info2 = "Metadata for object stored in cache."
            status = 204
        else:
            info1 = "Metadata for '%s' updated in cache (NDO not present)" % ni_uri
            info2 = "Metadata for object updated - object not present."
            status = 205

        self.loginfo("publish,status,%d,uri,%s,ctype,%s,size,%s" % (status,
                                                                    ni_uri,
                                                                    metadata.get_ctype(),
                                                                    metadata.get_size()))
            
        # Select response format and construct body in a StringIO pseudo-file
        f = StringIO()
        if rform == "json":
            # JSON format: Metadata as JSON string        
            ct = "application/json"
            # Add the locator of this node to the locator list in the summary
            rd = metadata.summary(self.authority)
            rd["status"]  = status
            rd["msgid"] = form["msgid"].value
            json.dump(rd, f)
        elif rform == "plain":
            # Textual form report (useful for publish command line applications)
            ct = "text/plain"
            f.write("NetInf PUBLISH succeeded - %s: status %d\n" % (info1, status))
        elif rform == "html":
            # HTML formatted report intended to be outputted by web browsers
            ct = "text/html"
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n')
            f.write("<html>\n<body>\n<title>NetInf PUBLISH Report</title>\n")
            f.write("<h2>NetInf PUBLISH Report</h2>\n")
            f.write("\n<p>%s: status %d</p>" % (info1, status))
            f.write("\n</body>\n</html>\n")
                
        length = f.tell()
        f.seek(0)
        
        self.send_response(200, info2)
        self.send_header("MIME-Version", "1.0")
        self.send_header("Content-Type", ct)
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        # Ensure response not cached
        self.send_header("Expires", "Thu, 01-Jan-70 00:00:01 GMT")
        self.send_header("Last-Modified", metadata.get_timestamp())
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        # IE extensions - extra header
        self.send_header("Cache-Control", "post-check=0, pre-check=0")
        # This seems irrelevant to a response
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.send_string(f.getvalue())
        f.close()

        return

    #--------------------------------------------------------------------------#
    def check_path_for_query_and_fragments(self, path):
        """
        @brief Generate flags indicating if a URL path has a query string or fragment(S)
        @param path string what is left after the netloc in the HTTP URL given to the server
        @return tuple of two boolean values, indicating (0) query string and (1) fragments present

        Determine if path has '?' or '#' or '?' followed by '#' that are introducers for
        respectively query string and fragments.

        NOTE: If the URI was supplied by a reputable web browser or other
        HTTP client, the URI should not contain any fragments as the fragment
        specifier is supposed to be applied to the returned resoource and is
        not sent over the wire.
        """
        split_query_frag = path.split("?", 1)
        if len(split_query_frag) > 1:
            has_query_string = True
            split_frag = split_query_frag[1].split("#", 1)
        else:
            has_query_string = False
            split_frag = split_query_frag[0].split("#", 1)
        has_fragments = (len(split_frag) > 1)
        if has_fragments:
            self.logwarn("URI supplied with fragment identifier (%s) - should not happen" %
                            path)

        return (has_query_string, has_fragments)

    #--------------------------------------------------------------------------#
    def path_to_ni_name(self, path, sep):
        """
        @brief Take trailing part of pathname and make ni_name instance
        @param path string path part in the form <alg-name>["/"|";"]<digest>
        @parame sep string either "/" or ";" - the separator in path
        @return 2-tuple (rv, validated ni-name instance or None)

        An ni_name instance is created from the path part using ni: scheme
        It is then validated.

        If the validation is successful, return (niSUCCESS, ni_name instance)
        Otherwise (error code from validation, None)
        """
        assert (sep == ";") or (sep == "/")
        try:
            alg_name, remainder = path.split(sep, 1)
        except:
            return(ni_errs.niBADURL, None)

        try:
            i = remainder.index("?")
            digest, query = remainder.split("?")
        except:
            digest = remainder
            query = ""
        
        ni_name = NIname((NI_SCHEME, "", alg_name, digest, query))
        rslt = ni_name.validate_ni_url()
        if rslt == ni_errs.niSUCCESS:
            return (rslt, ni_name)
        else:
            return (rslt, None)
        
    #--------------------------------------------------------------------------#
    def check_form_data(self, form, mandatory_fields,
                        optional_fields, form_name):
        """
        @brief Checks that the fields in the form sent with a POST are as expected.
        @param form cgi.FieldStorage object with processed form data from POST request
        @param mandatory_fields list of strings for names of fields that must be present
        @param optional_fields  list of strings for names of fields that may be present
        @param form_name string name of form that generated form data for error messages
        @retval (False, None) 2-tuple if checking fails
        @retval (True, field_values) 2-tuple if checking succeeds with field_values
                                     holding the value of the various fields present or
                                     "(not supplied)" for optional fields not present.

        Gather field values for all fields present in form.

        Check:
        - Mandatory_fields are all present
        - Remaining fields are all in the optional_fields and there are no others
        """
        # Record field values found
        field_values = {}
        # Validate form data
        # Check only expected keys and no more
        for field in mandatory_fields:
            if field not in form.keys():
                self.logerror("Missing mandatory field %s in %s form" %
                              (field, form_name))
                self.send_error(412, "Missing mandatory field %s in %s form." %
                                (field, form_name))
                return (False, None)
            field_values[field] = form[field].value
            
        ofc = 0
        for field in optional_fields:
            if field in form.keys():
                ofc += 1
                field_values[field] = form[field].value
            else:
                field_values[field] = "(not supplied)"
                
        if (len(form.keys()) > (len(mandatory_fields) + ofc)):
            self.logerror("NetInf %s form has too many fields: %s" %
                          (form_name, str(form.keys())))
            self.send_error(412, "Form has unexpected extra fields beyond %s" %
                            (str(mandatory_fields) + str(optional_fields)))
            return (False, None)
                          
        return (True, field_values)

    #--------------------------------------------------------------------------#
    def form_to_locs(self, form):
        """
        @brief Extract locator items (loc1, loc2) from form and return a tuple
        of loc values.
        @param form cgi.FieldStorage object with processed form data from POST request
        @return two item tuple of locators - either None or value from form
        """
        if "loc1" in form.keys():
            loc1 = form["loc1"].value
        else:
            loc1 = None

        if "loc2" in form.keys():
            loc2 = form["loc2"].value
        else:
            loc2 = None

        return (loc1, loc2)

    #--------------------------------------------------------------------------#
    def read_nrs_entry(self, redis_key, val_names):
        """
        @brief Read the entry in the NRS database for the redis_key and return values
               for hash names in val_names (if present).
        @param redis_key string key name for NRS database
        @param val_names list of strings with names of hash elements to read
        @retval None if the key does not exist or has no entries or getting
                     values fails
        @retval dictionary object representing JSON object with fields 'hints' and
                           'locs' containing arrays of strings from 'hints*' and
                           'locs*' hashes, respectively and 'meta' containing
                           the value of the 'meta' hash.
        """
        # Check if there is any entry
        try:
            all_vals = self.nrs_redis.hgetall(redis_key)
        except Exception, e:
            return None

        if len(all_vals) == 0:
            return None
        
        try:
            vals = self.nrs_redis.hmget(redis_key, val_names)
        except Exception, e:
            return None

        # Combine hints and locs into lists
        hints = []
        locs = []
        meta = None
        for pair in itertools.imap(None, val_names, vals):
            if pair[1] is not None:
                if pair[0].startswith("hint"):
                    hints.append(pair[1])
                elif pair[0].startswith("loc"):
                    locs.append(pair[1])
                elif pair[0] == "meta":
                    meta = pair[1]

        # Return the results as a dictionary 
        return { "hints" : hints, "locs": locs, "meta": meta }

    #--------------------------------------------------------------------------#
    def metadata_timestamp_for_now(self):
        """
        @brief Format timestamp recording time 'now' as string for metadata files.
        @return string with formatted timestamp for time at this instant
                as expressed using UTC time.
        """
        return datetime.datetime.utcnow().strftime(self.METADATA_TIMESTAMP_TEMPLATE)

    #--------------------------------------------------------------------------#
    def mime_boundary(self):
        """
        @brief Create a MIME boundary string by hashing today's date
        @return ASCII string suitable for use as mime boundary
        """
        return hashlib.sha256(str(datetime.date.today())).hexdigest()

#==============================================================================#
class AlgDigestOp:
    """
    @brief Encapsulates prefix and operations for alg/digest GET ops

    Several of the GET operations use URLs of the form
        <prefix><alg><sep><digest["?"<query string>]
    where the prefix is of the form (as regular expression) "/[.*]/"

    To avoid having to repeat the same code fragment several times
    we make a dictionary which is indexed by the prefix and provides
    the values for each case in the value which is an instnce of this class
    The intention is to try and minimise the amount of dynamic code executed
    by incorporating the construction in a class method.  Not sure how much
    this helps yet. 
    """
    def __init__(self, prefix, op_name, scheme, sep, errmsg, send_op):
        """
        @brief Constructor - save the parameters
        @param prefix string the distinguishing prefix in the path
        @param op_name string operation name for logging
        @param scheme string ni: or nih: scheme to construct
        @param sep string single character that separates alg/digest
        @param errmsg string error message in case path is not in right form
        @param send_op callable passed ni_name constructed from path
                                This will be an unbound instance of a method
                                in NIHTTPRequestHandler
        """
        self.prefix  = prefix
        self.op_name = op_name
        self.scheme  = scheme
        self.sep     = sep
        self.errmsg  = errmsg
        self.send_op = send_op
        return

#==============================================================================#
# === GLOBAL VARIABLES ===

##@var alg_digest_get_dict
# dictionary indexed by prefixes for paths that are used in GET requests
#            that are completed by a string of the form
#            <alg-name><sep><digest>
#            where
#               <alg-name> is one of the digest algorithm identifiers
#               <sep> is either ';' or '/'
#               <digest> is the digest of the conetnt of the NDO
#            The values in the dictionary are instances of the
#            AlgDigestOp class defined immediately above.
#            This dictionary is (only) used the send_head method of
#            NIHTTPRequestHandler.

alg_digest_get_dict = {
    NIHTTPRequestHandler.CONT_PRF:
        AlgDigestOp(NIHTTPRequestHandler.CONT_PRF, "get_content", NI_SCHEME,
                    ";", "Content access URL cannot be parsed: %s",
                    NIHTTPRequestHandler.send_get_header),
    NIHTTPRequestHandler.META_PRF:
        AlgDigestOp(NIHTTPRequestHandler.META_PRF, "get_meta", NI_SCHEME, 
                    ";", "Content access URL cannot be parsed: %s",
                    NIHTTPRequestHandler.send_meta_header),
    NIHTTPRequestHandler.QRCODE_PRF:
        AlgDigestOp(NIHTTPRequestHandler.QRCODE_PRF, "get_qrcode", NI_SCHEME, 
                    ";", "Content access URL cannot be parsed: %s",
                    NIHTTPRequestHandler.send_qrcode_header),
    NIHTTPRequestHandler.NI_HTTP:
        AlgDigestOp(NIHTTPRequestHandler.NI_HTTP, "get_wkn_ni", NI_SCHEME, 
                    "/", "Content access URL cannot be parsed: %s",
                    NIHTTPRequestHandler.send_get_redirect),
    NIHTTPRequestHandler.NIH_HTTP:
        AlgDigestOp(NIHTTPRequestHandler.NIH_HTTP, "get_wkn_nih", NIH_SCHEME, 
                    "/", "Content access URL cannot be parsed: %s",
                    NIHTTPRequestHandler.send_get_redirect)

#==============================================================================#

        }
