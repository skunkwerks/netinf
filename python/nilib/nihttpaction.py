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
import os.path
import  random
from optparse import OptionParser
import urllib
import urllib2
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
from ni import ni_errs, ni_errs_txt, NIname, NIproc
from nifeedparser import DigestFile, FeedParser
from nidtnevtmsg import HTTPRequest, MsgDtnReq
from metadata import NetInfMetaData

#============================================================================#
verbose = False

def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    global verbose
    if verbose:
        print string
    return

#===============================================================================#
logger=logging.getLogger("nigetlist")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def nilog(string):
	"""
	@brief Log the node, time, and the string
	@param string to be printed (in)
	"""
	node=platform.node()
	now=time.time() 
	nano= "%.10f" %now
	utct = time.strftime("%Y-%m-%dT%H:%M:%S")
	
	logger.info('NILOG: ' + node + ',' + nano + ',' + utct + ',' + string)
	
	return

#===============================================================================#
def get_req(req_id, ni_url, http_host, http_index, form_params, tempdir):
    """
    @brief Perform a NetInf 'get' from the http_host for the ni_url.
    @param req_id integer sequence number of message containing request
    @param ni_url string ni name to be retrieved
    @param http_host string HTTP host name to be accessed
                            (FQDN or IP address with optional port number)
    @param http_index integer index of host name being processed within request
    @param form_params dictionary of paramter values to pass to HTTP
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
    form_data = urllib.urlencode({ "URI":   ni_url,
                                   "msgid": form_params["msgid"],
                                   "ext": "" if not form_params.has_key["ext"] else
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
        
#===============================================================================#
#===============================================================================#
#===============================================================================#
def action_req(req_type, req_id, ni_url, http_host, http_index, form_params, tempdir):
    """
    @brief Switch to correct proceeing routine for req_type
    @param req_type string HTTP_GET, HTTP_PUBLISH or HTTP_SEARCH from HTTPRequest
    @param req_id integer sequence number of message containing request
    @param ni_url NIname object instance with ni URI to be retrieved or
                                         published or None (search case)
    @param http_host string HTTP host name to be accessed
    @param http_index integer index of host name being processed within request
    @param form_params dictionary of paramter values to pass to HTTP
    @param tempdir string where to place retrieved data
    @return 5-tuple with:
                boolean - True if succeeds, False if fails
                string req_id as supplied as parameter
                integer http_index as supplied as parameter
                string pathname for content file/response or None is no content etc
                dictionary returned JSON metadata if any, decoded
                
    Requests translated from DTN bundles to be actioned by HTTP CL are
    funneled through this routine to simplify the multi-process interface.
    The result is a tuple that is fed back to the callback routine when using
    multiprocessing implementation allowing the result to be linked to the
    original request.
    """
    try:
        req_rtn = {HTTPRequest.HTTP_GET: get_req,
                   HTTPRequest.HTTP_PUBLISH: publish_req,
                   HTTPRequest.HTTP_SEARCH: search_req}[req_type]
    except:
        nilog("Bad req_type (%s) supplied to action_req" % req_type)
        return(False, req_id, http_index, None, None)

    try:
        return req_rtn(req_id, ni_url, http_host, http_index,
                       form_params, tempdir)
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

    The individual requests can be arried out in sub-processes in parallel
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
        # Logging functions
        self.logger = self.server.logger
        self.loginfo = self.server.logger.info
        self.logdebug = self.server.logger.debug
        self.logwarn = self.server.logger.warn
        self.logerror = self.server.logger.error

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
            self.multi = True
            self.pool = multiprocessing.Pool(mprocs)
        else:
            self.multi = False
            self.pool = None

        # Initialize records of work in progress
        self.curr_reqs = []
        self.req_dict = {}
        # Number of running processes
        self.running_procs = 0
        # Provide lock to control access to curr_reqs and process count
        self.reqs_lock = ThreadingLock()

        # Event indicating that there is something to be done
        self.action_needed = Event()
        self.action_needed.clear()
        # Fudge for Python 2.6
        self.work_todo = False

        # Connection to Redis database
        self.redis_conn = redis_conn

        self.nexthop_key = "NIROUTER/GET_FWD/nh"

        return

    #--------------------------------------------------------------------------#
    def add_new_req(self, req_msg):
        # Create the set of next hops to try
        # If there is a netloc in the ni_name, put it first
        if (req.ni_name is not None):
            nl = req.ni_name.get_netloc()
            if nl != "":
                ll0 = [ nl ]
            else:
                ll0 = []
        # See if there is a locliat in the json_in field
        if json_in.has_key("loclist"):
            ll1 = json_in["loclist"]
            # Worry about unicode
            if type(ll1) != StringType:
                ll1 = [ ll1 ]
            elif type(ll) != ListType:
                ll1 = []
        else:
            ll1 = []
        # Add next hops from Redis database
        try:
            ll2 = self.redis_conn.hgetall(self.nexthop_key)
            # Gets empty dictionary if key not present
        except Exception, e:
            self.logerror("Unable to retrieve nexthop list from Redis: %s" %
                          str(e))
            return False

        # Remove duplicates and select only HTTP URLs if specified
        # (remove explicitly DTN URLs)
        for nh in chain(ll0, ll1, ll2):
            nh = nh.lower()
            if nh.startswith(self.DTN_SCHEME_PREFIX):
                continue
            if nh.startswith(self.HTTP_SCHEME_PREFIX):
                nh = nh[len(HTTP_SCHEME_PREFIX):]
            if nh not in req_msg.http_host_list:
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
        req_msg.timeout = Timer(10.0, self.send_result, args = [True, req_msg])

        # Add the new request to list of requests to process and flag action
        # needed
        with self.reqs_lock:
            self.curr_reqs.append(req_msg)
            self.req_dict[req_msg.req_seqno]= req_msg
            self.work_todo = True
            self.action_needed.set()
            req_msg.timeout.start()
            
        return True
    
    #--------------------------------------------------------------------------#
    def run(self):
        count = 0

        while (self.keep_running):
            work_todo = self.action_needed.wait(1.0)
            self.action_needed.clear()
            # Fudge for Python 2.6
            # For timeout case just loop in case this thread is being shutdown
            if work_todo is None:
                if not self.work_todo:
                    continue
            elif not work_todo:
                continue
            self.work_todo = False

            # Either a request has arrived or there is a spare process now
            # Check if there are any spare processes
            # If so start the next request running
            # Need to have the lock on the requests data for this
            with self.reqs_lock:
                restart_loop = False
                # XXX  - may need to move this later so sorting out new
                # requests already in local cache isn't delayed unecessarily
                if self.running_procs >= self.parallel_limit:
                    # Can't do anything till a process comes free
                    restart_loop = True
                    continue
                # Find the request to process next
                curr_req = None
                http_host = None
                http_index = None
                for req in self.curr_reqs:
                    # Check if this is first look at this request
                    if not req.proc_started:
                        # If it is first pass, check local cache first if a GET
                        if ((not req.proc_started) and
                            (req.req_type == HTTPRequest.HTTP_GET)):
                            try:
                                metadata, cfn = self.ndo_cache.get_cache(req.ni_name)
                                req.content = cfn
                                req.metadata = NetInfMetaData()
                                req.metadata. set_json_val(metadata.summary())
                            except Exception, e:
                                pass
                    req.proc_started = True
                        
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
                        req.http_host_index = None
                    # Record this one as being in progress
                    req.http_hosts_pending.add(http_index)
                    # Increment processes in progress
                    self.running_procs += 1
                    break

            # Did we find anything to do?
            if restart_loop or (http_host is None):
                continue

            # Set up parameters for action routine
            # Create a dictionary with keys:
            # - msgid (all cases)
            # - loc1, loc2 (optional if has loclist in json_in)
            # - fullPut (for PUBLISH only)
            # - rform (for PUBLISH and SEARCH)
            # - tokens (for SEARCH only)
            form_params = {}

            form_params["msgid"] = curr_reg.bpq_data.query_id

            if curr_req.req_type == HTTPRequest.HTTP_SEARCH:
                form_params["tokens"] = curr_req.bpq_data.query_val

            if curr_req.json_in.has_key("rform"):
                form_params["rform"] = curr_req.json_in["rform"]
            else:
                form_params["rform"] = "json"

            if curr_req.req_type == HTTPRequest.HTTP_PUBLISH:
                form_params["fullPut"] = \
                                    "true" if curr_req.has_payload else "false"

                if curr_req.json_in.has_key("meta"):
                    md = { "meta": curr_req.json_in["meta"] }
                    form_params["ext"] = json.dumps(md)

            if curr_req.json_in.has_key("loclist"):
                ll = curr_req.json_in["loclist"]
                if type(ll) == ListType:
                    if len(ll) > 0:
                        form_params["loc1"] = ll[0]
                    if len(ll) > 1:
                        form_params["loc2"] = ll[1]            

            try:
                if multi:
                    self.pool.apply_async(action_req,
                                          args=(curr_req.req_type,
                                                curr_req,req_seqno,
                                                curr_req.ni_name,
                                                http_host, http_index.
                                                form_params, self.tempdir),
                                          callback=self.handle_result)
                else:
                    self.handle_result(action_req(curr_req.req_type,
                                                  curr_req.req_seqno,
                                                  curr_req.ni_name,
                                                  http_host,
                                                  http_index,
                                                  form_params,
                                                  self.tempdir))
                # count how many we do
                count = count + 1
            except Exception, e:
                nilog("Exception: %s" %  str(e))
                if multi:
                        pool.close()
                        pool.join()
                return (count, complete_count, goodlist, badlist)

        # Close down the multiprocessing if used
        if multi:
                pool.close()
                pool.join()
        return (count,complete_count, goodlist,badlist)

    #--------------------------------------------------------------------------#
    def handle_result(self, result_tuple):
        rv, req_id, http_index, content_file, metadata = result_tuple
        try:
            req_msg = self.req_dict[req_id]
        except KeyError:
            logerror("Result req_id (%d) not found in req_dict." % req_id)
            self.running_procs -= 1
            self.action_needed.set()
            self.work_todo = True
            return
        with self.reqs_lock:
            if rv:
                req_msg.content = content_file
                if req_msg.metadata is None:
                    req_msg.metadata = NetInfMetaData()
                    req_msg.metadata.set_json_val(metadata)
                else:
                    req_msg.metadata.insert_resp_metadata(metadata)
            try:
                req_msg.http_hosts_pending.remove(http_index)
                req_msg.http_hosts_not_completed.remove(http_index)
            except KeyError:
                logerror("Result http_index (%d) not in trq_msg set(s)" %
                         http_index)
            self.running_procs -= 1
            if len(req_msg.http_hosts_not_completed) == 0:
                # All hosts have responded - sent back to DTN
                self.send_result(False, req_msg)

        self.action_needed.set()
        self.work_todo = True                          
        return
                                                                                            
    #--------------------------------------------------------------------------#
    def send_result(self, timed_out, req_msg):
        # Clear the timer if still running
        if not timed_out:
            req_msg.timeout.cancel()
        evt_msg = DtnEvtMsg(MsgDtnEvt.MSG_TO_DTN, req_msg)
        self.resp_q.put(evt_msg)
        with self.reqs_lock:
            try:
                del self.req_dict[req_msg.req_seqno]
                self.curr_reqs.remove(req_msg)
            except:
                loginfo("Duplicate removal of req_msg %d" % req_msg.req_seqno)

        return

    #--------------------------------------------------------------------------#
    def end_run(self):
        """
        @brief terminate running of HTTP action thread.
        """
        self.keep_running = False
        return
 #===============================================================================#
if __name__ == "__main__":
    py_nigetlist()
