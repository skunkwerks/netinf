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
standard Python module BaseHTTPServer.

The logging and thread management was inspired by the PyMail program from the
N4C project.

The basic GET and POST handlers are inspired by Doug Hellmann's writing on
on BaseHTTPServer in his Python Module of the Week series at
http://www.doughellmann.com/PyMOTW/BaseHTTPServer/index.html

Should be used with Python 2.x where x is 6 or greater (the TCP socket
server up to version 2.5 is badly flawed (euphemism)).

The server uses a configuration file to specify various items (see
niserver_main.py) and set up logging.  The items that are significant
for the internal operations here are:

- server_port     the TCP port used by the HTTP server listener (default 8080)
- authority       the hostname part of the address of the HTTP server
- storage_root    the base directory where the content cache is stored
- logger          a logger to be used by the server (uses Python logging module)
- provide-nrs     flag indicating if NRS operations should be supported by
                  this server
- getputform      pathname for a file containing the HTML code uploaded to show
                  the NetInf GET/PUBLISH/SEARCH forms in a browser
- nrsform         pathname for file containing the HTML code uploaded to show
                  the NetInf NRS configuration forms in a browser
- favicon         pathname for favicon file sent to browsers for display.

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

The vast majority of the code is contained in the NIHTTPHandler class which
is a subclass of the standard BaseHTTPRequestHandler.

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
##@var NISERVER_VER
# Version string for niserver
NISERVER_VER = "1.1"

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

from BaseHTTPServer import BaseHTTPRequestHandler
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

##@var redis_loaded
# Flag indicating if it was possible to load the Redis module.
# The program can do without Redis if not providing NRS services.
try:
    import redis
    redis_loaded = True
except ImportError:
    redis_loaded = False

#=== Local package modules ===

import ni

#==============================================================================#
# List of classes/global functions in file
__all__ = ['NetInfMetaData', 'NIHTTPServer', 'NIHTTPHandler',
           'check_cache_dirs', 'ni_http_server'] 
#==============================================================================#
# GLOBAL VARIABLES

##@var NETINF_VER
# Version of NetInf implemented - written into metadata instances 
NETINF_VER = "v0.3 Elwyn"

##@var NDO_DIR
# Pathname component identifying sub-directory under storage base for content files
NDO_DIR        = "/ndo_dir/"

##@var META_DIR
# Pathname component identifying sub-directory under storage base for metadata files
META_DIR       = "/meta_dir/"

#==============================================================================#
class NetInfMetaData:
    """
    @brief Class holding the data from a metadata file.
    The metadata file holds a serialized version of a JSON object that is
    read/written to the json_obj held in the class.

    The structure of the JSON object is:
    - NetInf    Version string for NetInf specification applied
    - ni        ni[h] name of NDO to which metadata applies
    - ct        MIME content type of NDO (if known)
    - size      Length of content in octets or -1 if not known
    - details   Array of JSON objects containing:
       - ts         UTC timestamp for object, format "%y-%m-%dT%H:%M:%S+00:00"
       - metadata   JSON object with arbitrary contents
       - loc        Array of locators for this NDO
       - publish    Information about how this was published - string or object
       - search     JSON object describing search that flagged this NDO with
          - searcher    The system that did the search (e.g., this code)
          - engine      The search engine used to perform the search
          - tokens      The search query run by the engine to flag this NDO

    The initial entries are made when an instance is first created.
    Subsequent 'details' entries are added whenever the metadata is updated.
    The content type may not be known on initial creation if the publisher
    only sent metadata.  It may be updated later if the content is added to
    the cache.

    The instance variable curr_detail holds the most recent details item
    at all times.
    """

    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var json_obj
    # A JSON object holding the representation of the metadata.

    ##@var curr_detail
    # The most recent (last) JSON object in the array of "details" objects

    #--------------------------------------------------------------------------#
    def __init__(self, ni_uri="", timestamp=None, ctype=None, file_len=-1,
                 myloc=None, loc1=None, loc2=None, extrameta=None):
        """
        @brief Create a new metadata object from parameters
        
        If all the parameters are omitted an empty object will be created
        that can be populated from a file using the 'set_json_val' method.
        @param ni_uri string The ni[h]: name to which the metadata applies
        @param timestamp string initial creation timestamp (format: see class header)
        @param ctype string MIME type of NDO (may be empty string if not yet known)
        @param file_len integer Length of content in octets or -1 if not yet known
        @param myloc string locator derived from authority in ni name (i.e., local server)
        @param loc1 string locator for NDO
        @param loc2 string locator for NDO
        @param extrameta dictionary JSON object with other objects for 'details'

        Creates JSON dictionary for json_obj with initial 'details' object 
        """
        self.json_obj = {}
        self.json_obj["NetInf"] = NETINF_VER
        self.json_obj["ni"]     = ni_uri
        if ctype is None:
            self.json_obj["ct"] = ""
        else:
            self.json_obj["ct"] = ctype
        self.json_obj["size"] = file_len
        self.json_obj["details"] = []
        self.add_new_details(timestamp, myloc, loc1, loc2, extrameta)
        return
    
    #--------------------------------------------------------------------------#
    def add_new_details(self, timestamp, myloc, loc1, loc2, extrameta):
        """
        @brief Append a new details entry to the array of objects

        @param timestamp string initial creation timestamp (format: see class header)
        @param ctype string MIME type of NDO (may be empty string if not yet known)
        @param myloc string locator derived from authority in ni name (i.e., local server)
        @param loc1 string locator for NDO
        @param loc2 string locator for NDO
        @param extrameta dictionary JSON object with other objects for 'details'
        @return (none)

        Creates JSON object dictionary to append to 'details' array from
        parameters:
        - The timestamp is used directly via set_timestamp
        - The parameters myloc, loc1, and loc2 are added to loclist if not None
        - All the key-value pairs in extrameta are copied to 'metadata'

        Reset the curr_detail instance object to point to new detail item.

        Note: we assume that the 'details' are in timestamp order, i.e., that
        added details entries have later timestamps.  This is not currently
        checked and might look odd if the system clock is rest backwards.
        It doesn't have any significant effect since the output from this
        object is generally the summary or bits of the most recently added
        entry - the timestamp is just for convenience.
        """
        
        self.curr_detail = {}
        self.json_obj["details"].append(self.curr_detail)
        self.set_timestamp(timestamp)
        self.append_locs(myloc, loc1, loc2)
        metadata = {}
        self.curr_detail["metadata"] = metadata
        
        if extrameta != None:
            try:
                for k in extrameta.keys():
                    metadata[k] = extrameta[k]
            except AttributeError, e:
                print("Error: extrameta not a dictionary (%s)" % type(extrameta))
                pass
        return

    #--------------------------------------------------------------------------#
    def json_val(self):
        """
        @brief Access JSON object representing metadata as Python dictionary
        @return json_obj
        """
        return self.json_obj
    
    #--------------------------------------------------------------------------#
    def set_json_val(self, json_val):
        """
        @brief Set json_obj to a dictionary typically derived from
        @brief an NDO metadata file
        @param json_val dictionary JSON object in correct form
        @return booleans indicating if load was successful

        Currently the format of the dictionary is not checked,
        but we do check that the "NetInf" entry matches with
        the current NETINF_VER string.
        TO DO: add more checking and deal with backwards compatibility.

        The curr_detail instance variable is set to the last
        item in the 'details' array.
        """
        if json_val["NetInf"] != NETINF_VER:
            return False
        self.json_obj = json_val
        # Set the current details to be the last entry
        self.curr_detail = self.json_obj["details"][-1]
        return True

    #--------------------------------------------------------------------------#
    def append_locs(self, myloc=None, loc1=None, loc2=None):
        """
        @brief Build loclist array from parameters
        @param myloc string locator derived from authority in ni name (i.e., local server)
        @param loc1 string locator for NDO
        @param loc2 string locator for NDO
        @return (none)

        Build 'loc' array of strings and put into 'curr_detail'
        object dictionary.  The parameters are only added to the
        list if they are not None and not the empty string.
        """
        loclist = []
        self.curr_detail["loc"] = loclist
        if myloc is not None and myloc is not "":
            if not myloc in loclist: 
                loclist.append(myloc)
        if loc1 is not None and loc1 is not "":
            if not loc1 in loclist: 
                loclist.append(loc1)
        if loc2 is not None and loc2 is not "":
            if not loc2 in loclist: 
                loclist.append(loc2)
        return
    
    #--------------------------------------------------------------------------#
    def get_ni(self):
        """
        @brief Accessor for NDO ni name in metadata
        @retval string Value of "ni" item in json_obj.
        """
        return self.json_obj["ni"]
    
    #--------------------------------------------------------------------------#
    def get_timestamp(self):
        """
        @brief Accessor for NDO most recent update timestamp
        @retval string Value of "ts" item in curr_detail.

        For format of timestamp see class header
        """
        return self.curr_detail["ts"]

    #--------------------------------------------------------------------------#
    def set_timestamp(self, timestamp):
        """
        @brief Set the timestamp item ("ts") in curr_detail
        @param string timestamp (for format see class header)
        @return (none)
        """
        if timestamp is None:
            self.curr_detail["ts"] = "(unknown)"
        else:
            self.curr_detail["ts"] = timestamp
        return

    #--------------------------------------------------------------------------#
    def get_ctype(self):
        """
        @brief Accessor for NDO content type in metadata
        @retval string Value of "ct" item in json_obj.
        """
        return self.json_obj["ct"]

    #--------------------------------------------------------------------------#
    def set_ctype(self, ctype):
        """
        @brief Set the content type item ("ct") in json_obj.
        @param ctype string MIME content type for NDO
        @return (none)

        Setting is skipped if parameter is None.
        """
        if ctype is not None:
            self.json_obj["ct"] = ctype
        return

    #--------------------------------------------------------------------------#
    def get_size(self):
        """
        @brief Accessor for NDO content file size in metadata
        @retval integer Value of "size" item in json_obj.
        """
        return self.json_obj["size"]

    #--------------------------------------------------------------------------#
    def set_size(self, file_len):
        """
        @brief Set the content file size item ("size") in json_obj.
        @param file_len integer content file size for NDO in octets
        @return (none)

        Setting is skipped if parameter is None.
        """
        if file_len is not None:
            self.json_obj["size"] = file_len
        return

    #--------------------------------------------------------------------------#
    def get_loclist(self):
        """
        @brief Scan all the details entries and get the set of all
        @brief distinct entries in loc entries
        @retval array of strings set of all different locators from "details" entries
        """
        loclist = []
        for d in self.json_obj["details"]:
            for l in d["loc"]:
                if not l in loclist:
                    loclist.append(l)
        #print("Summarized loclist: %s" % str(loclist))
        
        return loclist
        
    #--------------------------------------------------------------------------#
    def get_metadata(self):
        """
        @brief Scan all the details entry and get the set of all
        @brief distinct entries in metadata entries
        @retval dictionary JSON object with summary of metadata

        Scan the 'metadata' entries from the objects in the
        'details' array to create a summary object from all the entries.

        For every different key found in the various 'metadata' objects,
        copy the key-value pair into the summary, except for the
        'search' keys.

        Treat 'search' key specially - combine the values from any
        search keys recorded into an array, omitting duplicates.
        Search key values are deemed to be duplicates if they have the
        same 'engine' and 'tokens' key values (i.e., the 'searcher' key
        value is ignored for comparison purposes).  Write the resulting
        array as the value of the 'searches' key in the summary object.

        For other keys, if their are duplicates, just take the most
        recently recorded one (they are recorded in time order)
        """
        metadict = {}
        srchlist = []
        n = -1
        for d in self.json_obj["details"]:
            curr_meta = d["metadata"]
            n += 1
            for k in curr_meta.keys():
                if k == "search":
                    # In case somebody put in a non-standard search entry
                    try:
                        se = curr_meta[k]
                        eng = se["engine"]
                        tok = se["tokens"]
                        dup = False
                        for s in srchlist:
                            if ((s["engine"] == eng) and (s["tokens"] == tok)):
                                dup = True
                                break
                        if not dup:
                            srchlist.append(se)
                    except:
                        # Non-standard search entry - leave it in place
                        metadict[k] = curr_meta[k]
                else:
                    metadict[k] = curr_meta[k]
        if len(srchlist) > 0:
            metadict["searches"] = srchlist
            
        #print("Summarized metadata: %s" % str(metadict))
        
        return metadict

    #--------------------------------------------------------------------------#
    def summary(self):
        """
        @brief Generate a JSON object dictionary containing summarized metadata.
        @retval dictionary JSON object containing summarized data

        The summary JSON object dictionary contains:
        - the 'NetInf', 'ni', 'ct' and 'size' entries copied from json_obj
        - the timestamp 'ts' from the most recent (last element) of the 'details'
        - the summarized locator list 'loclist' derived by get_loclist
        - the summarized 'metadata' object derived by get_metadata.
        """
        sd = {}
        for k in ["NetInf", "ni", "ct", "size"]:
            sd[k] = self.json_obj[k]
        sd["ts"] = self.get_timestamp()
        sd["loclist"] = self.get_loclist()
        sd["metadata"] = self.get_metadata()
        return sd

    #--------------------------------------------------------------------------#
    def __repr__(self):
        """
        @brief Output compact string representation of json_obj.
        @retval string JSON dump of json_obj in maximally compact form.
        """
        return json.dumps(self.json_obj, separators=(',',':'))
        
    #--------------------------------------------------------------------------#
    def __str__(self):
        """
        @brief Output pretty printed string representation of json_obj.
        @retval string JSON dump of json_obj with keys sorted and indent 4.
        """
        return json.dumps(self.json_obj, sort_keys = True, indent = 4)

#==============================================================================#

class NIHTTPHandler(BaseHTTPRequestHandler):
    """
    @brief Action routines for all requests handled by niserver.

    @details
    The class (name) for this class is passed to the NIHTTPServer base class
    HTTPServer when the NIHTTPServer is instantiated (see below).  The server
    is set up as a threaded server.

    When the HTTPServer listener receives a connection request, it creates
    a new thread to handle the request(s) that is(are) passed over the
    connection and calls the overridden 'handle' method. It then reads in the
    request headers of the first request and passes the request to the
    appropriate routine out of 'do_HEAD', 'do_GET' and 'do_POST', depending on
    the request type.

    Depending on the value of the 'Connection' header in the request, the thread may
    remain active to receive additional requests ('keep-alive' value) or close
    and terminate the thread after processing the request ('close' value).

    When a new connection is opened and the thread created, the handle() function
    in this class is called.  This function sets up a name for the thread and
    calls add_thread in the NIHTTPServer to record the running threads so that
    they can be enumerated and closed down when the server terminates if they have
    been left running because of 'Connection: keep-alive' specifications.  The
    handle function also sets up instance variables with convenience functions
    for calling the logger.  The logger uses the thread name in the logged
    messages to differentiate messages from different handlers.

    Note: All instance variables are defined in the superclass.
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
    # Path prefix for /.well-known/ni 
    NI_HTTP         = WKN + "ni"
    ##@var NIH_HTTP
    # Path prefix for /.well-known/nih 
    NIH_HTTP        = WKN + "nih"
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
    TI              = "?ct="

    # === NetInf NDO Cache listing ===
    ##@var NETINF_LIST
    # URL path to invoke return of cache list
    NETINF_LIST     = "/netinfproto/list"
    ##@var ALG_QUERY
    # Query string prefix for selecting the digest algorithm when listing the cache.
    ALG_QUERY       = "?alg="

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

    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    # === Thread information ===
    ##@var request_thread
    # The thread identifier retrieved from threading.CurrentThread()
    ##@var thread_num
    # Sequence number for threads controlled by next_handler_num in
    # the NIHTTPServers.  Incorporated in thread name to identify thread.

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
    def handle(self):
        """
        @brief Wrapper round superclass handle() function setting up context.
        @return (none)

        Obtain unique sequence number for handler thread and make name
        for thread using it when connection is opened.

        Inform HTTPServer listener that thread is running.

        Generate convenience function variables for various levels of logging.

        Call superclass handle() function to manage requests -  farms out
        requests to 'do_GET', 'do_HEAD' or 'do_POST' according to request
        type.  There may be several requests on a single connection if
        requests specify 'Connect: keep-alive'.

        After all requests have been processed, inform HTTPServer listener that
        thread is no longer running.
        """
        
        # Record thread identifier in instance and set up thread name.
        self.request_thread = threading.currentThread()
        # Serialize access to next_handler_num
        with self.server.thread_running_lock:
            self.thread_num = self.server.next_handler_num
            self.server.next_handler_num += 1
        self.request_thread.setName("NI HTTP handler - %d" %
                                    self.thread_num)

        # Tell listener we are running
        self.server.add_thread(self)
        
        # Logging functions
        self.loginfo = self.server.logger.info
        self.logdebug = self.server.logger.debug
        self.logwarn = self.server.logger.warn
        self.logerror = self.server.logger.error

        self.loginfo("New HTTP request connection from %s" % self.client_address[0])

        # Delegate to super class handler
        BaseHTTPRequestHandler.handle(self)

        # Tell listener thread has finished
        self.server.remove_thread(self)
        self.loginfo("NI HTTP handler finishing")
        return

    #--------------------------------------------------------------------------#
    """
    Unclear that this is needed (or works.. where is request_close?)
    end_run is defined in the NIHTTPServer class and shuts down the threads.
    def end_run(self):
        self.request_close()
    """
    #--------------------------------------------------------------------------#
    def log_message(self, format, *args):
        """
        @brief Log an arbitrary message.
        @param format string Format template string with %-encoded substitutions
        @param args any Variables to substitute into format template
        @return (none)
        
        Overridden from base class to use logger functions

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client host and current date/time are prefixed to
        every message.
        """

        self.loginfo("%s - - [%s] %s\n" %
                      (self.address_string(),
                       self.log_date_time_string(),
                       format % args))
        return

    #--------------------------------------------------------------------------#
    def do_GET(self):
        """
        @brief Serve a GET request.

        Processing is performed by send_head which will send the HTTP headers
        and generally leave a file descriptor ready to read with the body
        unless there is an error.
        If send_head returns a file object, copy the contents to self.wfile
        which sends it back to the client.

        @return (none)
        """
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()
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

        There are four special cases:
        - 1. Getting a listing of the cache
        - 2. Returning the form code for GET/PUT/SEARCH form
        - 3. If running NRS server, return the form code for NRS configuration 
        - 4. Returning the NETINF favicon

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
        
        @return (none)
        """
        self.logdebug("GET or HEAD with path %s" % self.path)

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
            return self.send_fixed_file( self.server.getputform,
                                         "text/html",
                                         "form definition")

        # Display the NRS form for this server, if running NRS server.
        # The HTML code is in a file with pathname configured and
        # passed to server.
        if (self.path.lower() == self.NRS_CONF_FORM):
            if not self.server.provide_nrs:
                self.loginfo("Request for NRS configuration form when not running NRS server")
                self.send_error(404, "NRS server not running at this location")
                return None
            # Display the form
            return self.send_fixed_file( self.server.nrsform,
                                         "text/html",
                                         "form definition")

        # Return the 'favicon' usually displayed in browser headers
        # Filename is configured and stored in self.server.favicon
        if (self.path.lower() == self.FAVICON_FILE) :
            self.logdebug("Getting favicon")
            return self.send_fixed_file( self.server.favicon,
                                         "image/x-icon",
                                         "form definition")
        
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
        # Deal with operations that retrieve cached NDO content, metadata files
        # or a QRcode image for the ni scheme URI for the NDO. 

        # Return content from http:///ni_cache/<alg>;<digest> URL
        if (self.path.lower().startswith(self.CONT_PRF)):
            ndo_path, meta_path = self.redirect_name_to_file_names( \
                                                self.server.storage_root,
                                                self.path)
            # TO DO: Really ought to get msgid as a query string?
            return self.send_get_header(ndo_path, meta_path, None)

        # Return metadata from http:///ni_meta/<alg>;<digest> URL
        if (self.path.lower().startswith(self.META_PRF)):
            return self.send_meta_header(self.path, self.server.storage_root) 

        # Return QRcode image from http:///ni_qrcode/<alg>;<digest> URL
        if (self.path.lower().startswith(self.QRCODE_PRF)):
            return self.send_qrcode_header(self.path, self.server.storage_root) 

        # Process /.well-known/ni[h]/<alg name>/<digest>
        rv, ni_name, ndo_path, meta_path = self.translate_wkn_path(self.server.authority,
                                                                   self.server.storage_root,
                                                                   self.path)
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("Path format for %s inappropriate: %s" % (self.path,
                                                                   ni.ni_errs_txt[rv]))
            self.send_error(400, ni.ni_errs_txt[rv])
            return None

        return self.send_get_redirect(ni_name, meta_path)

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
        ni.NIname.get_all_algs() which returns a list of the textual names of
        the possible algorithms.

        There is a sub-directory below the (server.)storage_root for each of
        these algorithms.  These are the directories that are listed.  At present
        there are one or two entries for each file in ni_ndo and/or ni_meta
        sub-directories for each algorithm, each named by the digest of the
        content for the relevant algorithm:
        - The content file in the ni_ndo sub-directory if the content is available
        - The metadata file in the ni_meta sub-directory which contains information
          about the content as a JSON encoded string

        Because of the nature of the ni: digests, the second form of the name
        is a.s. unique, although there may be some issues with heavily
        truncated hashes where uniqueness is a smaller concept.

        This code dynamically builds some HTTP to display the selected
        directory listing(s).  The entries for each directory are sorted with
        the nih entries before the ni entries and each group sorted case
        insensitively.

        If the content file is present the displayed ni or nih URI is a link
        to the .well-known HTTP URL that would retrieve the metadata and content.
        If there is metadata for the ni[h] URI, the word 'meta' is displayed
        after the URI giving a link to just the metadata.
        In addition, the word 'QRcode' is displayed with a link that will
        display q QRcode image for the ni[h] name for the item. 
        """
        # Determine which directories to list - assume all by default
        algs_list = ni.NIname.get_all_algs()
        qo = len(self.NETINF_LIST)
        if (len(path) > qo):
            # Check if there is a query string
            # Note: the caller has already checked there is no fragment part
            if not path[qo:].startswith(self.ALG_QUERY):
                # Not a valid query string
                if (path[qo] == '?'):
                    self.send_error(406, "Unrecognized query string in request")
                else:
                    self.send_error(400, "Unimplemented request")
                return None
            if path[(qo + len(self.ALG_QUERY)):] not in algs_list:
                self.send_error(404, "Cache for unknown algorithm requested")
                return
            algs_list = [ path[(qo + len(self.ALG_QUERY)):]]

        # Set up a StringIO buffer to gather the HTML
        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Named Data Object Cache Listing for server %s</title>\n" % self.server.server_name)
        f.write("<body>\n<h1>Named Data Object Cache Listing for server %s</h1>\n" % self.server.server_name)
        f.write("<hr>\n<ul>")

        # Server access netloc
        if (self.server.server_port == 80):
            # Can omit the default HTTP port
            netloc = self.server.server_name
        else:
            netloc = "%s:%d" % (self.server.server_name, self.server.server_port)

        # List all the algorithms selected as HTTP style URLs
        # Within each pair of selected algorithm directories
        # - Read the lists of files in each directory and convert to sets
        #   Expect that generally the ndo list will be a subset of meta list
        #   because can upload just metadata and/or have content expired.
        # - Create union of sets
        for alg in algs_list:
            meta_dirpath = "%s%s%s" % (self.server.storage_root, META_DIR, alg)
            try:
                meta_set = set(os.listdir(meta_dirpath))
            except os.error:
                self.send_error(404, "No permission to list directory for algorithm %s" % alg)
                return None
            
            ndo_dirpath = "%s%s%s" % (self.server.storage_root, NDO_DIR, alg)
            try:
                ndo_set = set(os.listdir(ndo_dirpath))
            except os.error:
                self.send_error(404, "No permission to list directory for algorithm %s" % alg)
                return None

            # This piece of magic produces a combined list of the different unique
            # entries in the two directories ordered so that nih name digests that
            # contain a semi-colon (';') come before ni name digests (which don't)
            # and within the sets digests are sorted i a case-insensitive order.
            # Note: sorted() is reasonably efficient since it only makes the key
            # once for each entry in the list during sort process.  The nih/ni split
            # is handled by generating keys which prefix the digests with '0' or '1'
            # respectively. 
            all_ordered = sorted(meta_set.union(ndo_set),
                                 key = lambda k:
                                 ("0"+k).lower() if ';' in k else ("1"+k).lower())
            
            f.write("</ul>\n<h2>Cache Listing for Algorithm %s</h2>\n<ul>\n" % alg)
            ni_http_prefix   = "http://%s%s/%s/" % (netloc, self.NI_HTTP, alg)
            nih_http_prefix  = "http://%s%s/%s/" % (netloc, self.NIH_HTTP, alg)
            meta_http_prefix = "http://%s%s%s;" % (netloc, self.META_PRF, alg)
            qrcode_http_prefix = "http://%s%s%s;" % (netloc, self.QRCODE_PRF, alg)
            ni_prefix        = "ni:///%s;" % alg
            nih_prefix       = "nih:/%s;" % alg
            for name in all_ordered:
                if ';' in name:
                    # It is an nih case
                    if name in ndo_set:
                        f.write('<li><a href="%s%s">%s%s</a> ' %
                                (nih_http_prefix, name, nih_prefix, name))
                    else:
                        # No link if content file is not present 
                        f.write('<li>%s%s ' % (nih_prefix, name))
                else:
                    # It is an ni case
                    if name in ndo_set:
                        f.write('<li><a href="%s%s">%s%s</a> ' %
                                (ni_http_prefix, name, ni_prefix, name))
                    else:
                        # No link if content file is not present 
                        f.write('<li>%s%s ' % (ni_prefix, name))
                if name in meta_set:
                    f.write('(<a href="%s%s">meta</a>)' %
                            (meta_http_prefix, name))
                else:
                    f.write('(no metadata available)</li>\n')
                f.write('(<a href="%s%s">QRcode</a>)</li>\n' %
                        (qrcode_http_prefix, name))
                
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
        return f

    #--------------------------------------------------------------------------#
    def send_get_header(self, ndo_path, meta_path, msgid):           
        """
        @brief Send headers and data for the response to a get request.
        @param ndo_path string prospective pathname of NDO content file
        @param meta_path string prospective pathname of NDO metadata file
        @param msgid integer or None (for direct ni_cache accesses)
        @return None - see below for explanation.

        This function is used both to handle
        - direct GET requests of HTTP URLS http://<netloc>/ni_cache/<alg>;<digest>, and
        - PUBLISH requests of ni scheme URIs using the NetInf GET form 
        The file paths have been derived from an ni[h]: scheme URI but not yet
        verified as extant.
        
        The cache of Named Data Objects contains files that have the
        digest as file name.  This makes it impossible to guess
        what the content type of the file is from the name.
        The content type of the file is stored in the metadata for the
        NDO in the parallel directory. If we weren't told what sort of
        file it was when the file was published or we can't deduce it
        from the contents then it defaults to application/octet-stream.

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
        handled in this routine instead of passing  file object back to
        top level of handler.
        """
        f = None
        self.logdebug("send_get_header for path %s" % meta_path)
        # Check if the path corresponds to an actual file
        if not os.path.isfile(meta_path):
            self.loginfo("File does not exist: %s" % meta_path)
            self.send_error(404, "Object not found in cache")
            return None

        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(meta_path, 'rb')
        except IOError:
            self.logerror("Unable to open file %s for reading." % meta_path)
            self.send_error(404, "Metadata not readable")
            return None
        try:
            # Create empty metadata structure
            md = NetInfMetaData()
            # Read in metadata
            if not md.set_json_val(json.load(f)):
                self.logerror("Attempt to load metadata for wrong server version")
                self.send_error(500, "Metadata written by incompatible server version")
                return None
        except Exception, e:
            self.logerror("JSON decode of metadata file %s failed: %s" % (meta_path, str(e)))
            self.send_error(500, "Metadata is corrupt")
            f.close()
            return None

        f.close()

        # Check if content is present
        if os.path.isfile(ndo_path):
            try:
                cf = open(ndo_path, "rb")
            except IOError:
                self.logerror("Unable to open file %s for reading: %s")
                self.send_error(500, "Unable to open content file")
                return None
            fs = os.fstat(cf.fileno())
            ct_length = fs[6]
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
            final_mb = "\n--" + mb + "--"
            f = StringIO()
            # Initial MIME boundary
            f.write("--" + mb + "\n")
            # Part 0 - Metadata as JSON string
            f.write("Content-Type: application/json\nMIME-Version: 1.0\n\n")
            json_obj = md.summary()
            json_obj["status"] = 200
            if msgid is not None:
                json_obj["msgid"] = msgid
            json.dump(json_obj, f)
            # MIME boundary
            f.write("\n\n--" + mb + "\n")
            # Headers for NDO content file
            f.write("Content-Type: %s\nMIME-Version: 1.0\n" % md.get_ctype())
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
            self.send_header("Last-Modified", md.get_timestamp())
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            # IE extensions - extra header
            self.send_header("Cache-Control", "post-check=0, pre-check=0")
            # This seems irrelevant to a response
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            # Copy the three chunks of data to the output stream
            self.wfile.write(f.read())
            self.copyfile(cf, self.wfile)
            self.wfile.write(final_mb)
            cf.close()
            f.close()
            return None
        else:
            # No content so just send the metadata as an application/json object
            f = StringIO()
            json_obj = md.summary()
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
            self.send_header("Last-Modified", md.get_timestamp())
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            # IE extensions - extra header
            self.send_header("Cache-Control", "post-check=0, pre-check=0")
            # This seems irrelevant to a response
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            return f
            
    #--------------------------------------------------------------------------#
    def send_meta_header(self, path, storage_root):
        """
        @brief Send HTTP headers and set up for sending metadata file for GET
        request access to an HTTP URL starting ni_meta.
        @param path string pathname received with HTTP GET request
        @param storage_root string pathname of directory at the root of the cache tree
        @return file object pointing to metadata file content as JSON string or None
        
        On entry the path format should be /ni_meta/<alg>;<digest>
        """
        if not path.startswith(self.META_PRF):
            self.logerror("Path '%s' does not start with %s." %
                          (path, self.META_PRF))
            self.send_error(412, "HTTP Path does not start with %s" %
                            self.META_PRF)
            return None

        # Remove prefix and find location of first semicolon
        path = path[len(self.META_PRF):]
        if len(path) == 0:
            self.logerror("Path '%s' does not have characters after %s." %
                          (path, self.META_PRF))
            self.send_error(412, "HTTP Path ends after %s" %
                            self.META_PRF)
            return None

        dgstrt = path.find(";", 1)
        if dgstrt == -1:
            self.logerror("Path '%s' does not contain';' after %s." %
                          (path, self.META_PRF))
            self.send_error(412, "HTTP Path does not have ';' after %s" %
                            self.META_PRF)
            return None

        meta_path = "%s%s%s/%s" % (storage_root, META_DIR,
                                   path[:dgstrt], path[dgstrt+1:])
        self.logdebug("path %s converted to file name %s" % (path, meta_path))

        # Open file if it exists
        if not os.path.isfile(meta_path):
            self.loginfo("Request for non-existent metadata file '%s'." % self.path)
            self.send_error(404, "Metadata file for '%s' is not in cache" % self.path)
            return None
        try:
            f = open(meta_path, 'rb')
        except Exception, e:
            self.logerror("Unable to open metadata path '%s'" % meta_path)
            self.send_error(500, "Unable to open existing metadata file.")
            return None

        # Find out how big it is and generate headers
        try:
            f.seek(0, os.SEEK_END)
            file_len = f.tell()
            f.seek(0, os.SEEK_SET)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(file_len))
            self.end_headers()
        except:
            self.logerror("Unable to seek in metadata file '%s'" % meta_path)
            self.send_error(500, "Cannot seek in metadata file")
            f.close()
            f = None
        return f

    #--------------------------------------------------------------------------#
    def send_qrcode_header(self, path, storage_root):
        """
        @brief Send HTTP headers and set up for sending metadata file for GET
        request access to an HTTP URL starting ni_qrcode.
        @param path string pathname received with HTTP GET request
        @param storage_root string pathname of directory at the root of the cache tree
        @return file object pointing to StringIO containing image page with
                            embedded QRcode image data or None
        
        On entry the path format should be /ni_qrcode/<alg>;<digest>
        """
        if not path.startswith(self.QRCODE_PRF):
            self.logerror("Path '%s' does not start with %s." %
                          (path, self.QRCODE_PRF))
            self.send_error(412, "HTTP Path does not start with %s" %
                            self.QRCODE_PRF)
            return None

        # Remove prefix and find location of first semicolon
        path = path[len(self.QRCODE_PRF):]
        if len(path) == 0:
            self.logerror("Path '%s' does not have characters after %s." %
                          (path, self.QRCODE_PRF))
            self.send_error(412, "HTTP Path ends after %s" %
                            self.QRCODE_PRF)
            return None

        dgstrt = path.find(";", 1)
        if dgstrt == -1:
            self.logerror("Path '%s' does not contain';' after %s." %
                          (path, self.QRCODE_PRF))
            self.send_error(412, "HTTP Path does not have ';' after %s" %
                            self.QRCODE_PRF)
            return None

        alg_name = path[:dgstrt]
        dgst = path[dgstrt+1:] 
        meta_path = "%s%s%s/%s" % (storage_root, META_DIR,
                                   alg_name, dgst)
        self.logdebug("path %s converted to file name %s" % (path, meta_path))

        # Open file if it exists
        if not os.path.isfile(meta_path):
            self.loginfo("Request for QRcode for NDO '%s that is not cached here'." % self.path)
            self.send_error(404, "NDO for '%s' is not in cache" % self.path)
            return None

        # Reassemble ni name
        if ';' in dgst:
            # nih name
            ni_string = ("nih:/%s/%s" % (alg_name, dgst))
        else:
            # ni name
            ni_string = ("ni:///%s/%s" % (alg_name, dgst))

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
    def send_get_redirect(self, ni_name, meta_path):
        """
        @brief Redirect HTTP GET requests for URL http//<netloc>/.well-known/ni...
        @param ni_name NIname object corresponding to .well-known URL
        @param meta_path string expected metadata pathname corresponding to ni_name
        @return None (only headers are sent for redirect)

        Send a Temporary Redirect (HTTP response code 307) when a GET request
        for an HTTP URL with a path starting /.well-known/ni[h]/ is received.

        This is done because .well-known URLs are not supposed to return large
        amounts of data.
        """
        # Check if the metadata path corresponds to an actual file
        if not os.path.isfile(meta_path):
            self.loginfo("File does not exist: %s" % meta_path)
            self.send_error(404, "Requested file not in cache")
            return None

        self.send_response(307, "Redirect for .well-known version of '%s'" %
                           ni_name.get_url())
        self.send_header("Location", "http://%s%s%s;%s" % (self.server.authority,
                                                            self.CONT_PRF,
                                                            ni_name.get_alg_name(),
                                                            ni_name.get_digest()))
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
       
        The cache is a directory tree rooted at the location specified
        in self.server.storage_root with two parallel trees for NDO content
        and corresponding metadata.  Each tree in the cache has a directory per
        hash digest algorithm used to generate names using the names of the
        algorithms as directory names. (The main server program ensures
        that all relevant directories exist (or creates them) using the
        list of known algorithms retrieved from ni.NIname.get_all_algs().

        The corresponding content and metadata files share a name. The files in
        the cache are named using the url-safe base64 encoded
        digest used in ni: URIs or the hex encoding with check digit used in nih:
        URIs. (NOTE: There is a small probability of clashing names for truncated
        hashes.)

        When an NDO is published, generally, at least the metadata is provided.
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

        The paths derived from the HTTP PUBLISH requests do not require any
        fragment components, and only the NetInf publish operation might need
        a query string (for optional content type specification).  The
        paths are checked before being passed to the processing routines.
        
        """
        
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
        self.loginfo("Headers: %s" % str(self.headers))
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
        elif self.server.provide_nrs:
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
                raise ValueError
        elif self.path in [ self.NRS_CONF, self.NRS_LOOKUP,
                            self.NRS_DELETE, self.NRS_VALS ]:
            self.logerror("NRS request '%s' sent to server not providing NRS" %
                          self.path)
            self.send_error(404, "NetInf server is not providing NRS services")
            return
        else:
            # ... as above
            raise ValueError

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

        self.logdebug("/netinfproto/get: URI: '%s', msgid: '%s', 'ext': '%s'" %
                      (fov["URI"], fov["msgid"], fov["ext"]))

        # Generate NIname and validate it (it should have a Params field).
        ni_name = ni.NIname(form["URI"].value)
        rv = ni_name.validate_ni_url()
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni.ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni.ni_errs_txt[rv])
            return

        # Turn the ni_name into paths for NDO and metadata.
        # Then send the headers if all is well
        (ndo_path, meta_path) = self.ni_name_to_file_names(self.server.storage_root, ni_name)
        # send_get_header returns open file pointer to file to be returned (or None)
        f = self.send_get_header(ndo_path, meta_path, form["msgid"].value)
        if f:
            self.copyfile(f, self.wfile)
            f.close()
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
        ni_name = ni.NIname(form["URI"].value)
        rv = ni_name.validate_ni_url(has_params=True)
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni.ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni.ni_errs_txt[rv])
            return

        # Save netloc and query string (if any) so we can canonicalize ni_name
        # but setting netloc and query sting to empty string
        # Revalidate - should not cause any problems but...!
        netloc = ni_name.get_netloc()
        qs = ni_name.get_query_string()
        ni_name.set_netloc("")
        ni_name.set_query_string("")
        rv = ni_name.validate_ni_url(has_params=True)
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni.ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni.ni_errs_txt[rv])
            return

        # Turn the ni_name into NDO and metadata file paths
        (ndo_path, meta_path) = self.ni_name_to_file_names(self.server.storage_root,
                                                          ni_name)

        # We don't know what the content type or the length are yet
        ctype = None
        file_len = -1

        # If the form data contains an uploaded file...
        if file_uploaded:
            # Copy the file from the network to a temporary name in the right
            # subdirectory of the storage_root.  This makes it trivial to rename it
            # once the digest has been verified.
            # This file name is unique to this thread and because it has # in it
            # should never conflict with a digested file name which doesn't use #.
            temp_name = "%s%s%s/publish#temp#%d" % (self.server.storage_root,
                                                    NDO_DIR,
                                                    ni_name.get_alg_name(),
                                                    self.thread_num)
            self.logdebug("Copying and digesting to temporary file %s" % temp_name)

            # Prepare hashing mechanisms
            hash_function = ni_name.get_hash_function()()

            # Copy file from incoming stream and generate digest
            try:
                f = open(temp_name, "wb");
            except Exception, e:
                self.loginfo("Failed to open temp file %s for writing: %s)" % (temp_name, str(e)))
                self.send_error(500, "Cannot open temporary file")
                return
            file_len = 0
            g = form["octets"].file
            while 1:
                buf = g.read(16 * 1024)
                if not buf:
                    break
                f.write(buf)
                hash_function.update(buf)
                file_len += len(buf)
            f.close()
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
                digest = ni.NIproc.make_b64_urldigest(bin_dgst[:ni_name.get_truncated_length()])
                if digest is None:
                    self.logerror("Failed to create urlsafe base64 encoded digest")
                    self.send_error(500, "Failed to create urlsafe base64 encoded digest")
                    os.remove(temp_name)
                    return
            else:
                digest = ni.NIproc.make_human_digest(bin_dgst[:ni_name.get_truncated_length()])
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
                self.loginfo("Guessed content type from file is %s" % ctype)
            else:
                self.loginfo("Supplied content type from form is %s" % ctype)

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

        # Check if the metadata file exists - i.e., if this is an update
        if os.path.isfile(meta_path):
            # It does - had previous publish so update metadata
            # Routine
            # - checks canonicalized ni is the same as that in the metadata file
            # - checks file_len and ctype are consistent with existing values
            first_store = False
            (md, http_code, ret_str) = self.update_metadata(meta_path,
                                                            loc1, loc2,
                                                            ni_name.get_url(),
                                                            timestamp,
                                                            ctype, file_len,
                                                            extrameta)
            if md is None:
                # Log message already written
                self.send_error(http_code, ret_str)
                return

        else:
            # New metadata file needed
            first_store = True
            md = self.store_metadata(meta_path, loc1, loc2, ni_name.get_url(),
                                     timestamp, ctype, file_len, extrameta)
            if md is None:
                self.logerror("Unable to create metadata file %s" % meta_path)
                self.send_error(500, "Unable to create metadata file for %s" % \
                                ni_name.get_url())
                return

        # Check if the path corresponds to an actual content file
        if os.path.isfile(ndo_path):
            self.loginfo("Content file already exists: %s" % ndo_path)
            # Discarding uploaded copy if received
            if file_uploaded:
                try:
                    os.remove(temp_name)
                except Exception, e:
                    self.logerror("Failed to unlink temp file %s: %s)" %
                                 (temp_name, str(e)))
                    self.send_error(500, "Cannot unlink temporary file")
                    return
                    
            fs = os.stat(ndo_path)

            self.send_publish_report(rform, True, True, first_store, form,
                                     md, ni_name.get_url(), fs)

            return

        # We now know there is no preexisting content file...
        # If a file was uploaded...
        if file_uploaded:
            # Rename the temporary file to be the NDO content file name
            try:
                os.rename(temp_name, ndo_path)
            except:
                os.remove(temp_name)
                self.logerror("Unable to rename tmp file %s to %s: %s" %
                              (temp_name, ndo_path, str(e)))
                self.send_error(500, "Unable to rename temporary file")
                return

            fs = os.stat(ndo_path)

            self.send_publish_report(rform, True, False, first_store, form,
                                     md, ni_name.get_url(), fs)

            return

        # Otherwise report we just stored the metadata
        self.send_publish_report(rform, False, False, first_store, form,
                                 md, ni_name.get_url(), None)

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
            self.loginfo("Using default rform - json")                
        
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
            for sect in root.iter(tag=section_name):
                for item in sect.iter(tag=item_name):
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
            ni_name = ni.NIname((self.SRCH_CACHE_SCHM, "", self.SRCH_CACHE_DGST))
            # The validation should be a formality but has to be done
            # otherwise can't get hash function...
            rv = ni_name.validate_ni_url(has_params = False)
            if rv != ni.ni_errs.niSUCCESS:
                self.logerror("Validation of ni_name failed after setting digest: %s" %
                              ni.ni_errs_txt[rv])
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
            temp_name = "%s%s%s/search#temp#%d" % (self.server.storage_root,
                                                   NDO_DIR,
                                                   ni_name.get_alg_name(),
                                                   self.thread_num)
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
                digest = ni.NIproc.make_b64_urldigest(bin_dgst[:ni_name.get_truncated_length()])
                if digest is None:
                    self.logerror("Failed to create urlsafe base64 encoded digest for URL '%s'")
                    os.remove(temp_name)
                    continue
            else:
                digest = ni.NIproc.make_human_digest(bin_dgst[:ni_name.get_truncated_length()])
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
            if rv != ni.ni_errs.niSUCCESS:
                self.logerror("Validation of ni_name failed after setting digest: %s" %
                              ni.ni_errs_txt[rv])
                continue

            # Determine file names for metadata and content
            (ndo_path, meta_path) = self.ni_name_to_file_names(self.server.storage_root,
                                                              ni_name)

            # Check if metadata file exists already - then either store new or update
            if os.path.isfile(meta_path):
                # It does - had previous publish so update metadata
                first_store = False
                (md, http_code, ret_str) = self.update_metadata(meta_path,
                                                                url, None,
                                                                ni_name.get_url(),
                                                                timestamp,
                                                                ctype, file_len,
                                                                extrameta)
                if md is None:
                    # Log message already written
                    # Filing system (server) problems are terminal for search
                    if http_code >= 500:
                        self.send_error(http_code, ret_str)
                        return
                    
                    # Otherwise just don't include this item in results
                    continue
                    
            else:
                # New metadata file needed
                first_store = True
                md = self.store_metadata(meta_path, url, None, ni_name.get_url(),
                                         timestamp, ctype, file_len, extrameta)
                if md is None:
                    self.logerror("Unable to create metadata file %s" % meta_path)
                    continue

            # Check if content file exists - if not rename temp file; otherwise delete temp file
            if os.path.isfile(ndo_path):
                self.loginfo("Content file already exists: %s" % ndo_path)
                # Discarding uploaded temporary file
                try:
                    os.remove(temp_name)
                except Exception, e:
                    # This is fatal for this item - need to abort whole search
                    self.logerror("Failed to unlink temp file %s: %s)" % (temp_name, str(e)))
                    self.send_error(500, "Cannot unlink temporary file")
                    return
            else:
                # Rename the temporary file to be the NDO content file name
                try:
                    os.rename(temp_name, ndo_path)
                except:
                    # This is fatal for this item - need to abort whole search
                    os.remove(temp_name)
                    self.logerror("Unable to rename tmp file %s to %s: %s" % (temp_name, ndo_path, str(e)))
                    self.send_error(500, "Unable to rename temporary file")
                    return
                
            # FINALLY... record cached item ready to generate response
            item["ni_obj"]    = ni_name
            item["meta_path"] = meta_path
            item["ndo_path"]  = ndo_path
            item["metadata"]  = md
            cached_results.append(item)
            self.logdebug("Successfully cached URL '%s' as '%s'" % (url, ni_name.get_url()))

        self.logdebug("Finished caching results - %d items cached" % len(cached_results))
            
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
                ni_name.set_netloc(self.server.authority)
                cl = "http://%s%s%s/%s/%s" % (self.server.authority,
                                              self.WKN,
                                              ni_name.get_scheme(),
                                              ni_name.get_alg_name(),
                                              ni_name.get_digest())
                ml = "http://%s%s%s;%s" % (self.server.authority,
                                             self.META_PRF,
                                             ni_name.get_alg_name(),
                                             ni_name.get_digest())
                ql = "http://%s%s%s;%s" % (self.server.authority,
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
                ni_name.set_netloc(self.server.authority)
                cl = "http://%s%s%s/%s/%s" % (self.server.authority,
                                              self.WKN,
                                              ni_name.get_scheme(),
                                              ni_name.get_alg_name(),
                                              ni_name.get_digest())
                ml = "http://%s%s%s;%s" % (self.server.authority,
                                             self.META_PRF,
                                             ni_name.get_alg_name(),
                                             ni_name.get_digest())
                ql = "http://%s%s%s;%s" % (self.server.authority,
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
        self.wfile.write(f.read())
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
        fov = {}
        mandatory = ["URI"]
        optional = ["hint1", "hint2", "loc1", "loc2", "meta"]
        if not self.check_form_data(form, mandatory, optional, fov, "nrsconf"):
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
            if not self.server.nrs_redis.hmset(redis_key, redis_vals):
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
        self.wfile.write(f.read())
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
        
        self.send_response(200, "NRS Entry lookup for '%s' successful" % redis_key)
        self.send_header("MIME-Version", "1.0")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(length))
        self.send_header("Expires", self.date_time_string(time.time()+(24*60*60)))
        self.send_header("Last-Modified", self.date_time_string())
        self.end_headers()
        self.wfile.write(f.read())
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
            if not self.server.nrs_redis.delete(redis_key):
                self.loginfo("Deleting Redis entry for '%s' failed" % redis_key)
                self.send_error(404, "Deleting entry for key '%s' failed" % redis_key)
                return
        except Exception, e:
            self.logerror("Deleting Redis key '%s' caused exception %s" %
                          (redis_key, str(e)))
            self.send_error(412, "Deleting key in NRS database caused exception: %s" %
                            str(e))
            return

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
        self.wfile.write(f.read())
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
            key_list = self.server.nrs_redis.keys(redis_patt)
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
        self.wfile.write(f.read())
        f.close
          
        return

    #--------------------------------------------------------------------------#
    def store_metadata(self, meta_path, loc1, loc2, uri, timestamp,
                       ctype, file_len, extrameta):
        """
        @brief Create new metadata file for a cached NDO from form data etc
        @param meta_path string pathname for metadata file
        @param loc1 string locator #1 or None
        @param loc2 string locator #2 or None
        @param uri string canonicalized ni scheme URI for object being stored
        @param timestamp string when metadata created
        @param ctype string content type (maybe None if no uploaded file)
        @param file_len integer length of content file
                                (maybe None if no uploaded file)
        @param extrameta dictionary with optionally 'meta' key with values from 'ext'
               parameter, 'publish' key with value reflecting how published,
               'search' key with values describing how searched if relevant, or
               None.  May contain more in future.
        @return NetInfMetaData instance that was written to file or None if a problem

        The metadata file contains JSON encoded affiliated data created by writing
        a JSON encoded NetInfMetaData class instance to the file.

        Contract: The meta_path file does not exist on entry
        """

        try:
            f = open(meta_path, "w")
        except Exception, e:
            self.logerror("Unable to create metadata file %s: %s" % (meta_path, str(e)))
            return None

        # Always add this server's authority as a locator when creating metadata file
        md = NetInfMetaData(uri, timestamp, ctype, file_len,
                            self.server.authority, loc1, loc2, extrameta)
        try:
            json.dump(md.json_val(), f)
        except Exception, e:
            self.logerror("Write to metadata file %s failed: %s." % (meta_path, str(e)))
            md = None

        f.close()

        return md
    
    #--------------------------------------------------------------------------#
    def update_metadata(self, meta_path, loc1, loc2, uri,
                        timestamp, ctype, file_len, extrameta):
        """
        @brief Update existing metadata file for a cached NDO from form data etc
        @param meta_path string pathname for metadata file
        @param loc1 string locator #1 or None
        @param loc2 string locator #2 or None
        @param uri string ni scheme URI for metadata 
        @param timestamp string when metadata updated
        @param ctype string content type (maybe None if no uploaded file)
        @param file_len integer length of content file
                                (maybe None if no uploaded file)
        @param extrameta dictionary with optionally 'meta' key with values from 'ext'
               parameter, 'publish' key with value reflecting how published,
               'search' key with values describing how searched if relevant, or
               None.  May contain more in future.
        @return 3-tuple
                - NetInfMetaData instance that was written to file or
                  None if a problem
                - Suitable HTTP response code
                - "Success" or Error message for HTTP response

        The metadata file contains JSON encoded affiliated data created by writing
        a JSON encoded NetInfMetaData class instance to the file.

        Contract: The meta_path file exists on entry

        Check ni_uri is the same as embedded in metadata (this would be a
        server error as file name and uri should match).

        If ctype or file_len are not None, check that they are consistent
        with existing values
        """

        try:
            f = open(meta_path, "r+")
        except Exception, e:
            self.logerror("Unable to open metadata file %s: %s" % (meta_path, str(e)))
            return (None, 500, "Unable to open metadata file")

        # Create empty metadata object
        md = NetInfMetaData()
        try:
            if not md.set_json_val(json.load(f)):
                err_msg = "Metadata written by incompatible server version"
                self.logerror(err_msg)
                return (None, 500, err_msg)
        except Exception, e:
            self.logerror("Read from metadata file %s failed.", meta_path)
            return (None, 500, "Read from metadata file failed")
        
        f.seek(0)

        # Check that ni_uri is still correct - as this is related to the
        # file name, this would be some sort of server problem.
        if uri != md.get_ni():
            self.logerror("Update uses different URI - old: %s; new: %s" % \
                          (md.get_ni(), uri))
            return (None, 500, "Metadata update found inconsistent ni name")
        

        # Check for consistency of ctype and file_len if appropriate
        md_ct = md.get_ctype()
        if (ctype != None) and (md_ct != ""):
            if ctype != md_ct:
                f.close()
                self.loginfo("Update uses different content type - old: %s; new: %s" % \
                              (md_ct, ctype))
                return(None, 412, "Update uses different content type from exiating.")
        md_size = md.get_size()
        if (file_len != None) and (md_size != -1):
            if file_len != md_size:
                f.close()
                self.loginfo("Update file has different size - old: %s; new: %s" % \
                              (md_size, file_len))
                return (None, 412, "Update file has differen length from exiating.")

        # Update info in metadata structure and set content type if appropriate
        # No need to write the authority again.
        md.add_new_details(timestamp, None, loc1, loc2, extrameta)
        md.set_size(file_len)
        md.set_ctype(ctype)

        # Write metadata back to file
        try:
            json.dump(md.json_val(), f)
        except Exception, e:
            self.logerror("Write to metadata file %s failed.", meta_path)
            f.close()
            return (None, 500, "Write to metadata file failed")

        f.close()        
        return (md, 200, "success")

    #--------------------------------------------------------------------------#
    def send_publish_report(self, rform, ndo_in_cache, ignored_upload,
                            first_store, form, metadata, ni_uri, content_fileinfo):
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
        @param content_fileinfo 10-tuple as returned by os.stat for NDO content
                                         file or None
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
        # Check parameter consistency
        if (content_fileinfo == None):
            if ndo_in_cache:
                self.logerror("Coding fault: Must have ndo_status if in cache: %s." %
                              ni_uri)
            file_length = "(unknown)"
        else:
            file_length = str(content_fileinfo[stat.ST_SIZE])
            
        # Format information strings to be used in report and set status
        # info1 is used in the HTML and plain text report bodies
        # info2 is the message send with the HTTP response type message
        if ndo_in_cache and ignored_upload:
            info1 = ("File %s is already in cache as '%s' (%s octets);" + \
                    " metadata updated.") % (form["octets"].filename,
                                             ni_uri,
                                             file_length)
            info2 = "Object already in cache; metadata updated."
            status = 202
        elif ndo_in_cache and first_store:
            info1 = ("File %s and metadata stored in new cache entry" + \
                     " as '%s' (%s octets)") % (form["octets"].filename,
                                                ni_uri,
                                                file_length)
            info2 = "Object and metadata cached."
            status = 201
        elif ndo_in_cache:
            info1 = ("File %s stored in cache and metadata updated" + \
                     " as '%s' (%s octets)") % (form["octets"].filename,
                                                ni_uri,
                                                file_length)
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

            
        # Select response format and construct body in a StringIO pseudo-file
        f = StringIO()
        if rform == "json":
            # JSON format: Metadata as JSON string        
            ct = "application/json"
            rd = metadata.summary()
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
        self.wfile.write(f.read())
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
        """
        split_query_frag = path.split("?", 1)
        if len(split_query_frag) > 1:
            has_query_string = True
            split_frag = split_query_frag[1].split("#", 1)
        else:
            has_query_string = False
            split_frag = split_query_frag[0].split("#", 1)
        has_fragments = (len(split_frag) > 1)

        return (has_query_string, has_fragments)

    #--------------------------------------------------------------------------#
    def ni_name_to_file_names(self, storage_root, ni_name):
        """
        @brief make basic pathname for ni_name in object cache
        @param storage_root string root of directory tree for object cache
        @param ni_name NIname instance encoding ni: scheme URL
        @return pathnames for NDO (content) and metadata files 

        Generate 2-tuple of
        <storage root>/ndo_dir/<hash alg identifier>/<digest>
        and
        <storage root>/meta_dir/<hash alg identifier>/<digest>
        """
        ndo_name =  "%s%s%s/%s" % (storage_root,
                                   NDO_DIR,
                                   ni_name.get_alg_name(),
                                   ni_name.get_digest())
        meta_name =  "%s%s%s/%s" % (storage_root,
                                   META_DIR,
                                   ni_name.get_alg_name(),
                                   ni_name.get_digest())
        return (ndo_name, meta_name)


    #--------------------------------------------------------------------------#
    def redirect_name_to_file_names(self, storage_root, redirect_name):
        """
        @brief Make file pathnames in object cache for the path from a redirected content URL  
        @param storage_root string root of directory tree for object cache
        @param redirect_name string path as supplied to redirect for ni: .well-known name
        @return pathnames for NDO content file and metadata file

        If the client uses the HTTP .well-known/ni[h] URL to access an NDO,
        the server responds with a 307 - Redirect indicating the location to be
        accessed. The URL for this location is of the form:
        http://<netloc>/ni_cache/<alg name>;<digest>

        This method converts such a redirect location to cache filenames, i.e.,<br/>
        <storage root>/[ndo_dir|meta_dir]/<redirect_name less CONT_PRF prefix><br/>
        with ';' between <alg name> and <digest> replaced by '/'.
        
        e.g., convert HTTP path:<br/>
        /ni_cache/sha-256-32;81fdb284;d<br/>
        to file path<br/>
        /<storage root>/ndo_dir/sha-256-32/81fdb284;d
        """
        ndo_name =  "%s%s%s" % (storage_root,
                                NDO_DIR,
                                redirect_name[len(self.CONT_PRF):].replace(";", "/", 1))
        meta_name =  "%s%s%s" % (storage_root,
                                 META_DIR,
                                 redirect_name[len(self.CONT_PRF):].replace(";", "/", 1))
        return (ndo_name, meta_name)


    #--------------------------------------------------------------------------#
    def translate_wkn_path(self, authority, storage_root, path):
        """
        @brief Translate a /-separated .well-known PATH to a ni_name and the local
        filename syntax. 
        @param the FQDN of this node used to build ni name
        @param the root of the directory tree where ni Named Data Objects are cached
        @param the path from the HTTP request
        @retval 4-tuple: (niSUCCESS, NIname instance, NDO path, metadata path) on success
        @retval 4-tuple: (error code from ni_errs, None, None, None) if errors found.

        The path is expected to have the form:
        /.well-known/ni[h]/<digest name>/<encoded digest>[?<query]
        Method strips off the '/.well-known/ni[h]' prefix and builds
        an NIname object corresponding to the http: form. Validates the
        form of the ni[h] name and then builds it into a pair of local file names
        corresponding to the content and metafile locations.

        The return value is a 4-tuple consisting of:
         - return code taken form ni.ni_errs_txt
         - ni URI:        ni://<authority>/<digest name>;<url encoded digest>[?<query]
           <br/>or<br/>
           nih URI:       nih:/<digest name>;<hex encoded digest>
         - NDO filename:  <storage_root>/ndo_dir/<digest name>;<url encoded digest>
         - META filename:<storage_root>/meta_dir/<digest name>;<url encoded digest>

        If the return code is not niSUCCESS, the other three members are None. 
        """

        # Note: 'path' will not contain query or fragment components
        # Must do nih first as ni is a substring of nih!
        if path.startswith(self.NIH_HTTP):
            path = path[len(self.NIH_HTTP):]
            if (len(path) == 0) or not path.startswith("/"):
                return (ni.ni_errs.niBADURL, None, None, None)
            # This should locate the division between algorithm and digest
            dgstrt = path.find("/", 1)
            if dgstrt == -1:
                return (ni.ni_errs.niBADURL, None, None, None)
                
            url = "nih:%s;%s" % (path[:dgstrt], path[dgstrt+1:])
            self.logdebug("path %s converted to url %s" % (path, url))
        elif path.startswith(self.NI_HTTP):
            path = path[len(self.NI_HTTP):]
            if (len(path) == 0) or not path.startswith("/"):
                return (ni.ni_errs.niBADURL, None, None, None)
            # This should locate the division between algorithm and digest
            dgstrt = path.find("/", 1)
            if dgstrt == -1:
                return (ni.ni_errs.niBADURL, None, None, None)
                
            url = "ni://%s%s;%s" % (authority, path[:dgstrt], path[dgstrt+1:])
            self.logdebug("path %s converted to url %s" % (path, url))
        else:
            self.logdebug("path '%s' does not start with %s or %s" % (path,
                                                                      self.NI_HTTP,
                                                                      self.NIH_HTTP))
            return (ni.ni_errs.niBADURL, None, None, None)
        
        ni_name = ni.NIname(url)
        rv = ni_name.validate_ni_url()
        if (rv != ni.ni_errs.niSUCCESS):
            return (rv, None, None, None)
        (ndo_path, meta_path) = self.ni_name_to_file_names(storage_root, ni_name)
        self.logdebug("NI URL: %s, NDO storage path: %s" % (url, ndo_path))

        return (ni.ni_errs.niSUCCESS, ni_name, ndo_path, meta_path)

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
            loc2 = form["loc1"].value
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
            all_vals = self.server.nrs_redis.hgetall(redis_key)
        except Exception, e:
            return None

        if len(all_vals) == 0:
            return None
        
        try:
            vals = self.server.nrs_redis.hmget(redis_key, val_names)
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
    def copyfile(self, source, outputfile):
        """
        @brief Copy all data between two file objects.

        @param source file object open for reading
                          (or anything with a read() method)
        @param outputfile file object open for writing
                              (or anything with a write() method).
        @return void
        
        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        """
        shutil.copyfileobj(source, outputfile)
        return

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
    the NIHTTPHandler class that processes the requests that come in on this
    connection.

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
    # object StrictRedis instance used for communication between the NRS server and the Redis database.
    ##@var thread_running_lock
    # object Lock instance used to serialize access to running_threads and next_handler_num
    ##@var running_threads
    # set contains NIHTTPHandler instances that are associated with the current running threads.
    ##@var next_handler_num
    # integer initialized to 0, incremented by one whenever a handler thread is created,
    # and the previous value used as part of the name for the thread.
    ##@var allow_reuse_address
    # boolean (from TCPServer) if set, when the listener socket is bound to the server
    # address, the ioctl SO_REUSEADDR is called on the socket before being bound.This is
    # handy especially during development as otherwise you have to wait for a
    # significant period (typically at least 4 minutes) while the TIME_WAIT state
    # on the socket from a previous instance terminates before the server can be
    # restarted using the same (address, port) pair.
    ##@var daemon_threads
    # boolean set to make all the spawned handler threads are made daemon threads. This
    # means that the handler threads are terminated when the main thread terminates.

    #--------------------------------------------------------------------------#
    def __init__(self, addr, storage_root, authority, logger,
                 getputform, nrsform, provide_nrs, favicon):
        """
        @brief Constructor for the NI HTTP threaded server.
        @param addr tuple two elements (<IP address>, <TCP port>) where server listens
        @param storage_root string pathname for root of cache directory tree
        @param authority string combination of server FQDN and server port as URL 'netloc' 
        @param logger object logger instance to output messages
        @param getputform string pathname of GET/PUBLISH/SEARCH form HTML file
        @param nrsform string pathname of NRS configuration form HTML file
        @param provide_nrs boolean True if server is to offer NRS server function
        @param favicon string pathname for browser favicon.ico icon file
        @return (none)

        Save the parameters (except for addr) as instance variables.
        These values can be accessed from the NIHTTPHandler class instance
        that is created to handle each incoming connection to the server.
        These handler instances run in separate threads on account of the
        ThreadingMixIn.  The server maintains a list of active threads
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
        
        """
        # These are used  by individual requests
        # accessed via self.server in the handle function
        self.storage_root = storage_root
        self.authority = authority
        self.logger = logger
        self.getputform = getputform
        self.nrsform = nrsform
        self.provide_nrs = provide_nrs
        self.favicon = favicon

        # If an NRS server is wanted, create a Redis client instance
        # Assume it is the default local_host, port 6379 for the time being
        if provide_nrs:
            try:
                self.nrs_redis = redis.StrictRedis()
            except Exception, e:
                logger.error("Unable to connect to Redis server: %s" % str(e))
                sys.exit(-1)
        
        self.running_threads = set()
        self.next_handler_num = 1
        # Lock for serializing access to running_threads and next_handler_num
        self.thread_running_lock = threading.Lock()

        # Setup to produce a daemon thread for each incoming request
        # and be able to reuse address
        HTTPServer.__init__(self, addr, NIHTTPHandler,
                            bind_and_activate=False)
        self.allow_reuse_address = True
        self.server_bind()
        self.server_activate()
                         
        self.daemon_threads = True

    #--------------------------------------------------------------------------#
    def add_thread(self, thread):
        """
        @brief Record a new handler thread resulting from a server connection.
        @param thread object NIHTTPHandler instance instantiated to handle connection.
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
        @param thread object NIHTTPHandler instance instantiated to handle connection.
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
        self.shutdown()

#==============================================================================#
# EXPORTED GLOBAL FUNCTIONS
#==============================================================================#
def check_cache_dirs(storage_root, logger):
    """
    @brief Check existence of object cache directories and create if necessary
    @param storage_root string pathname of root directory of storage tree
    @param logger object logger instance to output messages
    @retval True  cache tree exists ready for use
    @retval False there is a problem somewhere - see log for details

    The storage_root directory has to be created and writeable before
    starting the server.

    For the rest of the tree, directories will be created if they do not exist.

    TO DO: check they are readable, writeable and searchable if they exist.
    """
    if not os.path.isdir(storage_root):
        logger.error("Storage root directory %s does not exist." % storage_root)
        return False
    for tree_name in (NDO_DIR, META_DIR):
        tree_root = "%s%s" % (storage_root, tree_name)
        if not os.path.isdir(tree_root):
            logger.info("Creating object cache tree directory: %s" % tree_root)
            try:
                os.mkdir(tree_root, 0755)
            except Exception, e:
                logger.error("Unable to create tree directory %s : %s." % \
                             (tree_root, str(e)))
                return False
        for auth_name in ni.NIname.get_all_algs():
            dir_name = "%s%s" % (tree_root, auth_name)
            if not os.path.isdir(dir_name):
                logger.info("Creating object cache directory: %s" % dir_name)
                try:
                    os.mkdir(dir_name, 0755)
                except Exception, e:
                    logger.error("Unable to create cache directory %s : %s." % \
                                 (dir_name, str(e)))
                    return False
    return True
    
#------------------------------------------------------------------------------#
def ni_http_server(storage_root, authority, server_port, logger,
                   getputform, nrsform, provide_nrs, favicon):
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

    if provide_nrs:
        if not redis_loaded:
            logger.error("Unable to import redis module needed for NRS server")
            sys.exit(-1)
        logger.info("Successfully loaded redis module for NRS server")

    # Pass the parameters and the derived IP address to the constructor
    return NIHTTPServer((ipaddr, server_port), storage_root,
                         "%s:%d" % (authority, server_port),
                        logger, getputform, nrsform,
                        provide_nrs, favicon)

#==============================================================================#

#==============================================================================#
# TESTING CODE
#==============================================================================#
if __name__ == "__main__":
    #==== TEST FUNCTIONS ====
    def test_client(my_host, my_port, ip, port, message):
        """
        @brief Simulate an HTTP client - push message to niserver
        @param my_host string hostname where client is running
        @param port integer port to use for client
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

        server = NIHTTPServer((HOST, PORT), sd, "example.com", logger,
                              "./getputform.html", "./nrsconfig.html",
                              False, "./favicon.ico")

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
        
