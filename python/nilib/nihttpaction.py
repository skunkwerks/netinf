#!/usr/bin/python
"""
@package nilib
@file nigetlist.py
@brief Command line client to perform a NetInf 'get' operation on a list of files.
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
To send 'get' requests to a server to retrieve a whole list of files.


@code
Revision History
================
Version   Date       Author         Notes
1.0	  14/01/2012 Elwyn Davies   Created using niget.py as template.
                                    Incorporate use of feedparser to
@endcode
"""
import sys
from types import *
import os.path
import  random
from optparse import OptionParser
import urllib
import urllib2
import magic
import json
import email.parser
import email.message
import time
import platform
import multiprocessing
from itertools import chain
from threading import Thread, Event, Timer
from threading import Lock as ThreadingLock
from os.path import join
import tempfile
import logging
import Queue
import StringIO

from redis import StrictRedis

from ni import ni_errs, ni_errs_txt, NIname, NIproc, NIdigester
from nifeedparser import DigestFile, FeedParser
from nidtnevtmsg import HTTPRequest, MsgDtnEvt
from metadata import NetInfMetaData
from ni_exception import NoCacheEntry
from nidtnbpq import BPQ
from encode import *
import streaminghttp

timeout_test = False 
#============================================================================#
# === Routines Executed in Asynchronous Multiprocess

# === GLOBAL VARIABLES ===

##@var process_logger
# instance of logger object used for logging in synchronous processes 
process_logger= None

#===============================================================================#
verbose = True
def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    if verbose:
        process_logger.debug(string)
    return

#------------------------------------------------------------------------------#
def nilog(string):
	"""
	@brief Log the node, time, and the string
	@param string to be printed (in)
	"""
	node=platform.node()
	now=time.time() 
	nano= "%.10f" %now
	utct = time.strftime("%Y-%m-%dT%H:%M:%S")
	
	process_logger.info('NILOG: ' + node + ',' + nano + ',' + utct + ',' + string)
	
	return

#------------------------------------------------------------------------------#
def get_req(req_id, ni_url, http_host, http_index, form_params,
            file_name, tempdir):
    """
    @brief Perform a NetInf 'get' from the http_host for the ni_url.
    @param req_id integer sequence number of message containing request
    @param ni_url object instance of NIname with ni name to be retrieved
    @param http_host string HTTP host name to be accessed
                            (FQDN or IP address with optional port number)
    @param http_index integer index of host name being processed within request
    @param form_params dictionary of paramter values to pass to HTTP
    @param file_name string file name of content to be published or None
    @param tempdir string ditrectory where to place retrieved content if any
    @return 5-tuple with:
                boolean - True if succeeds, False if fails
                string req_id as supplied as parameter
                integer http_index as supplied as parameter
                string pathname for content file/response or None is no content etc
                dictionary returned JSON metadata if any, decoded
                
    Assume that ni_url has a valid ni URI
    Assume that tempdir provides a directory path into which file can be written
    """

    # Record start time
    stime= time.time()
    
    # Must be a complete ni: URL with non-empty params field
    rv = ni_url.validate_ni_url(has_params = True)
    if (rv != ni_errs.niSUCCESS):
            nilog("Error: %s is not a complete, valid ni scheme URL: %s" % (ni_url.get_url(), ni_errs_txt[rv]))
            return(False, req_id, http_index, None, None)

    # Generate NetInf form access URL
    ni_url_str = ni_url.get_canonical_ni_url()
    
    # Generate NetInf form access URL
    http_url = "http://%s/netinfproto/get" % http_host
    
    # Set up HTTP form data for get request
    form_data = urllib.urlencode({ "URI":   ni_url_str,
                                   "msgid": form_params["msgid"],
                                   "ext": "" if not form_params.has_key("ext") else
                                          form_params["ext"]})

    # Send POST request to destination server
    try:
        http_object = urllib2.urlopen(http_url, form_data)
    except Exception, e:
        nilog("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        return(False, req_id, http_index, None, None)

    # Get HTTP result code
    http_result = http_object.getcode()

    # Get message headers - an instance of email.Message
    http_info = http_object.info()
    debug("Response type: %s" % http_info.gettype())
    debug("Response info:\n%s" % http_info)

    if (http_result != 200):
        nilog("Get request returned HTTP code %d" % http_result)
        buf = http_object.read()
        debug("HTTP Response: %s" % buf)
        http_object.close()
        return (False, ni_url_str)

    obj_length_str = http_info.getheader("Content-Length")
    if (obj_length_str != None):
        obj_length = int(obj_length_str)
    else:
        obj_length = None

    # The results may be either:
    # - a single application/json MIME item carrying metadata of object
    # - a two part multipart/mixed object with metadats and the content (of whatever type)
    # Parse the MIME object

    primer = "Content-Type: %s\r\n\r\n" % http_object.headers["content-type"]
    fd, digested_file = tempfile.mkstemp(dir=tempdir)
    fo = os.fdopen(fd, "w")
    debug("Writng content to %s" % digested_file)

    digester = DigestFile(digested_file, fo, ni_url.get_hash_function())

    # Expecting up to three MIME message objects
    # - Top level multipart/mixed,
    # - application/json with metadata, and
    # - any type for content file
    # In dest_list, None results in output being written to a StringIO buffer
    # Other not None items should be filelike objects that can be written to. 
    # If there is only metadata than first ones will cover it
    msg_parser = FeedParser(dest_list=[None, None, digester])

    # Grab and digest the HTTP response body in chunks
    msg_parser.feed(primer)
    payload_len = 0
    blk_size = 4096
    while True:
        buf = http_object.read(blk_size)
        if len(buf) == 0:
            break
        msg_parser.feed(buf)
        payload_len += len(buf)
    
    msg = msg_parser.close()
    http_object.close()

    if len(msg.defects) > 0:
        nilog("Response was not a correctly formed MIME object")
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)
    # Verify length 
    if ((obj_length != None) and (payload_len != obj_length)):
        nilog("Warning: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)
        
    debug( msg.__dict__)
    # If the msg is multipart this is a list of the sub messages
    parts = msg.get_payload()
    debug("Multipart: %s" % str(msg.is_multipart()))
    if msg.is_multipart():
        debug("Number of parts: %d" % len(parts))
        if len(parts) != 2:
            nilog("Error: Response from server does not have two parts.")
            os.remove(digested_file)
            return(False, req_id, http_index, None, None)
        json_msg = parts[0]
        ct_msg = parts[1]
    else:
        debug("Return is single part")
        json_msg = msg
        ct_msg = None

    # Extract JSON values from message
    # Check the message is a application/json
    debug(json_msg.__dict__)
    if json_msg.get("Content-type") != "application/json":
        nilog("First or only component (metadata) of result is not of type application/json")
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)

    # Extract the JSON structure
    try:
        json_report = json.loads(json_msg.get_payload())
    except Exception, e:
        nilog("Error: Could not decode JSON report '%s': %s" % (json_msg.get_payload(),
                                                                    str(e)))
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)
    
    debug("Returned metadata for %s:" % ni_url_str)
    debug(json.dumps(json_report, indent = 4))

    msgid = json_report["msgid"]
    if msgid != form_params["msgid"]:
        nilog("Returned msgid (%s) does not match request msgid (%s)" %
              (msgid, form_params["msgid"]))
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)

    # If the content was also returned..
    if ct_msg != None:
        debug(ct_msg.__dict__)
        digest= digester.get_digest()[:ni_url.get_truncated_length()]
        digest = NIproc.make_b64_urldigest(digest)
                                          
        # Check the digest
        #print digest, ni_url.get_digest()
        if (digest != ni_url.get_digest()):
            nilog("Digest of %s did not verify" % ni_url.get_url())
            os.remove(digested_file)
            return(False, req_id, http_index, None, None)
        etime = time.time()
        duration = etime - stime
        nilog("%s,GET rx fine,ni,%s,size,%d,time,%10.10f" %
              (msgid, ni_url_str, obj_length, duration*1000))
    else:
        # Clean up unused temporary file
        os.remove(digested_file)
        digested_file = None

    return(True, req_id, http_index, digested_file, json_report)
        
#------------------------------------------------------------------------------#
def publish_req(req_id, ni_url, http_host, http_index, form_params,
                file_name, tempdir):
    """
    @brief Perform a NetInf 'publish' towards the http_host for the ni_url.
    @param req_id integer sequence number of message containing request
    @param ni_url object instance of NIname with ni name to be retrieved
    @param http_host string HTTP host name to be accessed
                            (FQDN or IP address with optional port number)
    @param http_index integer index of host name being processed within request
    @param form_params dictionary of paramter values to pass to HTTP
    @param file_name string file name of content to be published or None
    @param tempdir string ditrectory where to place retrieved content if any
    @return 5-tuple with:
                boolean - True if succeeds, False if fails
                string req_id as supplied as parameter
                integer http_index as supplied as parameter
                string actual response or None is no response etc
                dictionary returned JSON metadata if any, decoded
                
    Assume that ni_url has a valid ni URI
    Assume that tempdir provides a directory path into which file can be written
    """

    # Where to send the publish request.
    http_url = "http://%s/netinfproto/publish" % http_host
    debug("Publishing via: %s" % http_url)

    # Handle full_put = True cases - we have a file with the octets in it
    full_put = (file_name is not None)
    if full_put:
        # Create NIdigester for use with form encoder and StreamingHTTP
        ni_digester = NIdigester()

        # Install the template URL built from the scheme, the nttp_host and
        # the digest algorithm
        scheme = ni_url.get_scheme()
        hash_alg = ni_url.get_alg_name()
        rv = ni_digester.set_url((scheme, http_host, "/%s" % hash_alg))
        if rv != ni_errs.niSUCCESS:
            nilog("Cannot construct valid ni URL: %s" % ni_errs_txt[rv])
            return(False, req_id, http_index, None, None)
        debug(ni_digester.get_url())

        # Open the file if possible
        try:
            f = open(file_name, "rb")
        except Exception, e :
            nilog("Unable to open file %s: Error: %s" % (file_name, str(e)))
            return(False, req_id, http_index, None, None)

        # If we don't know content type, guess it
        if form_params.has_key("ct"):
            ctype = form_params["ct"]
        else:
            # Guess the mimetype of the file
            m = magic.Magic(mime=True)
            ctype = m.from_file(file_name)
            debug("Content-Type: %s" % ctype)
            if ctype is None:
                # Guessing didn't work - default
                ctype = "application/octet-stream"

        # Set up HTTP form data for publish request
        # Make parameter for file with digester
        octet_param = MultipartParam("octets",
                                     fileobj=f,
                                     filetype=ctype,
                                     filename=file_name,
                                     digester = ni_digester)
        # Make dictionary that will dynamically retrieve ni URI when it has been made
        uri_dict = { "generator": octet_param.get_url,
                     "length": (len(ni_digester.get_url()) + len(";") +
                                ni_digester.get_b64_encoded_length())}

        rform = form_params.get("rform", "json")
        param_list = [octet_param,
                      ("URI",       uri_dict),
                      ("msgid",     form_params["msgid"]),
                      ("ext",       form_params["ext"]),
                      ("fullPut",   "yes"),
                      ("rform",     rform),
                      ("loc1",      form_params.get("loc1", "")),
                      ("loc2",      form_params.get("loc2", ""))]
    else:
        # full_put = False case
        # No need for complicated multipart parameters
        param_list = [("URI",       ni_name.get_url()),
                      ("msgid",     form_params["msgid"]),
                      ("ext",       form_params["ext"]),
                      ("fullPut",   "no"),
                      ("rform",     rform),
                      ("loc1",      form_params.get("loc1", "")),
                      ("loc2",      form_params.get("loc2", ""))]
        
    # Construct data generator and header strings
    datagen, headers = multipart_encode(param_list)

    #debug("Parameters prepared: %s"% "".join(datagen))
    debug("Parameters prepared")

    # Set up streaming HTTP mechanism - register handlers with urllib2
    opener = streaminghttp.register_openers()
                                         
    # Send POST request to destination server
    try:
        req = urllib2.Request(http_url, datagen, headers)
    except Exception, e:
        nilog("Error: Unable to create request for http URL %s: %s" %
              (http_url, str(e)))
        if full_put:
            f.close()
        return(False, req_id, http_index, None, None)

    # Get HTTP results
    try:
        http_object = urllib2.urlopen(req)
    except Exception, e:
        nilog("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        if full_put:
            f.close()
        return(False, req_id, http_index, None, None)

    if full_put:
        f.close()
        target = octet_param.get_url()
    else:
        target = ni_name.get_url()
    debug("Sent request: URL: %s" % target)


    # Get message headers
    http_info = http_object.info()
    http_result = http_object.getcode()
    nilog("HTTP result: %d" % http_result)
    debug("Response info: %s" % http_info)
    debug("Response type: %s" % http_info.gettype())

    # Read results into buffer
    payload = http_object.read()
    http_object.close()
    debug(payload)

    # Report outcome
    if (http_result != 200):
        nilog("Unsuccessful publish request returned HTTP code %d" %
              http_result) 
        return(False, req_id, http_index, None, None)

    # Check content type of returned message matches requested response type
    ct = http_object.headers["content-type"]
    if rform == "plain":
        if ct != "text/plain":
            nilog("Error: Expecting plain text (text/plain) response "
                  "but received Content-Type: %s" % ct)
        return(False, req_id, http_index, None, None)
    elif rform == "html":
        if ct != "text/html":
            nilog("Error: Expecting HTML document (text/html) response "
                  "but received Content-Type: %s" % ct)
    else:
        if ct != "application/json":
            nilog("Error: Expecting JSON coded (application/json) "
                  "response but received Content-Type: %s" % ct)
            return(False, req_id, http_index, None, None)
    """
    try:
        fd, response_file = tempfile.mkstemp(dir=tempdir)
        fo = os.fdopen(fd, "wb")
        fo.write(payload)
        fo.close()
    except Exception, e:
        nilog("Writing response to temp file %s failed: %s" %
              (response_file, str(e)))
        return(False, req_id, http_index, None, None)
    debug("Written response to %s" % response_file)
    """
    return(True, req_id, http_index, payload, None)

#------------------------------------------------------------------------------#
def search_req(req_id, ni_url, http_host, http_index, form_params,
               file_name, tempdir):
    """
    @brief Perform a NetInf 'search' on the http_host using the form_params.
    @param req_id integer sequence number of message containing request
    @param ni_url None for earch requests
    @param http_host string HTTP host name to be accessed
                            (FQDN or IP address with optional port number)
    @param http_index integer index of host name being processed within request
    @param form_params dictionary of paramter values to pass to HTTP
    @param file_name string file name of content to be published or None
    @param tempdir string ditrectory where to place retrieved response if any
    @return 5-tuple with:
                boolean - True if succeeds, False if fails
                string req_id as supplied as parameter
                integer http_index as supplied as parameter
                string actual response or None is no response etc
                dictionary returned JSON metadata if any, decoded
                
    Assume that ni_url has a valid ni URI
    Assume that tempdir provides a directory path into which file can be written
    """

    return(False, req_id, http_index, None, None)

#------------------------------------------------------------------------------#
def action_req(req_type, req_id, ni_url, http_host, http_index, form_params,
               file_name, tempdir):
    """
    @brief Switch to correct proceeing routine for req_type
    @param req_type string HTTP_GET, HTTP_PUBLISH or HTTP_SEARCH from HTTPRequest
    @param req_id integer sequence number of message containing request
    @param ni_url NIname object instance with ni URI to be retrieved or
                                         published or None (search case)
    @param http_host string HTTP host name to be accessed
    @param http_index integer index of host name being processed within request
    @param form_params dictionary of paramter values to pass to HTTP
    @param file_name string file name of content to be published or None
    @param tempdir string where to place retrieved data
    @return 5-tuple with:
                boolean - True if succeeds, False if fails
                string req_id as supplied as parameter
                integer http_index as supplied as parameter
                string pathname for content file or response or None is no content etc
                dictionary returned JSON metadata if any, decoded
                
    Requests translated from DTN bundles to be actioned by HTTP CL are
    funneled through this routine to simplify the multi-process interface.
    The result is a tuple that is fed back to the callback routine when using
    multiprocessing implementation allowing the result to be linked to the
    original request.
    """
    nilog("Entering action_req %s: id %s http index %d" %
          (req_type, req_id, http_index))
    try:
        req_rtn = {HTTPRequest.HTTP_GET: get_req,
                   HTTPRequest.HTTP_PUBLISH: publish_req,
                   HTTPRequest.HTTP_SEARCH: search_req}[req_type]
    except:
        nilog("Bad req_type (%s) supplied to action_req" % req_type)
        return(False, req_id, http_index, None, None)

    try:
        rv = req_rtn(req_id, ni_url, http_host, http_index,
                       form_params, file_name, tempdir)
        print rv
        return rv
    except Exception, e:
        nilog("Exception occurred while processing (%s, %s, %d): %s" %
              (req_type, req_id, http_index, str(e)))
        return(False, req_id, http_index, None, None)

#===============================================================================#

class HTTPAction(Thread):
    """
    @brief Manager for sending requests over HTTP CL originated from DTN

    @detail
    Reads a queue of requests from the DTN receive thread and farms them
    out to subsidiary routine to carry out each request using the HTTP
    CL.  The name of the host to use 

    The individual requests can be carried out in sub-processes in parallel
    if the 'multi' parameter to the constructor is True.  Otherwise the
    actions are carried out in series.

    When an action completes, the manager sends a message to the DTN sender
    thread which encapsulates it into bundle and injects back into the DTN
    """
    HTTP_SCHEME_PREFIX = "http://"
    DTN_SCHEME_PREFIX = "dtn://"
    
    # === Logging convenience functions, etc ===
    ##@var logger
    # object instance of Logger object configured by NIHTTPServer
    
    ##@var loginfo
    # Convenience function for logging informational messages
    
    ##@var logdebug
    # Convenience function for logging debugging messages
    
    ##@var logwarn
    # Convenience function for logging warning messages
    
    ##@var logerror
    # Convenience function for logging error reporting messages
    
    #--------------------------------------------------------------------------#
    def __init__(self, resp_q, tempdir, logger, redis_conn, ndo_cache,
                 mprocs=1, parallel_limit=1, per_req_limit=1):
        """
        @brief Constructor - set up logging and squirrel parameters
        """
        Thread.__init__(self, name="http-action")
        # Logging functions
        global process_logger
        process_logger = logger
        self.logger = logger
        self.loginfo = logger.info
        self.logdebug = logger.debug
        self.logwarn = logger.warn
        self.logerror = logger.error

        self.resp_q = resp_q
        self.tempdir = tempdir
        self.ndo_cache = ndo_cache
        self.mprocs = mprocs
        if parallel_limit > mprocs:
            self.parallel_limit = mprocs
            self.logwarn("Limiting parallel processing to %d (parallel_limit %d)" %
                         (mprocs, parallel_limit))
        else:
            self.parallel_limit = parallel_limit
        
        self.per_req_limit = per_req_limit
        
        # Keep running indicator
        self.keep_running = True

        # Set up multiprocessing if mprocs > 1
        if mprocs > 1:
            # Generate a pool of mprocs worker processes
            self.logdebug("HTTP action running in multiprocess mode")
            self.multi = True
            self.pool = multiprocessing.Pool(mprocs)
        else:
            self.logdebug("HTTP action running in single process mode")
            self.multi = False
            self.pool = None

        # Initialize records of work in progress
        self.curr_reqs = []
        self.req_dict = {}
        
        # Number of running asynchronous processes when using multiprocessing
        self.running_procs = 0
        
        # Provide lock to control access to curr_reqs and process count
        self.reqs_lock = ThreadingLock()

        # Event indicating that there is something to be done
        self.action_needed = Event()
        self.action_needed.clear()
        
       # Connection to Redis database
        self.redis_conn = redis_conn

        self.nexthop_key = "NIROUTER/GET_FWD/nh"

        return

    #--------------------------------------------------------------------------#
    def add_new_req(self, req_msg):
        # Create the set of next hops to try
        # If there is a http_auth in the json_in, put it first
        # This will have been derived from original ni URI specified
        if req_msg.json_in.has_key("http_auth"):
            ll0 = [ req_msg.json_in["http_auth"] ]
        else:
            ll0 = []
        # See if there is a locliat in the json_in field
        if req_msg.json_in.has_key("loclist"):
            ll1 = req_msg.json_in["loclist"]
            # Worry about unicode
            if type(ll1) == StringType:
                ll1 = [ ll1 ]
            elif type(ll1) != ListType:
                ll1 = []
        else:
            ll1 = []
        print ll1
        # Add next hops from Redis database
        try:
            ll2 = self.redis_conn.hvals(self.nexthop_key)
            self.logdebug("Next hops: %s" % str(ll2))
            # Gets empty list if key not present
        except Exception, e:
            self.logerror("Unable to retrieve nexthop list from Redis: %s" %
                          str(e))
            return False

        self.logdebug("Retrieving from %s" % str(" ".join(chain(ll0, ll1, ll2))))

        # Remove duplicates and select only HTTP URLs if specified
        # (remove explicitly DTN URLs)
        for nh in chain(ll0, ll1, ll2):
            nh = nh.lower()
            if nh.startswith(self.DTN_SCHEME_PREFIX):
                continue
            if nh.startswith(self.HTTP_SCHEME_PREFIX):
                nh = nh[len(self.HTTP_SCHEME_PREFIX):]
            if nh not in req_msg.http_host_list:
                self.logdebug("add %s" % nh)
                req_msg.http_host_list.append(nh)

        # See if we have any next hops
        if len(req_msg.http_host_list) == 0:
            self.loginfo("No next hops found for %s" %
                         req_msg.bpq_data.bpq_val)
            return False

        # Create the set of host indices not yet completed
        req_msg.http_hosts_not_completed = \
                                        set(range(len(req_msg.http_host_list)))

        # Initialize timer to cut off waiting for more results
        req_msg.timeout = Timer(10.0, self.id_timed_out, args = [req_msg.req_seqno])

        # Add the new request to list of requests to process and flag action
        # needed
        with self.reqs_lock:
            self.curr_reqs.append(req_msg)
            self.req_dict[req_msg.req_seqno]= req_msg
            self.action_needed.set()
            
        return True
    
    #--------------------------------------------------------------------------#
    def run(self):
        count = 0

        while (self.keep_running):
            self.logdebug("Waiting for more work - running procs %d" %
                          self.running_procs)
            work_todo = self.action_needed.wait()
            self.logdebug("Starting http_action loop: %s %s %d" %
                          (self.keep_running, work_todo, self.running_procs))
            self.action_needed.clear()

            # Either a request has arrived or there is a spare process now
            # Check if there are any spare processes
            # If so start the next request running
            # Need to have the lock on the requests data for this
            with self.reqs_lock:
                # Need this flag because may need to 'continue' from nexted loop
                wait_for_event = False

                # Find the request to process next
                curr_req = None
                http_host = None
                http_index = None
                for req in self.curr_reqs:
                    # Check if this is first look at this request
                    if not req.proc_started:
                        # If it is first pass, check local cache first if a GET
                        if req.req_type == HTTPRequest.HTTP_GET:
                            try:
                                metadata, cfn = self.ndo_cache.cache_get(req.ni_name)
                                req.content = cfn
                                req.metadata = NetInfMetaData()
                                req.metadata. set_json_val(metadata.summary())
                            except NoCacheEntry,e:
                                # It's not in the local cache
                                self.logdebug("Not found in local cache")
                                pass
                            except Exception, e:
                                self.logerror("Cache failure for %s: %s" %
                                              (ni_name.get_url(), str(e)))
                                pass
                        req.proc_started = True
                        # Start timeout for processing request
                        req.timeout.start()
                        
                    if self.running_procs >= self.parallel_limit:
                        # Can't do anything till a process comes free
                        self.logdebug("All available processes in use - waiting for a free one")
                        wait_for_event = True
                        # Continue processing other requests to find new ones
                        # and look in local cache.
                        continue
                    if req.http_host_next is None:
                        # No more to start for this request
                        continue
                    if len(req.http_hosts_pending) >= self.per_req_limit:
                        # Doing as many as we should at once for this one
                        continue
                    curr_req = req
                    http_host = req.http_host_list[req.http_host_next]
                    http_index = req.http_host_next
                    req.http_host_next += 1
                    if req.http_host_next >= len(req.http_host_list):
                        # Now handled all hosts for this request
                        self.logdebug("Despatched to all hosts for this request")
                        req.http_host_next = None
                        # Test timeout
                        if timeout_test:
                            time.sleep(10.0)
                    # Record this one as being in progress
                    req.http_hosts_pending.add(http_index)
                    break

            # Did we find anything to do?
            if wait_for_event or (http_host is None):
                self.logdebug("Nothing to do on this pass - wait for event")
                continue

            # Set up parameters for action routine
            # Create a dictionary with keys:
            # - msgid (all cases)
            # - loc1, loc2 (optional if has loclist in json_in)
            # - fullPut, ct and meta (for PUBLISH only)
            # - rform (for PUBLISH and SEARCH)
            # - tokens (for SEARCH only)
            form_params = {}

            form_params["msgid"] = curr_req.bpq_data.bpq_id

            if curr_req.json_in.has_key("loclist"):
                ll = curr_req.json_in["loclist"]
                if type(ll) == ListType:
                    if len(ll) > 0:
                        form_params["loc1"] = ll[0]
                    if len(ll) > 1:
                        form_params["loc2"] = ll[1]            

            if curr_req.req_type == HTTPRequest.HTTP_SEARCH:
                form_params["tokens"] = curr_req.bpq_data.bpq_val

            if curr_req.req_type == HTTPRequest.HTTP_PUBLISH:
                form_params["fullPut"] = \
                                    "true" if curr_req.has_payload else "false"

                if curr_req.json_in.has_key("meta"):
                    md = { "meta": curr_req.json_in["meta"] }
                else:
                    md = { "meta" : { } }
                md["meta"]["dtn-to-http"] = "yes"
                form_params["ext"] = json.dumps(md)

                if curr_req.json_in.has_key("ct"):
                    form_params["ct"] = curr_req.json_in["ct"]

            if ((curr_req.req_type == HTTPRequest.HTTP_SEARCH) or
                (curr_req.req_type == HTTPRequest.HTTP_PUBLISH)):
                if curr_req.json_in.has_key("rform"):
                    form_params["rform"] = curr_req.json_in["rform"]
                else:
                    form_params["rform"] = "json"

            try:
                if self.multi:
                    self.logdebug("Starting async request")
                    self.pool.apply_async(action_req,
                                          args=(curr_req.req_type,
                                                curr_req.req_seqno,
                                                curr_req.ni_name,
                                                http_host,
                                                http_index,
                                                form_params,
                                                curr_req.content,
                                                self.tempdir),
                                          callback=self.handle_result)
                    with self.reqs_lock:
                        # Increment count of processes in progress
                        self.running_procs += 1

                        # If now have as many as is allowed at once wait for
                        # one to finish
                        if self.running_procs >= self.parallel_limit:
                            self.logdebug("Pause until process free")
                            wait_for_event = True

                else:
                    self.logdebug("Starting synchronous request")
                    self.handle_result(action_req(curr_req.req_type,
                                                  curr_req.req_seqno,
                                                  curr_req.ni_name,
                                                  http_host,
                                                  http_index,
                                                  form_params,
                                                  curr_req.content,
                                                  self.tempdir))
                # count how many we do
                count = count + 1
            except Exception, e:
                self.logerror("Exception: %s" %  str(e))
                if self.multi:
                        self.pool.close()
                        self.pool.join()
                raise
            
            if not wait_for_event:
                self.logdebug("Forcing immediate next pass") 
                self.action_needed.set()

            self.logdebug("Going round the loop")

        # Close down the multiprocessing if used
        self.logdebug("Exitting HTTP action thread run")  
        if self.multi:
                self.pool.close()
                self.pool.join()
        return

    #--------------------------------------------------------------------------#
    def handle_result(self, result_tuple):
        rv, req_id, http_index, response, metadata = result_tuple
        self.logdebug("Received result for request #%d for request id %s" %
                      (http_index, req_id))
        #time.sleep(2)
        old_content = None
        with self.reqs_lock:
            try:
                req_msg = self.req_dict[req_id]
                self.logdebug(req_msg)
            except KeyError:
                self.logerror("Result req_id (%d) not found in req_dict." % req_id)
                if self.multi:
                    self.running_procs -= 1
                self.action_needed.set()
                return
            if rv:
                self.logdebug("Request #%d for %s succeeded" %
                              (http_index, req_msg.bpq_data.bpq_val))
                if req_msg.req_type == HTTPRequest.HTTP_GET:
                    # Take latest content file (all the same in theory)
                    if response is not None:
                        old_content = req_msg.result
                        req_msg.result = response
                    # Combine metadata
                    if req_msg.metadata is None:
                        req_msg.metadata = NetInfMetaData()
                    req_msg.metadata.insert_resp_metadata(metadata)
                else:
                    # PUBLISH and SEARCH - concatentate responses
                    src = req_msg.http_host_list[http_index]
                    rform_json = (req_msg.json_in.get("rform") == "json")
                    if req_msg.result is None:
                        # First response
                        req_msg.result = StringIO.StringIO()
                        if rform_json:
                            req_msg.result.write('{ "%s" :' % src)
                        else:
                            req_msg.result.write("From %s:\n" % src)
                    elif rform_json:
                        req_msg.result.write(', "%s" :' % src)
                    else:
                        req_msg.result.write("\n\n==========\n\nFrom %s:\n" % src)
                    req_msg.result.write(response)
            try:
                req_msg.http_hosts_pending.remove(http_index)
                req_msg.http_hosts_not_completed.remove(http_index)
            except KeyError:
                self.logerror("Result http_index (%d) not in trq_msg set(s)" %
                              http_index)
            if self.multi:
                self.running_procs -= 1
            if len(req_msg.http_hosts_not_completed) == 0:
                # All hosts have responded - send back to DTN
                self.logdebug("Sending back response for request %d" %
                              req_msg.req_seqno)
                # Move concatentated PUBLISh and SEARCH response to disk file
                if req_msg.req_type != HTTPRequest.HTTP_GET:
                    if req_msg.json_in.get("rform") == "json":
                        req_msg.result.write("}")
                    try:
                        fd, response_file = tempfile.mkstemp(dir=tempdir)
                        fo = os.fdopen(fd, "wb")
                        fo.write(req_msg.result.getvalue())
                        fo.close()
                    except Exception, e:
                        nilog("Writing responses to temp file %s failed: %s" %
                              (response_file, str(e)))
                        req_msg.result.close()
                        req_msg.result = None
                    finally:
                        req_msg.result = response_file

                    debug("Written response to %s" % response_file)
                    

                # Warning: send_result also requires the reqs_lock!
                self.send_result(False, req_msg)
            else:
                self.logdebug("Waiting for more responses for request %d" %
                              req_msg.req_seqno)

        # Eemove duplicate content file
        if old_content is not None:
            self.logdebug("Removing duplicate content file %s" % old_content)
            os.remove(old_content)

        # There is now a free process if multiprocessing or
        # in single processing we are ready for the next host/request.
        self.action_needed.set()
        return
                                                                                            
    #--------------------------------------------------------------------------#
    def id_timed_out(self, req_id):
        self.logdebug("Handling request time out for req id %d" % req_id)
        with self.reqs_lock:
            try:
                req_msg = self.req_dict[req_id]
                self.logdebug(req_msg)
            except:
                self.logerror("Result req_id (%d) not found in req_dict." % req_id)
                return
        
            self.send_result(True, req_msg)
        return
    
    #--------------------------------------------------------------------------#
    def send_result(self, timed_out, req_msg):
        # Must be called with reqs_lock on
        self.logdebug("Sending result - response %s" %
                      "timed out" if timed_out else "received")
        # Clear the timer if still running
        if not timed_out:
            req_msg.timeout.cancel()
        evt_msg = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, req_msg)
        self.resp_q.put(evt_msg)
        try:
            del self.req_dict[req_msg.req_seqno]
            self.curr_reqs.remove(req_msg)
        except:
            self.loginfo("Duplicate removal of req_msg %d" % req_msg.req_seqno)
        return

    #--------------------------------------------------------------------------#
    def end_run(self):
        """
        @brief terminate running of HTTP action thread and send 'end' message
        to DTN send thread.
        """
        self.logdebug("HTTP action end run called")
        self.keep_running = False
        self.action_needed.set()
        evt = MsgDtnEvt(MsgDtnEvt.MSG_END, None)
        self.resp_q.put_nowait(evt)
        return

 #=============================================================================#
if __name__ == "__main__":
    #=== Test Code ===#
    # dtnapi is only needed during testing for definitions of structures
    import dtnapi
    class TestCache():
        def __init(self):
            return
        def cache_get(self, ni_name):
            raise NoCacheEntry("Test cache")
        # Normally returns 2-tuple (metadata, content file name)
            
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    dtn_send_q = Queue.Queue()
    tempdir = "/tmp"

    # Clear existing next hop key in Redis
    redis_conn = StrictRedis()
    nh_key = "NIROUTER/GET_FWD/nh"
    redis_conn.delete(nh_key)
    
    ndo_cache = TestCache()
    http_action = HTTPAction(dtn_send_q, tempdir, logger, redis_conn, ndo_cache,
                             mprocs=1, parallel_limit=1, per_req_limit=1)
    http_action.setDaemon(True)

    # With timeout_test True, the last despatch to a host for a request is
    # held up for 10s, sufficient to trigger the timeout for that request
    # and demonstrate that the timeout mechanism works.
    # The remaining despatch will be processed after the request has been
    # removed from the request queue, so this also checks that late returning
    # results do not break the system,
    timeout_test = False

    http_action.start()

    
    time.sleep(0.1)
    logger.info("HTTP action handler running: %s" % http_action.getName())
    logger.info("Test will end in approximately 15s")

    # Build a request message to send
    # Note that we don't actually need the original bundle to do this
    # This is deliberate so that can use this for forwarding.
    # BPQ data structure
    # digest used here is for a snapshot of the /etc/group
    # file that is specified as content later. It is irrelevant
    # for internal testing as the digest is not checked but
    # you might wish to modify it if using this test code to
    # test the nigetalt.py module.
    #nis = "ni:///sha-256-32;IEtLRQ"
    nis = "ni:///sha-256;--3eVr68lofft_RqlGiV_R8xSBbj2MUul7zoCK1TO7I"
    bndl = dtnapi.dtn_bundle()
    bpq = BPQ()
    bpq.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_QUERY)
    bpq.set_matching_rule(BPQ.BPQ_MATCHING_RULE_EXACT)
    bpq.set_src_eid("dtn://example.dtn")
    bpq.set_bpq_id("msgid_zzz")
    bpq.set_bpq_val(nis)
    bpq.clear_frag_desc()
    logger.info("BPQ block:\n%s" % str(bpq))

    json_in = { "loc": "http://tcd.netinf.eu" }

    nin = NIname(nis)
    nin.validate_ni_url()

    req = HTTPRequest(HTTPRequest.HTTP_GET, bndl, bpq, json_in,
                      has_payload=True, ni_name=nin,
                      make_response=True,
                      response_destn="dtn://example.dtn/netinfproto/app/response",
                      content=None)
    #req.metadata = { "d": "e" }
    rv =True
    #rv = http_action.add_new_req(req)
    if not rv:
        logger.info("Adding request failed correctly on account of nowhere to get from")

    # Put some entires in the next hop database
    nhl = {}
    nhl[0] = "tcd.netinf.eu"
    nhl[1] = "dtn://mightyatom.dtn"
    nhl[2] = "tcd-nrs.netinf.eu"
    redis_conn.hmset(nh_key, nhl)

    json_in = { "loclist": ["tcd.netinf.eu"] }
    req = HTTPRequest(HTTPRequest.HTTP_GET, bndl, bpq, json_in,
                      has_payload=True, ni_name=nin,
                      make_response=True,
                      response_destn="dtn://example.dtn/netinfproto/app/response",
                      content=None)
    #rv = http_action.add_new_req(req)

    nis = "ni:///sha-256;--3eVr68lofft_RqlGiV_R8xSBbj2MUul7zoCK1TO7I"
    bndl = dtnapi.dtn_bundle()
    bpq = BPQ()
    bpq.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_PUBLISH)
    bpq.set_matching_rule(BPQ.BPQ_MATCHING_RULE_EXACT)
    bpq.set_src_eid("dtn://example.dtn")
    bpq.set_bpq_id("msgid_zzz")
    bpq.set_bpq_val(nis)
    bpq.clear_frag_desc()
    logger.info("BPQ block:\n%s" % str(bpq))

    json_in = { "loclist": [ "http://neut-r.netinf.eu" ],
                "rform" : "json",
                "meta" : { },
                "fullPut" : "no"
                }

    nin = NIname(nis)
    nin.validate_ni_url()

    req = HTTPRequest(HTTPRequest.HTTP_PUBLISH, bndl, bpq, json_in,
                      has_payload=False, ni_name=nin,
                      make_response=True,
                      response_destn="dtn://example.dtn/netinfproto/app/response",
                      content="ss")
    rv = http_action.add_new_req(req)
    """
    # Build a response to a GET request with no content payload
    req = HTTPRequest(HTTPRequest.HTTP_GET, bndl, bpq, json_in,
                      has_payload=False, ni_name=nin,
                      make_response=True, response_destn=response_eid,
                      content=None)

    req.metadata = { "d": "e" }


    # Build a GET request
    req = HTTPRequest(HTTPRequest.HTTP_GET, bndl, bpq, json_in,
                      has_payload=False, ni_name=nin,
                      make_response=False, response_destn=get_eid,
                      content=None)

    """
    test_run = True
    def end_test():
        http_action.end_run()
        test_run = False
    t = Timer(15.0, end_test)
    t.start()
    
    while test_run:
        try:
            evt = dtn_send_q.get(True, 1.0)
            logger.debug("Event received")
        except:
            continue
        if evt.is_last_msg():
            logger.info("End msg received")
            break
        logger.info("=== Response received in test routine: ===")
        logger.info("Event seqno: %d" % evt.msg_seqno())
        logger.info("Data:\n%s" % str(evt.msg_data()))
        logger.info("Metadata: %s" % str(evt.msg_data().metadata))
        logger.info("Content in %s" % evt.msg_data().result)
        logger.info("=== End of response ===")

    logger.info("End of test")
    time.sleep(4)
    logger.info("Exitting")
    
