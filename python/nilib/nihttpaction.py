#!/usr/bin/python
"""
@package nilib
@file nihttpaction.py
@brief Multiprocess handler for forwarding requests via HTTP convergence layer.
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
Multiprocess handler for forwarding requests via HTTP convergence layer.

This module contains two pieces:
- a class, HTTPAction, an instance of which is used to manage a thread that
  forwards incoming NetInf requests to one or more locators found from
  various sources:
  - the locator originally in the ni name
  - any http scheme or unspecified scheme URLs in the loclist in the affiliated
    data of the request
  - any http or unnspecified scheme locators found in the NRS datnbase
  Duplicates ane the current node are removed from the list and the request
  forwarded to each remaining locator (if any).


@code
Revision History
================
Version   Date       Author         Notes
1.3   28/03/2012 Elwyn Davies   Clean up and adding local operations using
                                local cache for GET and PUBLISH.
1.2   16/03/2012 Elwyn Davies   Completed documentation comments.
1.1   13/02/2012 Elwyn Davies   Running version for demo tests.
1.0   10/02/2012 Elwyn Davies   Prepared for demo tests.
0.2   06/02/2012 Elwyn Davies   Added publish functionality.
0.1   03/02/2012 Elwyn Davies   Debugged ready for integration.
0.0   01/02/2012 Elwyn Davies   Created with get functionality only.
@endcode
"""
#==============================================================================#
#=== Standard modules for Python 2.[567].x distributions ===
import sys
from types import *
import os.path
import  random
from optparse import OptionParser
from urllib import urlencode
from urllib2 import Request, urlopen, URLError, HTTPError
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

#=== Modules needing special downloading
from redis import StrictRedis

#=== Local package modules ===

from ni import ni_errs, ni_errs_txt, NIname, NIproc, NIdigester
from nifeedparser import DigestFile, FeedParser
from nidtnevtmsg import HTTPRequest, MsgDtnEvt
from metadata import NetInfMetaData
from ni_exception import NoCacheEntry
from nidtnbpq import BPQ
from encode import *
from streaminghttp import register_openers

#============================================================================#
# === Routines Executed in Asynchronous Multiprocess

# === GLOBAL VARIABLES ===

##@var process_logger
# instance of logger object used for logging in asynchronous processes 
process_logger= None

# --- The following three variables are used by logging in spawned processes ---
##@var curr_req_id
# integer identifier for request being processed in asynchronous process
curr_req_id = -1

##@var curr_req_index
# integer index of host for request being processed in asynchronous process
curr_req_index = -1

##@var curr_req_type
# string type of request (GET, PUBLISH, SEARCH) being processed in async process
curr_req_type = "unknown"

#===============================================================================#
#=== Logging Functions for spawned processes ===
#-------------------------------------------------------------------------------#
def splog(logfn, logstr):
    """
    @brief Log the node, request id, request index, request type, time, and
           the logstr using logger function provided in logfn
    @param logfn callable unbound logging function (info, warn, error, etc)
    @param logstr string to be printed
    """
    node=platform.node()
    now=time.time() 
    nano= "%.10f" % now
    utct = time.strftime("%Y-%m-%dT%H:%M:%S")
    
    logfn('HTTPActionProc: ' +
              ','.join([node, nano, str(curr_req_id), str(curr_req_index),
                        curr_req_type, utct, logstr]))
    
    return

#------------------------------------------------------------------------------#
def sploginfo(logstr):
    """
    @brief Log the node, request id, request index, request type, time, and
           the logstr as an info level message
    @param logstr string to be printed
    """
    splog(logger.info, logstr)
    return
    
#------------------------------------------------------------------------------#
def splogwarn(logstr):
    """
    @brief Log the node, request id, request index, request type, time, and
           the logstr as a warning level message
    @param logstr string to be printed
    """
    splog(logger.warn, logstr)
    return
    
#------------------------------------------------------------------------------#
def splogdebug(logstr):
    """
    @brief Log the node, request id, request index, request type, time, and
           the logstr as a debug level message
    @param logstr string to be printed
    """
    splog(logger.debug, logstr)
    return
    
#------------------------------------------------------------------------------#
def splogerror(logstr):
    """
    @brief Log the node, request id, request index, request type, time, and
           the logstr as an error level message
    @param logstr string to be printed
    """
    splog(logger.error, logstr)
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
            splogdebug("Error: %s is not a complete, valid ni scheme URL: %s" % (ni_url.get_url(), ni_errs_txt[rv]))
            return(False, req_id, http_index, 500,
                   "Invalid ni name object", None)

    # Generate NetInf form access URL
    ni_url_str = ni_url.get_canonical_ni_url()
    
    # Generate NetInf form access URL
    http_url = "http://%s/netinfproto/get" % http_host
    
    # Set up HTTP form data for get request
    form_data = urlencode({ "URI":   ni_url_str,
                            "msgid": form_params["msgid"],
                            "ext": "" if not form_params.has_key("ext") else
                                        form_params["ext"]})

    # Send POST request to destination server
    try:
        http_object = urlopen(http_url, form_data)
    except URLErrror, e:
        sploginfo("Info: Unable to access http URL %s: %s" % (http_url, str(e)))
        return(False, req_id, http_index, 404,
               ("Unable to access server %s: %s" % (http_url, str(e))),
               None, None)
    except HTTPError, e:
        

    # Get HTTP result code
    http_result = http_object.getcode()

    # Get message headers - an instance of email.Message
    http_info = http_object.info()
    splogdebug("Response type: %s" % http_info.gettype())
    splogdebug("Response info:\n%s" % http_info)

    if (http_result != 200):
        splogdebug("Get request returned HTTP code %d" % http_result)
        buf = http_object.read()
        splogdebug("HTTP Response: %s" % buf)
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
    splogdebug("Writng content to %s" % digested_file)

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
        splogwarn("Warning: Response was not a correctly formed MIME object")
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)
    # Verify length 
    if ((obj_length != None) and (payload_len != obj_length)):
        splogwarn("Warning: Retrieved contents length (%d) does not match"
                  "Content-Length header value (%d)" % (len(buf), obj_length))
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)
        
    splogdebug( msg.__dict__)
    # If the msg is multipart this is a list of the sub messages
    parts = msg.get_payload()
    splogdebug("Multipart: %s" % str(msg.is_multipart()))
    if msg.is_multipart():
        splogdebug("Number of parts: %d" % len(parts))
        if len(parts) != 2:
            splogwarn("Warning: Response from server does not have two parts.")
            os.remove(digested_file)
            return(False, req_id, http_index, None, None)
        json_msg = parts[0]
        ct_msg = parts[1]
    else:
        splogdebug("Return is single part")
        json_msg = msg
        ct_msg = None

    # Extract JSON values from message
    # Check the message is a application/json
    splogdebug(json_msg.__dict__)
    if json_msg.get("Content-type") != "application/json":
        splogwarn("Warning: First or only component (metadata) of result "
                  "is not of type application/json")
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)

    # Extract the JSON structure
    try:
        json_report = json.loads(json_msg.get_payload())
    except Exception, e:
        splogwarn("Warning: Could not decode JSON report '%s': %s" %
                  (json_msg.get_payload(),
                   str(e)))
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)
    
    splogdebug("Returned metadata for %s:" % ni_url_str)
    splogdebug(json.dumps(json_report, indent = 4))

    msgid = json_report["msgid"]
    if msgid != form_params["msgid"]:
        splogwarn("Returned msgid (%s) does not match request msgid (%s)" %
                  (msgid, form_params["msgid"]))
        os.remove(digested_file)
        return(False, req_id, http_index, None, None)

    # If the content was also returned..
    if ct_msg != None:
        splogdebug(ct_msg.__dict__)
        digest= digester.get_digest()[:ni_url.get_truncated_length()]
        digest = NIproc.make_b64_urldigest(digest)
                                          
        # Check the digest
        #print digest, ni_url.get_digest()
        if (digest != ni_url.get_digest()):
            splogwarn("Digest of %s did not verify" % ni_url.get_url())
            os.remove(digested_file)
            return(False, req_id, http_index, None, None)
        etime = time.time()
        duration = etime - stime
        sploginfo("%s,GET rx fine,ni,%s,size,%d,time,%10.10f" %
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
    splogdebug("Publishing via: %s" % http_url)

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
            splogerror("Cannot construct valid ni URL: %s" % ni_errs_txt[rv])
            return(False, req_id, http_index, None, None)
        splogdebug(ni_digester.get_url())

        # Open the file if possible
        try:
            f = open(file_name, "rb")
        except Exception, e :
            splogwarn("Unable to open file %s: Error: %s" % (file_name, str(e)))
            return(False, req_id, http_index, None, None)

        # If we don't know content type, guess it
        if form_params.has_key("ct"):
            ctype = form_params["ct"]
        else:
            # Guess the mimetype of the file
            m = magic.Magic(mime=True)
            ctype = m.from_file(file_name)
            splogdebug("Content-Type: %s" % ctype)
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

    #splogdebug("Parameters prepared: %s"% "".join(datagen))
    splogdebug("Parameters prepared")

    # Set up streaming HTTP mechanism - register handlers with urllib2
    opener = register_openers()
                                         
    # Send POST request to destination server
    try:
        req = Request(http_url, datagen, headers)
    except Exception, e:
        splogerror("Error: Unable to create request for http URL %s: %s" %
                   (http_url, str(e)))
        if full_put:
            f.close()
        return(False, req_id, http_index, None, None)

    # Get HTTP results
    try:
        http_object = urlopen(req)
    except Exception, e:
        sploginfo("Warning: Unable to access http URL %s: %s" % (http_url,
                                                                 str(e)))
        if full_put:
            f.close()
        return(False, req_id, http_index, None, None)

    if full_put:
        f.close()
        target = octet_param.get_url()
    else:
        target = ni_name.get_url()
    splogdebug("Sent request: URL: %s" % target)


    # Get message headers
    http_info = http_object.info()
    http_result = http_object.getcode()
    splogdebug("HTTP result: %d" % http_result)
    splogdebug("Response info: %s" % http_info)
    splogdebug("Response type: %s" % http_info.gettype())

    # Read results into buffer
    payload = http_object.read()
    http_object.close()
    splogdebug(payload)

    # Report outcome
    if (http_result != 200):
        sploginfo("Unsuccessful publish request returned HTTP code %d" %
              http_result) 
        return(False, req_id, http_index, None, None)

    # Check content type of returned message matches requested response type
    ct = http_object.headers["content-type"]
    if rform == "plain":
        if ct != "text/plain":
            sploginfo("Error: Expecting plain text (text/plain) response "
                      "but received Content-Type: %s" % ct)
        return(False, req_id, http_index, None, None)
    elif rform == "html":
        if ct != "text/html":
            sploginfo("Error: Expecting HTML document (text/html) response "
                  "but received Content-Type: %s" % ct)
    else:
        if ct != "application/json":
            sploginfo("Error: Expecting JSON coded (application/json) "
                      "response but received Content-Type: %s" % ct)
            return(False, req_id, http_index, None, None)
    return(True, req_id, http_index, payload, None)

#------------------------------------------------------------------------------#
def publish_local(req_id, ni_url, http_host, http_index, form_params,
                  file_name, tempdir):
    """
    @brief Perform a NetInf 'publish' towards the http_host for the ni_url.
    @param req_id integer sequence number of message containing request
    @param ni_url object instance of NIname with ni name to be retrieved
    @param http_host string HTTP host name for this node 
                            (only used for building response strings)
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
    # Record timestamp for this operation
    timestamp = NetInfMetaData.metadata_timestamp_for_now()
    
    full_put = (file_name is not None)
    splogdebug("NetInf publish for "
               "URI %s, fullPut %s octets %s, msgid %s, rform %s, ext %s,"
               "loc1 %s, loc2 %s at %s" % (ni_url.get_canonical_ni_url(),
                                           full_put,
                                           file_name,
                                           form_params["msgid"],
                                           form_params["rform"],
                                           form_params["ext"],
                                           form_params,get("loc1", ""),
                                           form_params.get"loc2", ""),
                                           timestamp))


    # Extract extra metadata if present
    # The metadata is to be held in a JSON object labelled "meta" in the "ext"
    # form field.  The following code extracts this object which is represented
    # by a Python dictionary, checking that it is a dictionary (object) in case
    # the user has supplied a garbled piece of JSON.
    extrameta = {}
    try:
        ext_json = json.loads(form_params["ext"])
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
        splogerror("Value of form field 'ext' '%s' is not a valid JSON string." %
                   form_params["ext"])
        return(False, req_id, http_index, None, None)

    extrameta["publish"] = "dtn-http-gateway"

    # Check that the response type is one we expect - default is JSON if not explicitly requested
    rform = form_params["rform"].lower()
    if not((rform == "json") or (rform == "html") or (rform == "plain")):
        sploginfo("Unhandled publish response format requested '%s'." % rform)
        return(False, req_id, http_index, None, None)
    
    # Extract the locators from the form_params
    loc1 = form_params.get("loc1", "")
    loc2 = form_params.get("loc2", "")
    
    # Generate NIname and validate it (it should have a Params field).
    rv = ni_url.validate_ni_url(has_params=True)
    if rv is not ni_errs.niSUCCESS:
        sploginfo("URI format of %s inappropriate: %s" % (self.path,
                                                          ni_errs_txt[rv]))
        return(False, req_id, http_index, None, None)

    # Retrieve query string (if any) 
    qs = ni_name.get_query_string()

    # We don't know what the content type or the length are yet
    ctype = None
    file_len = -1

    # If the form data contains an uploaded file...
    temp_name = None
    if file_name is not None:
        # Copy the file from the network to a temporary name in the right
        # subdirectory of the storage_root.  This makes it trivial to rename it
        # once the digest has been verified.
        temp_fd, temp_name = tempfile.mkstemp(dir=tempdir)

        # Convert file descriptor to file object
        f = os.fdopen(temp_fd, "w")

        splogdebug("Copying and digesting to temporary file %s" %
                   temp_name)

        # Prepare hashing mechanisms
        hash_function = ni_name.get_hash_function()()

        # Copy file from incoming file and generate digest
        file_len = 0
        try:
            g = open(file_name, "rb")
        except Exception, e:
            splogwarn("Unable to open payload file %s: %s" %
                      (file_name, str(e)))
            f.close()
            os.remove(temp_name)
            return(False, req_id, http_index, None, None)
        
        while True:
            buf = g.read(16 * 1024)
            if not buf:
                break
            f.write(buf)
            hash_function.update(buf)
            file_len += len(buf)
        f.close()
        g.close()

        splogdebug("Finished copying")

        # Get binary digest and convert to urlsafe base64 or hex
        # encoding depending on URI scheme
        bin_dgst = hash_function.digest()
        if (len(bin_dgst) != ni_name.get_digest_length()):
            splogerror("Binary digest has unexpected length")
            self.send_error(500, "Calculated binary digest has wrong length")
            os.remove(temp_name)
            return(False, req_id, http_index, None, None)
        if ni_name.get_scheme() == "ni":
            digest = NIproc.make_b64_urldigest(bin_dgst[:ni_name.get_truncated_length()])
            if digest is None:
                splogerror("Failed to create urlsafe base64 encoded digest")
                os.remove(temp_name)
                return(False, req_id, http_index, None, None)
        else:
            digest = NIproc.make_human_digest(bin_dgst[:ni_name.get_truncated_length()])
            if digest is None:
                splogerror("Failed to create human readable encoded digest")
                os.remove(temp_name)
                return(False, req_id, http_index, None, None)

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
    @brief Switch to correct processing routine for req_type
    @param req_type string HTTP_GET, HTTP_PUBLISH or HTTP_SEARCH from HTTPRequest
    @param req_id integer sequence number of message containing request
    @param ni_url NIname object instance with ni URI to be retrieved or
                                         published or None (search case)
    @param http_host string HTTP host name to be accessed
    @param http_index integer index of host name being processed within request
    @param form_params dictionary of paramter values to pass to HTTP
    @param file_name string file name of content to be published or None
    @param tempdir string where to place retrieved data
    @return 6-tuple with:
                boolean - True if succeeds, False if fails
                string req_id as supplied as parameter
                integer http_index as supplied as parameter
                integer (HTTP) status code for response
                string pathname for content file or response or None is no content etc
                dictionary returned JSON metadata if any, decoded
                
    Requests translated from DTN bundles to be actioned by HTTP CL are
    funneled through this routine to simplify the multi-process interface.
    The result is a tuple that is fed back to the callback routine when using
    multiprocessing implementation allowing the result to be linked to the
    original request.
    """
    global curr_req_id, curr_req_index, curr_req_type
    curr_req_id =req_id
    curr_req_index = http_index
    curr_req_type = req_type
    splogdebug("Entering action_req %s: id %s http index %d" %
          (req_type, req_id, http_index))
    try:
        req_rtn = {HTTPRequest.HTTP_GET:           get_req,
                   HTTPRequest.HTTP_PUBLISH:       publish_req,
                   HTTPRequest.HTTP_PUBLISH_LOCAL: publish_local,
                   HTTPRequest.HTTP_SEARCH:        search_req,
                   HTTPRequest.HTTP_SEARCH_LOCAL:  search_local}[req_type]
    except:
        splogerror("Bad req_type (%s) supplied to action_req" % req_type)
        return(False, req_id, http_index, 500, "Bad request type", None)

    try:
        rv = req_rtn(req_id, ni_url, http_host, http_index,
                       form_params, file_name, tempdir)
        splogdebug("Sending back " + str(rv))
        return rv
    except Exception, e:
        splogerror("Exception occurred while processing (%s, %s, %d): %s" %
                   (req_type, req_id, http_index, str(e)))
        return(False, req_id, http_index, 500,
               ("Uncaught exception in server: %s" % str(e)), None)

#===============================================================================#
#=== Request Manager Thread Class ===
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
                 authority, mprocs=1, per_req_limit=1):
        """
        @brief Constructor - set up logging and squirrel parameters
        @param resp_q Queue instance for feeding responses back to DTN
        @param tempdir string pathname for directory for temporary files
        @param logger logging instance for thread
        @param redis_conn StrictRedis instance for Redis NRS database
        @param ndo_cache NetInfCache instance with local NDO cache
        @param authority string authority for local HTTP server
        @param mprocs integer number of async processes in pool
        @param per_req_limit integer max number parallel processes per request

        @detail
        Set up HTTP request processing thread.

        Initialize logging convenience functions

        Save parameters.

        If mprocs > 1 set up a pool of asynchronous worker processes to
        process requests in parallel, otherwise requests will be processed
        serially in this thread.

        Set up request queue and initialize a lock for the queue so it can
        be fed from other threads.

        Set up Event object so that thread can be informed when there is
        - a new request to process
        - a free asynchronous process to use
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
        self.authority = authority
        self.mprocs = mprocs
        self.parallel_limit = mprocs
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
        """
        @brief Record a new request to be forwarded
        @param req_msg HTTPRequest object instance containing request
        @return boolean True if request queued successfully

        @detail
        Create the set of next hops to try with HTTP CL
        - If there is a http_auth in the json_in, put it first
             This will have been derived from original ni URI specified
        - Add any possibilities from loclist
        - Add any possibilities looked up via NS Redis database

        Combine the three lists, removing any duplicates and check this results
        in at least one location to try.  If not return False

        Record the list in the req_msg.
        Create an index of locations to try as the results will not
        necessarily be returned in the order requests are sent out.

        Set up a timer to limit the lengthg of time to wait for respponses
        but don't start it yet as the first request may be held back
        due to others in the queue - the timer is started when the
        first request is sent.

        Lock the request queue while adding the new request to the
        queue, recording the request's presence in the dictionary of active
        requests using its req_msg number (this allows the req_msg to be found
        easily when a response comes back without having the entire req_msg
        in the response or needing to search the queue), and set the
        action_needed semaphore so run loop knows there is something new to do.
        """

        # Consider local cache if requested
        do_local = False
        if req.check_local_cache:
            if req.req_type == HTTPRequest.HTTP_GET:
                # For GET:
                #     Short circuit the forwarding if the NDO is in the
                #     local cache but also forward if only metadata
                try:
                    req.metadata, req.result = \
                                  self.ndo_cache.cache_get(req.ni_name)
                    if req.result is not None:
                        # Got a complete result
                        evt_msg = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, req_msg)
                        self.resp_q.put(evt_msg)
                        return True

                    # Still need to forward the request to see if can
                    # find content if there was only metadata
                    pass

                except NoCacheEntry,e:
                    # It's not in the local cache
                    self.logdebug("Not found in local cache")
                    pass
                except Exception, e:
                    self.logerror("Cache failure for %s: %s" %
                                  (req.ni_name.get_url(), str(e)))
                    return False
                
            # Put the NDO in the cache if its a PUBLISH request
            elif req.req_type == HTTPRequest.HTTP_PUBLISH:
                # Add local publish if requested
                do_local = True

            # Do a local search if its a SEARCH request
            elif req.req_type == HTTPRequest.HTTP_SEARCH:
                # Probably call the Lucene search process
                # To be done later - skip for now
                return True


        # Build lists from each source and then chain them together
        # For Publish or Search do operation locally if requested
        if do_local:
            ll0 = [ self.authority ]
        else:
            ll0 = []

        # Look for http_auth key in affiliated data
        if req_msg.json_in.has_key("http_auth"):
            ll0.append(req_msg.json_in["http_auth"])
            
        # See if there is a locliat in the json_in field
        # Could either be a single string or a list already
        if req_msg.json_in.has_key("loclist"):
            ll1 = req_msg.json_in["loclist"]
            # Worry about unicode
            if type(ll1) == StringType:
                ll1 = [ ll1 ]
            elif type(ll1) != ListType:
                ll1 = []
        else:
            ll1 = []

        # Add next hops from Redis database
        try:
            ll2 = self.redis_conn.hvals(self.nexthop_key)
            self.logdebug("Next hops: %s" % str(ll2))
            # Gets empty list if key not present
        except Exception, e:
            self.logerror("Unable to retrieve nexthop list from Redis: %s" %
                          str(e))
            return False

        self.logdebug("Raw location list is %s" % str(" ".join(chain(ll0, ll1, ll2))))

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
        # but don't start it yet - wait till first request is sent
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
        """
        @brief Request managememt thread loop.

        @detail
        Loop until keep_running is set False by shutdown routine.

        The loop initially hangs up waiting on the action_needed semaphore.
        This can be set either when a new request arrives or, when using
        multiple asynchronous processes, when a process terminates so that
        there is a spare process to give the next request to.

        The semaphore wait also has a timeout so that the wait can terminate
        even if there is no work to do.  For versions of Python after 2.7
        the return value from wait is a boolean that is True if the semaphore
        was really set and False if the timeout triggered the return. In Python
        2.6 and earlier the wait always returns None and so this is not very
        useful.   We don't rely on this return value.

        Clear the semaphore and look to see what has to be done.

        With the request queue locked, scan the queue of current requests
        looking for the next request with a location to send to.
        (this is somewhat inefficient if we are running a large number of
        processes in parallel as there might be quite a few requests that are
        pending so that there may be lots of requests that have been completed
        and so really need not be scanned aagin.  For the time being we'll
        assume that we aren't dealing with lots of requests and start at the
        beginning every time.)  Because of the potential limit on the number
        of parallel processes in progress for any one request, you can't
        just start where you left off because there might be earlier requests
        that still have locations to be processed.
        """
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
                # Need this flag because may need to 'continue' from nested loop
                wait_for_event = False

                # Find the request to process next
                curr_req = None
                http_host = None
                http_index = None
                for req in self.curr_reqs:
                    # Check if this is first look at this request
                    if not req.proc_started:
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
            # Check for local request (PUBLISH and SEARCH only)
            form_params = {}

            form_params["msgid"] = curr_req.bpq_data.bpq_id

            if curr_req.json_in.has_key("loclist"):
                ll = curr_req.json_in["loclist"]
                if type(ll) == ListType:
                    if len(ll) > 0:
                        form_params["loc1"] = ll[0]
                    if len(ll) > 1:
                        form_params["loc2"] = ll[1]            

            local_req_type = curr_req.req_type
            if curr_req.req_type == HTTPRequest.HTTP_SEARCH:
                form_params["tokens"] = curr_req.bpq_data.bpq_val
                if http_host == self.authority:
                    local_req_type = HTTPRequest.HTTP_SEARCH_LOCAL

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

                if http_host == self.authority:
                    local_req_type = HTTPRequest.HTTP_PUBLISH_LOCAL

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
                                          args=(local_req_type,
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
                    self.handle_result(action_req(local_req_type,
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
        rv, req_id, http_index, status, response, metadata = result_tuple
        self.logdebug("Received result status %d for request #%d "
                      "for request id %s" %
                      (status, http_index, req_id))
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
                        self.logdebug("Updated GET result: %s" % response)
                    # Combine metadata
                    if req_msg.metadata is None:
                        req_msg.metadata = NetInfMetaData()
                    req_msg.metadata.insert_resp_metadata(metadata)
                else:
                    # PUBLISH and SEARCH - concatentate responses
                    src = req_msg.http_host_list[http_index]
                    self.logdebug("%s response format: %s" % (req_msg.req_type,
                                                              req_msg.json_in.get("rform", "?")))
                                                              
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
                # Move concatentated PUBLISH and SEARCH response to disk file
                if req_msg.req_type != HTTPRequest.HTTP_GET:
                    if req_msg.result is None:
                        # No useful results have been received
                        req_msg.result = StringIO.StringIO()
                        if req_msg.json_in.get("rform") == "json":
                            req_msg.result.write('{ "(NULL)" : '
                                                 '"No results received"')
                        else:
                            req_msg.result.write("No results received\n")
                    if req_msg.json_in.get("rform") == "json":
                        req_msg.result.write("}")
                    try:
                        fd, response_file = tempfile.mkstemp(dir=self.tempdir)
                        fo = os.fdopen(fd, "wb")
                        fo.write(req_msg.result.getvalue())
                        fo.close()
                        req_msg.result = response_file
                    except Exception, e:
                        splogerror("Writing responses to temp file %s failed: %s" %
                                   (response_file, str(e)))
                        req_msg.result.close()
                        req_msg.result = None

                    self.logdebug("Written response to %s" % response_file)
                    

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
                             "localhost", mprocs=1, per_req_limit=1)
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
    rv = http_action.add_new_req(req)
    if not rv:
        logger.info("Adding request failed correctly on account of nowhere to get from")

    # Put some entries in the next hop database
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
        global test_run
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
    
