#!/usr/bin/python
"""
@package nilib
@file nigetalt.py
@brief Command line client to perform a NetInf 'get' operation using either HTTP
@brief convergence layer or DTN convergence layer.
@version $Revision: 0.05 $ $Author: elwynd $
@version Copyright (C) 2013 Trinity College Dublin and Folly Consulting Ltd
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

@detail
Performs NetInf GET operation for a specified ni URI using either the HTTP
convergence layer or the DTN convergence layer.

The choice of convergence layer to use is determined by the form of the
locator used to specify whence the request should be actioned.

If the locator is a dtn scheme URI the DTN will be used; otherwise if the locator
is explicitly an HTTP scheme URI or just a bare FQDN with optional port (i.e.,
URI netloc field) then HTTP will be used.  For the HTTP case the locator can be
incorporated in the ni name.

The HTTP version accesses the URL:
http://<specified netloc>/netinfproto/get

The DTN version accesses the EID
dtn://<specified netloc>/netinfproto/service/get

If DTN is to be used a DTN2 dtnd instance must be running on the local machine
(or one accessible over a permanent UDP connection).

@code
Revision History
================
Version   Date       Author         Notes
1.0       31/01/2013 Elwyn Davies   Created using niget.py, nidtnproc.py, nigetlist.py. 
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

import dtnapi
from dtn_api_const import QUERY_EXTENSION_BLOCK, METADATA_BLOCK

from ni import ni_errs, ni_errs_txt, NIname, NIproc
from nifeedparser import DigestFile, FeedParser
from nidtnbpq import BPQ
from nidtnmetadata import Metadata

#===============================================================================#
# GLOBAL CONSTANTS

##@var HTTP_SCHEME
# string scheme prefix for HTTP URIs
HTTP_SCHEME = "http://"

##@var DTN_SCHEME
# string scheme prefix for DTN URIs
DTN_SCHEME = "dtn://"

#===============================================================================#
def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    print string
    return

#===============================================================================#
def get_via_http(ni_url, http_host, file_name, verbose, lax):
    """
    @brief Perform a NetInf 'get' from the http_host for the ni_url.
    @param ni_url object instance of NIname with ni name to be retrieved
    @param http_host string HTTP host name to be accessed
                            (FQDN or IP address with optional port number)
    @param file_name string path to save content if returned
    @param verbose boolean if True print error messages, otherwise be quiet
    @param lax boolean if True return content file even if it doesn't verify
    @return 3-tuple with:
                dictionary containing returned JSON metadata decoded
                boolean indicating if content was obtained (and is in file_name
                boolean indicating if contenmt failed to verify if lax was True
                
    Assume that ni_url has a valid ni URI
    """
    # Record if content failed to verify (for lax case)
    faulty = False

    # Record if content was retrieved at all
    got_content = False

    # Must be a complete ni: URL with non-empty params field
    rv = ni_url.validate_ni_url(has_params = True)
    if (rv != ni_errs.niSUCCESS):
        if verbose:
            print("Error: %s is not a complete, valid ni scheme URL: %s" %
                  (ni_url.get_url(), ni_errs_txt[rv]))
            sys.exit(-10)

    # Generate canonical form (no netloc, ni scheme) URI for ni name
    ni_url_str = ni_url.get_canonical_ni_url()
    
    # Generate NetInf form access URL
    http_url = "http://%s/netinfproto/get" % http_host
    
    # Set up HTTP form data for get request
    sent_msgid = str(random.randint(1, 32000)) 
    form_data = urllib.urlencode({ "URI":   ni_url_str,
                                   "msgid": sent_msgid,
                                   "ext": ""})

    # Send POST request to destination server
    try:
        http_object = urllib2.urlopen(http_url, form_data)
    except Exception, e:
        if verbose:
            print("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        sys.exit(-11)

    # Get HTTP result code
    http_result = http_object.getcode()

    # Get message headers - an instance of email.Message
    http_info = http_object.info()
    debug("Response type: %s" % http_info.gettype())
    debug("Response info:\n%s" % http_info)

    if (http_result != 200):
        if verbose:
            print("HTTP GET request returned HTTP code %d" % http_result)
        buf = http_object.read()
        debug("HTTP Response: %s" % buf)
        http_object.close()
        sys.exit(-12)

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
    try:
        fo = open(file_name, "wb")
    except Exception, e:
        if verbose:
            print("Error: Unable to open file %s for writing." % file_name)
        sys.exit(-13)
    debug("Writng content to %s" % file_name)

    digester = DigestFile(file_name, fo, ni_url.get_hash_function())

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
        if verbose:
            print("Error: HTTP Response was not a correctly formed MIME object")
        os.remove(file_name)
        sys.exit(-14)
        
    # Verify length 
    if ((obj_length != None) and (payload_len != obj_length)):
        if verbose:
            print("Error: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))
        os.remove(file_name)
        sys.exit(-15)
        
    debug( msg.__dict__)
    # If the msg is multipart this is a list of the sub messages
    parts = msg.get_payload()
    debug("Multipart: %s" % str(msg.is_multipart()))
    if msg.is_multipart():
        debug("Number of parts: %d" % len(parts))
        if len(parts) != 2:
            if verbose:
                print("Error: HTTP Multipart response from server does not have two parts.")
            os.remove(file_name)
            sys.exit(-16)
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
        if verbose:
            print("Error: First or only component (metadata) of result is not of type application/json")
        os.remove(file_name)
        sys.exit(-17)

    # Extract the JSON structure
    try:
        json_report = json.loads(json_msg.get_payload())
    except Exception, e:
        if verbose:
            print("Error: Could not decode JSON report '%s': %s" %
                  (json_msg.get_payload(), str(e)))
        os.remove(file_name)
        sys.exit(-18)
    
    debug("Returned metadata for %s:" % ni_url_str)
    debug(json.dumps(json_report, indent = 4))

    msgid = json_report.get("msgid", "")
    if msgid != sent_msgid:
        if verbose:
            print("Returned msgid (%s) does not match request msgid (%s)" %
                  (msgid, sent_msgid))
        os.remove(file_name)
        sys.exit(-19)

    # If the content was also returned..
    if ct_msg != None:
        debug(ct_msg.__dict__)
        digest= digester.get_digest()[:ni_url.get_truncated_length()]
        digest = NIproc.make_b64_urldigest(digest)
        got_content = True
                                          
        # Check the digest
        #print digest, ni_url.get_digest()
        if (digest != ni_url.get_digest()):
            if verbose:
                print("Warning: Digest of %s did not verify" % ni_url.get_url())
            if not lax:
                os.remove(file_name)
                sys.exit(-20)
            faulty = True
    else:
        # Clean up unused temporary file
        os.remove(file_name)
        file_name = None

    return(json_report, got_content, faulty)

#===============================================================================#
def get_via_dtn(ni_url, dtn_eid, file_name, verbose, lax):
    """
    @brief Perform a NetInf 'get' from the http_host for the ni_url.
    @param ni_url object instance of NIname with ni name to be retrieved
    @param dtn_eid string EID for node to be accessed
                            (FQDN or IP address with optional port number)
    @param file_name string path to save content if returned
    @param verbose boolean if True print error messages, otherwise be quiet
    @param lax boolean if True return content file even if it doesn't verify
    @return 3-tuple with:
                dictionary containing returned JSON metadata decoded
                boolean indicating if content was obtained (and is in file_name
                boolean indicating if contenmt failed to verify if lax was True
                
    Assume that ni_url has a valid ni URI
    """
    # Record if content failed to verify (for lax case)
    faulty = False

    # Record if content was retrieved at all
    got_content = False

    # Must be a complete ni: URL with non-empty params field
    rv = ni_url.validate_ni_url(has_params = True)
    if (rv != ni_errs.niSUCCESS):
        if verbose:
            print("Error: %s is not a complete, valid ni scheme URL: %s" %
                  (ni_url.get_url(), ni_errs_txt[rv]))
            sys.exit(-10)

    # Generate canonical form (no netloc, ni scheme) URI for ni name
    ni_url_str = ni_url.get_canonical_ni_url()

    # Generate EID + service tag for service to be accessed via DTN
    remote_service_eid = "dtn://" + dtn_eid + "/netinfproto/service/get"

    # Create a connection to the DTN daemon
    dtn_handle = dtnapi.dtn_open()
    if dtn_handle == -1:
        if verbose:
            print("Error: unable to open connection with DTN daemon")
        sys.exit(-20)

    # Generate the EID and service tag for this service
    local_service_eid = dtnapi.dtn_build_local_eid(dtn_handle,
                                                   "netinfproto/app/response")
    debug("Service EID: %s" % local_service_eid)

    # Check if service_eid registration exists and register if not
    # Otherwise bind to the existing registration
    regid = dtnapi.dtn_find_registration(dtn_handle, local_service_eid)
    if (regid == -1):
        # Need to register the EID.. make it permanent with 'DEFER'
        # characteristics so that bundles are saved if they arrive
        # while the handler is inactive
        # Expire the registration an hour in the future
        exp = 60 * 60
        # The registration is immediately active
        passive = False
        # We don't want to execute a script
        script = ""
        
        regid = dtnapi.dtn_register(dtn_handle, local_service_eid,
                                    dtnapi.DTN_REG_DEFER,
                                    exp, passive, script)
    else:
        dtnapi.dtn_bind(dtn_handle, regid)

    # Build the bundle to send
    # First a suitable BPQ block
    bpq = BPQ()
    bpq.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_QUERY)
    bpq.set_matching_rule(BPQ.BPQ_MATCHING_RULE_EXACT)
    bpq.set_src_eid(local_service_eid)
    sent_msgid = str(random.randint(1, 32000))
    print sent_msgid
    bpq.set_bpq_id(sent_msgid)
    bpq.set_bpq_val(ni_url_str)
    bpq.clear_frag_desc()

    # Don't need to send any metadata or payload placeholder

    # Payload is the empty string sent via memory
    pt = dtnapi.DTN_PAYLOAD_MEM
    pv = ""

    # - We want delivery reports (and maybe deletion reports?)
    dopts = dtnapi.DOPTS_DELIVERY_RCPT
    # - Send with normal priority.
    pri = dtnapi.COS_NORMAL
    # NetInf bundles should last a while..
    exp = (24 *60 * 60)

    # Build an extension blocks structure to hold the BPQ block
    ext_blocks =  dtnapi.dtn_extension_block_list(1)

    # Construct the extension block
    bpq_block = dtnapi.dtn_extension_block()
    bpq_block.type = QUERY_EXTENSION_BLOCK
    bpq_block.flags = 0
    bpq_block.data = bpq.build_for_net()
    ext_blocks.blocks.append(bpq_block)

    # Send the bundle
    bundle_id = dtnapi.dtn_send(dtn_handle, regid, local_service_eid,
                                remote_service_eid, local_service_eid,
                                pri, dopts, exp, pt, pv, 
                                ext_blocks, None, "", "")

    # Wait for a reponse - maybe aalso some reports
    while(True):
        recv_timeout = 2 * 60
        bpq_bundle = dtnapi.dtn_recv(dtn_handle, dtnapi.DTN_PAYLOAD_FILE,
                                     recv_timeout)
        # If bpq_bundle is None then either the dtn_recv timed out or
        # there was some other error.
        if bpq_bundle != None:
            # Filter out report bundles
            if bpq_bundle.status_report != None:
                debug("Received status report")
                if bpq_bundle.status_report.flags == dtnapi.STATUS_DELIVERED:
                    if verbose:
                        print("Received delivery report re from %s sent %d seq %d" %
                              (bpq_bundle.status_report.bundle_id.source,
                               bpq_bundle.status_report.bundle_id.creation_secs,
                               bpq_bundle.status_report.bundle_id.creation_seqno))

                elif bpq_bundle.status_report.flags == dtnapi.STATUS_DELETED:
                    if verbose:
                        print("Received deletion report re from %s sent %d seq %d" %
                              (bpq_bundle.status_report.bundle_id.source,
                               bpq_bundle.status_report.bundle_id.creation_secs,
                               bpq_bundle.status_report.bundle_id.creation_seqno))

                else:
                    if verbose:
                        print("Received unexpected report: Flags: %d" %
                              bpq_bundle.status_report.flags)
                        
                # Wait for more status reports and incoming response
                continue

            # Check the payload really is in a file
            if not bpq_bundle.payload_file:
                if verbose:
                    print("Received bundle payload not in file - ignoring bundle")
                sys.exit(-21)
            
            # Have to delete this file before an error exit or if empty
            pfn = bpq_bundle.payload
            l = len(pfn)
            if pfn[l-1] == "\x00":
                pfn = pfn[:-1]
            debug("Got incoming bundle in file %s" % pfn)

            # Does the bundle have a BPQ block
            bpq_data = None
            if bpq_bundle.extension_cnt == 0:
                if verbose:
                    print("Error: Received bundle with no extension block.")
                os.remove(pfn)
                sys.exit(-22)
                          
            for blk in bpq_bundle.extension_blks:
                if blk.type == QUERY_EXTENSION_BLOCK:
                    bpq_data = BPQ()
                    if not bpq_data.init_from_net(blk.data):
                        if verbose:
                          print("Error: Bad BPQ block received")
                        os.remove(pfn)
                        sys.exit(-23)

            if bpq_data is None:
                if verbose:
                    print("Error: Received bundle with no BPQ block in extension blocks")
                os.remove(pfn)
                sys.exit(-23)

            debug(bpq_data)

            # Does the bundle have a Metadata block of type JSON and optionally
            # a payload placeholder
            json_data = None
            got_content = True
            if bpq_bundle.metadata_cnt > 0:
                debug("Metadata count for bundle is %d" %
                      bpq_bundle.metadata_cnt)
                for blk in bpq_bundle.metadata_blks:
                    if blk.type == METADATA_BLOCK:
                        md = Metadata()
                        if not md.init_from_net(blk.data):
                            if verbose:
                                print("Error: Bad Metadata block received")
                            os.remove(pfn)
                            sys.exit(-24)
                        if md.ontology == Metadata.ONTOLOGY_JSON:
                            json_data = md
                        elif md.ontology == Metadata.ONTOLOGY_PAYLOAD_PLACEHOLDER:
                            got_content = False
                            debug("Have placeholder: %s" % md.ontology_data)
                        else:
                            if verbose:
                                print("Warning: Metadata (type %d) block not processed" %
                                      md.ontology)

            if json_data is not None:
                debug("JSON data: %s" % json_data)
                od = json_data.ontology_data
                if od[-1:] == '\x00':
                    od = od[:-1]
                json_dict = json.loads(od)
            else:
                json_dict = None

            # Check if bundle has a (non-empty) payload even if it has a placeholder
            if (bpq_bundle.payload_len > 0) and not got_content:
                if verbose:
                    print("Error: Bundle has payload placeholder and non-empty payload")
                os.remove(pfn)
                sys.exit(-25)
            

            # Validate the digest if there is content
            faulty = False
            if got_content:
                # Unfortunately there is no easy way to do this without reading the file again.
                # But that lets us copy it into the final destination at the same time.
                # Digest output
                bin_dgst = None

                h = ni_url.get_hash_function()()

                # Open the bundle payload file
                try:
                    fr = open(pfn, "rb")
                except Exception, e :
                    if verbose:
                        print("Error: Cannot open payload file %s: Reason: %s" %
                              (pfn, str(e)))
                    os.remove(pfn)
                    sys.exit(-26)

                # Open the destination file
                try:
                    fw = open(file_name, "wb")
                except Exception, e :
                    if verbose:
                        print("Error: Cannot open destination file %s: Reason: %s" %
                              (file_name, str(e)))
                    fr.close()
                    os.remove(pfn)
                    sys.exit(-26)

                while True:

                    try:
                        l = fr.read(1024)
                    except Exception, e :
                        if verbose:
                            print("Error: Cannot read payload file %s: Reason: %s" %
                                  (fn, str(e)))
                        fr.close()
                        os.remove(pfn)
                        fw.close(0)
                        os.remove(file_name)
                        sys.exit(-27)

                    if len(l) == 0:
                        fr.close()
                        fw.close()
                        break
                     
                    h.update(l)
                    try:
                        fw.write(l)
                    except Exception, e :
                        if verbose:
                            print("Error: Cannot write destination file %s: Reason: %s" %
                                  (file_name, str(e)))
                        fr.close()
                        os.remove(pfn)
                        fw.close(0)
                        os.remove(file_name)
                        sys.exit(-28)

                bin_dgst = h.digest()
                os.remove(pfn)
                
                if len(bin_dgst) != ni_url.get_digest_length():
                    if verbose:
                        print ("Error: Hash had unexpected length (Exp: %d; Actual: %d)" %
                               (self.hash_algs[alg_name][HL], len(dgst)))
                    os.remove(file_name)
                    sys.exit(-29)

                digest = NIproc.make_b64_urldigest(bin_dgst[:ni_url.get_truncated_length()])

                # Check the digest
                debug("Calculated digest: %s; Name digest: %s" %
                      (digest, ni_url.get_digest()))
                if (digest != ni_url.get_digest()):
                    if verbose:
                        print("Warning: Digest of %s did not verify" % ni_url.get_url())
                    if not lax:
                        os.remove(file_name)
                        sys.exit(-30)
                    faulty = True
                      
            # OK.. got the response - finish with daemon
            break
                
        elif dtnapi.dtn_errno(dtn_handle) != dtnapi.DTN_ETIMEOUT:
            if verbose:
                print(dtnapi.dtn_strerror(dtnapi.dtn_errno(dtn_handle)))
            sys.exit(-21)
        else:
            if verbose:
                print("dtn_recv timed out without receiving response bundle")
            sys.exit(1)
                           
    dtnapi.dtn_close(dtn_handle)
    debug("get_via_dtn completed")
    
    return (json_dict, got_content, faulty)

#===============================================================================#
def py_niget():
    """
    @brief Command line program to perform a NetInf 'get' operation using http
    @brief convergence layer.
    
    Uses NIproc global instance of NI operations class

    Run:
    
    >  niget.py --help

    to see usage and options.

    Exit code is 0 for success, 1 if HTTP returned something except 200,
    and negative for local errors.
    """
    
    # Options parsing and verification stuff
    usage = "%prog [-q] [-l] [-d] [-m|-v] [-f <pathname of content file>] [-w <locator>] <ni name>\n" + \
            "Either <ni name> must include location (netloc) from which to retrieve object, or\n" + \
            "a locator must be given with the -w/--whence option.\n" + \
            "The locator may be prefixed with an HTTP ('http://')or DTN ('dtn://') URI scheme identifier.\n" + \
            "If no scheme identifier is given then HTTP is assumed.  The DTN scheme does not accept ports."
    parser = OptionParser(usage)
    
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="File to hold retrieved content. Defaults to hash code in current directory if not present")
    parser.add_option("-w", "--whence", dest="loc",
                      type="string", default=None,
                      help="Locator to which to send NetInf GET request.  May be prefixed with http:// or dtn://")
    parser.add_option("-q", "--quiet", default=False,
                      action="store_true", dest="quiet",
                      help="Suppress textual output")
    parser.add_option("-l", "--lax", default=False,
                      action="store_true", dest="lax",
                      help="Store returned content even if digest doesn't validate")
    parser.add_option("-m", "--metadata", default=False,
                      action="store_true", dest="metadata",
                      help="Output returned metadata as JSON string")
    parser.add_option("-v", "--view", default=False,
                      action="store_true", dest="view",
                      help="Pretty print returned metadata.")

    (options, args) = parser.parse_args()

    # Check command line options - -q, -f, -l, -m, and -v are optional,
    # <ni name> is mandatory
    # -w is optional if <ni name> contains a netloc
    if len(args) != 1:
        parser.error("URL <ni name> not specified.")
        sys.exit(-1)
    verbose = not options.quiet

    # Create NIname instance for supplied URL and validate it
    ni_url = NIname(args[0])

    # Must be a complete ni: URL with non-empty params field
    rv = ni_url.validate_ni_url(has_params = True)
    if (rv != ni_errs.niSUCCESS):
        if verbose:
            print("Error: %s is not a complete, valid ni scheme URL: %s" % (ni_url.get_url(), ni_errs_txt[rv]))
        sys.exit(-2)

    # Generate file name for output if not specified
    if (options.file_name == None):
        options.file_name = ni_url.get_digest()

    # Decide Convergence Layer to use and locator to access
    netloc = ni_url.get_netloc()
    cl = HTTP_SCHEME
    if netloc == "":
        # Must have -w option
        if options.loc is None:
            if verbose:
                print("Error: Must provide a locator either in ni URI or via -w/--whence")
            sys.exit(-3)
        loc = options.loc.lower()
    elif options.loc is not None:
        if verbose:
            print("Warning: -w/--whence locator option overrides netloc in ni URI")
        loc = options.loc.lower()
    else:
        loc = netloc.lower()

    # See if URI scheme was specified
    if loc.startswith(HTTP_SCHEME):
        loc = loc[len(HTTP_SCHEME):]
    elif loc.startswith(DTN_SCHEME):
        loc = loc[len(DTN_SCHEME):]
        cl = DTN_SCHEME
    else:
        ssep = loc.find("://")
        if ssep != -1:
            if verbose:
                print("Error: Convergence Layer for scheme %s is not supported - use dtn or http" %
                      loc[:ssep])
            sys.exit(-4)
        # Default assume HTTP

    # Action the GET according to CL selected
    if cl == HTTP_SCHEME:
        json_report, got_content, faulty = get_via_http(ni_url, loc,
                                                        options.file_name,
                                                        verbose, options.lax)
    else:
        json_report, got_content, faulty = get_via_dtn(ni_url, loc,
                                                       options.file_name,
                                                       verbose, options.lax)

    if options.view:
        print("Returned metadata for %s:" % args[0])
        print json.dumps(json_report, indent = 4)
    elif options.metadata:
        print json.dumps(json_report, separators=(",", ":"))

    if not got_content:
        rv = 1
    elif faulty:
        rv = 2
    else:
        rv = 0

    if verbose and got_content:
        if not faulty:
            print("Content successfully retrieved and placed in file %s." %
                  options.file_name)
        else:
            print("Content retrieved and placed in file %s but digest didn't verify." %
                  options.file_name)
    elif verbose:
        print("Only metadata retrieved")

    sys.exit(rv)
                                                                                                    
#===============================================================================#
if __name__ == "__main__":
    py_niget()

#===============================================================================#
# === Testing ===
# This code can be conveniently tested using test mode of nidtnproc.py.
# You need a DTN2 dtnd daemon running on the same machine and need to know
# what its local EID is (dtn://...).
# Run nidtnproc.py standalone and let the internal tests complete.
# Then run nigetalt.py.
# The code in nidtnproc.py will reflect the request back and add the content
# file /etc/group as payload.
# A command such as:
#  ./nigetalt.py 'ni://tcd.netinf.eu/sha-256;--3eVr68lofft_RqlGiV_R8xSBbj2MUul7zoCK1TO7I'
#  -f aaa -w <EID of local dtnd> -l
# should complete and report that the content didn't verify
# If you generate a correct ni name for the current /etc/group on your system
# a command such as
#  ./nigetalt.py 'ni:///sha-256-32;IEtLRQ' -f aaa -w <EID of local dtnd>
# should complete corectly if IETtLRQ is the right digest.
