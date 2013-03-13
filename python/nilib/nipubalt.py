#!/usr/bin/python
"""
@package nilib
@file nipub.py
@brief Command line client to perform a NetInf 'publish' operation using either
HTTP or DTN convergence layer.
@version $Revision: 0.04 $ $Author: elwynd $
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

===============================================================================#

@code
Revision History
================
Version   Date       Author         Notes
1.1       12/02/2013 Elwyn davies   Modified so that publish_with_.. functions
                                    can be used independent of command line
                                    driver sothat can be used with netinffs.
                                    Failures in these routines now raise
                                    PublishFail rather than calling sys.exit.
1.0       03/02/2013 Elwyn Davies   Cloned from nipub.py. Remove unimplemented
                                    publish of web page.  Added access via DTN
                                    convergence layer.
@endcode
"""
import sys
import os.path
import  random
from optparse import OptionParser
import urllib2
import magic
import json

import dtnapi
from dtn_api_const import QUERY_EXTENSION_BLOCK, METADATA_BLOCK

import mimetools
import email.parser
import email.message
from ni import ni_errs, ni_errs_txt, NIname, NIproc, NIdigester
from encode import *
import streaminghttp
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

##@var DIGEST_DFLT
# Default digest hashing algorithm's name in ni.py
DIGEST_DFLT = "sha-256"

#===============================================================================#
class PublishFailure(Exception):
    """
    @brief Exception raised by publish_with_xxx routines - provokes exit
    """
    def __init__(self, reason, code):
        """
        @brief constructor
        @param resaon string explanation string priented if verbose is True
        @param code integer return code to be givem to sys.exit
        """
        self.reason = reason
        self.code = code
        return

    def __str__(self):
        return "Error: publish failed - %s" % self.reason

#===============================================================================#
def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    #print string
    return


#-------------------------------------------------------------------------------#
def publish_with_http(ni_name, destination, authority, hash_alg, ext, locs, 
                      scheme, full_put, file_name, rform, verbose):
    """
    @brief Action a NetInf publish request using the HTTP convergence layer
    @param ni_name NIname object instance or None - ni URI to publish if
                          given on comand line - otherwise will be constructed
    @param destination string netloc (FQDN or IP address with optional port)
                              indicating where to send publish request
    @param authority string netloc component to insert into ni name (may be "")
    @param hash_alg string name of hash algorithm used for ni URI
    @param ext string additional information to send with request if any
    @param locs list of strings with locators to publish
    @param scheme URI scheme used for ni URI
    @param full_put boolean True if the file_name with the content was given
    @param file_name string name of file to publish or None if only doing metadata
    @param rform string request format of response
    @param verbose bolean indicates how much error message output is produced
    @return 2-tuple - target - string the actual ni name published
                      payload - string - the response received on publication
    """
    
    # Where to send the publish request.
    http_url = "http://%s/netinfproto/publish" % destination
    debug("Publishing via: %s" % http_url)

    # Handle full_put = True cases - we have a file with the octets in it
    if full_put:
        # Create NIdigester for use with form encoder and StreamingHTTP
        ni_digester = NIdigester()

        # Install the template URL built from the scheme, the authority and the digest algorithm
        rv = ni_digester.set_url((scheme, authority, "/%s" % hash_alg))
        if rv != ni_errs.niSUCCESS:
            raise PublishFailure("Cannot construct valid ni URL: %s" %
                                 ni_errs_txt[rv], -10)
        debug(ni_digester.get_url())

        # Open the file if possible
        try:
            f = open(file_name, "rb")
        except Exception, e :
            raise PublishFailure("Unable to open file %s: Error: %s" %
                                 (file_name, str(e)), -11)

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

        param_list = [octet_param,
                      ("URI",       uri_dict),
                      ("msgid",     str(random.randint(1, 32000))),
                      ("ext",       ext),
                      ("fullPut",   "yes"),
                      ("rform",     rform)]
    else:
        # full_put = False case
        # No need for complicated multipart parameters
        param_list = [("URI",       ni_name.get_url()),
                      ("msgid",     str(random.randint(1, 32000))),
                      ("ext",       ext),
                      ("fullPut",   "no"),
                      ("rform",     rform)]
        
    if (locs is not None):
        param_list.append(("loc1", locs[0]))
    else:
        param_list.append(("loc1", ""))
    if ((locs is not None) and (len(locs) >= 2)):
        param_list.append(("loc2", locs[1]))
    else:
        param_list.append(("loc2", ""))
        
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
        f.close()
        raise PublishFailure("Unable to create request for http URL %s: %s" %
                             (http_url, str(e)), -12)

    # Get HTTP results
    try:
        http_object = urllib2.urlopen(req)
    except Exception, e:
        if full_put:
            f.close()
        raise PublishFailure("Unable to access http URL %s: %s" %
                             (http_url, str(e)), -13)

    if full_put:
        f.close()
        target = octet_param.get_url()
    else:
        target = ni_name.get_url()
    debug("Sent request: URL: %s" % target)


    # Get message headers
    http_info = http_object.info()
    http_result = http_object.getcode()
    debug("HTTP result: %d" % http_result)
    debug("Response info: %s" % http_info)
    debug("Response type: %s" % http_info.gettype())

    # Read results into buffer
    payload = http_object.read()
    http_object.close()
    debug(payload)

    # Report outcome
    if (http_result != 200):
        raise PublishFailure("Unsuccessful publish request returned HTTP code %d" %
                             http_result, -14) 

    # Check content type of returned message matches requested response type
    ct = http_object.headers["content-type"]
    if rform == "plain":
        if ct != "text/plain":
            raise PublishFailure("Expecting plain text (text/plain) response "
                                 "but received Content-Type: %s" % ct, -15)
    elif rform == "html":
        if ct != "text/html":
            raise PublishFailure("Expecting HTML document (text/html) response "
                                 "but received Content-Type: %s" % ct, -16)
    else:
        if ct != "application/json":
            raise PublishFailure("Expecting JSON coded (application/json) "
                                 "response but received Content-Type: %s" % ct,
                                 -17)

    return (target, payload)

#-------------------------------------------------------------------------------#
def publish_with_dtn(ni_name, destination, authority, hash_alg, ext_json, locs, 
                     scheme, full_put, file_name, rform, verbose):
    """
    @brief Action a NetInf publish request using the HTTP convergence layer
    @param ni_name NIname object instance or None - ni URI to publish if
                          given on comand line - otherwise will be constructed
    @param destination string netloc (FQDN or IP address with optional port)
                              indicating where to send publish request
    @param authority string netloc component to insert into ni name (may be "")
    @param hash_alg string name of hash algorithm used for ni URI
    @param ext_json dictionary additional information to send with request if any
                               in the form of a JSON dictionary or None
    @param locs list of strings with locators to publish - maybe None
    @param scheme URI scheme used for ni URI
    @param full_put boolean True if the file_name with the content was given
    @param file_name string name of file to publish or None if only doing metadata
    @param rform string request format of response
    @param verbose bolean indicates how much error message output is produced
    @return 2-tuple - target - string the actual ni name published
                      payload - string - the response received on publication
    """
    
    debug("Publishing via: %s" % destination)

    # Handle full_put = True cases - we have a file with the octets in it
    if full_put:
        if ni_name is None:
            # Make a ni_name template from specified components
            ni_name = NIname((scheme, authority, "/%s" % hash_alg))

            # Construct the digest from the file name and the template
            rv = NIproc.makenif(ni_name, file_name)
            if rv != ni_errs.niSUCCESS:
                raise PublishFailure("Unable to construct digest of file %s: %s" %
                                     (file_name, ni_errs_txt[rv]), -20)
        else:
            # Check the ni_name and the file match
            rv = Niproc.checknif(ni_name, file_name)
            if rv != ni_errs.niSUCCESS:
                raise PublishFailure("Digest of file %s does not match ni_name %s: %s" %
                                     (file_name,
                                      ni_name.get_url(),
                                      ni_errs_txt[rv]), -21)

        # Guess the mimetype of the file
        m = magic.Magic(mime=True)
        ctype = m.from_file(file_name)
        debug("Content-Type: %s" % ctype)
        if ctype is None:
            # Guessing didn't work - default
            ctype = "application/octet-stream"

    else:
        ctype = None

    target = ni_name.get_canonical_ni_url()
    debug("Using URI string: %s" % target)

    # Add extra items to ext_json to pass across as metadata
    ext_json["ni"] = target
    if ctype is not None:
        ext_json["ct"] = ctype
    if authority != "":
        ext_json["http_auth"] = authority
    # Send at most two locators as a list
    if (locs is not None):
        ext_json["loclist"] = locs[:2]
    ext_json["fullPut"] = full_put
    ext_json["rform"] = rform
    
    # Create a connection to the DTN daemon
    dtn_handle = dtnapi.dtn_open()
    if dtn_handle == -1:
        raise PublishFailure("Error: unable to open connection with DTN daemon",
                             -22)

    # Generate EID + service tag for service to be accessed via DTN
    if destination is None:
        remote_service_eid = \
                    dtnapi.dtn_build_local_eid(dtn_handle,
                                               "netinfproto/service/publish")
        i = remote_service_eid.find("/netinfproto")
        destination = remote_service_eid[:i]
    else:                           
        remote_service_eid = destination + "/netinfproto/service/publish"

    # Add destination to locs if it isn't there already
    if locs is None:
        locs = []
    if destination not in locs:
        locs.append(destination)
    
    # Generate the EID and service tag for this service
    local_service_eid = dtnapi.dtn_build_local_eid(dtn_handle,
                                                   "netinfproto/app/response")
    debug("Local Service EID: %s" % local_service_eid)
    debug("Remote Service EID: %s" % remote_service_eid)

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
    bpq.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_PUBLISH)
    bpq.set_matching_rule(BPQ.BPQ_MATCHING_RULE_EXACT)
    bpq.set_src_eid(local_service_eid)
    sent_msgid = str(random.randint(1, 32000))
    bpq.set_bpq_id(sent_msgid)
    bpq.set_bpq_val(target)
    bpq.clear_frag_desc()

    # Build an extension blocks structure to hold the block
    ext_blocks =  dtnapi.dtn_extension_block_list(1)

    # Construct the extension block
    bpq_block = dtnapi.dtn_extension_block()
    bpq_block.type = QUERY_EXTENSION_BLOCK
    bpq_block.flags = 0
    bpq_block.data = bpq.build_for_net()
    ext_blocks.blocks.append(bpq_block)

    # Build an extension blocks structure to hold the block
    meta_blocks =  dtnapi.dtn_extension_block_list(2)
            
    # Build a metadata block for JSON data
    md = Metadata()
    md.set_ontology(Metadata.ONTOLOGY_JSON)
    md.set_ontology_data(json.dumps(ext_json))
    json_block = dtnapi.dtn_extension_block()
    json_block.type = METADATA_BLOCK
    json_block.flags = 0
    json_block.data = md.build_for_net()
    meta_blocks.blocks.append(json_block)

    # Set up payload and placeholder if needed
    if full_put:
        # No placeholder required (obviously!)        
        pt = dtnapi.DTN_PAYLOAD_FILE
        pv = file_name
    else:
        # DTN bundle always has a payload - distinguish
        # zero length file form no content available
        # Payload is the empty string sent via memory
        pt = dtnapi.DTN_PAYLOAD_MEM
        pv = ""
        # Add a payload placeholder metablock
        md = Metadata()
        md.set_ontology(Metadata.ONTOLOGY_PAYLOAD_PLACEHOLDER)
        md.set_ontology_data("No content supplied")
        pp_block = dtnapi.dtn_extension_block()
        pp_block.type = METADATA_BLOCK
        pp_block.flags = 0
        pp_block.data = md.build_for_net()
        meta_blocks.blocks.append(pp_block)

    # We want delivery reports and publication reports
    # (and maybe deletion reports?)
    dopts = dtnapi.DOPTS_DELIVERY_RCPT | dtnapi.DOPTS_PUBLICATION_RCPT
    # - Send with normal priority.
    pri = dtnapi.COS_NORMAL
    # NetInf bundles should last a while..
    exp = (24 *60 * 60)

    # Send the bundle
    bundle_id = dtnapi.dtn_send(dtn_handle, regid, local_service_eid,
                                remote_service_eid, local_service_eid,
                                pri, dopts, exp, pt, pv, 
                                ext_blocks, meta_blocks, "", "")
    if bundle_id == None:
        raise PublishFailure("dtn_send failed - %s" %
                             dtnapi.dtn_strerror(dtnapi.dtn_errno(dtn_handle)),
                             -23)

    # Wait for a reponse - maybe also some reports
    while(True):
        # NOTE: BUG in dtnapi - timeout is in msecs
        recv_timeout = 2000 * 60
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

                elif bpq_bundle.status_report.flags == dtnapi.STATUS_PUBLISHED:
                    if verbose:
                        print("Received publication report re from %s sent %d seq %d" %
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
                raise PublishFailure("Received bundle payload not in file - "
                                     "ignoring bundle", -24)
            
            # Have to delete this file before an error exit or if empty
            pfn = bpq_bundle.payload
            l = len(pfn)
            if pfn[l-1] == "\x00":
                pfn = pfn[:-1]
            debug("Got incoming bundle with response in file %s" % pfn)

            # Does the bundle have a BPQ block
            bpq_data = None
            if bpq_bundle.extension_cnt == 0:
                os.remove(pfn)
                raise PublishFailure("Error: Received bundle with no "
                               "extension block.", -25)
                          
            for blk in bpq_bundle.extension_blks:
                if blk.type == QUERY_EXTENSION_BLOCK:
                    bpq_data = BPQ()
                    if not bpq_data.init_from_net(blk.data):
                        os.remove(pfn)
                        raise PublishFailure("Error: Bad BPQ block received",
                                             -26)
    
            if bpq_data is None:
                os.remove(pfn)
                raise PublishFailure("Error: Received bundle with no BPQ block "
                                     "in extension blocks", -27)

            debug(bpq_data)
            # OK.. got the response - finish with daemon
            break
                
        elif dtnapi.dtn_errno(dtn_handle) != dtnapi.DTN_ETIMEOUT:
            raise PublishFailure(dtnapi.dtn_strerror(dtnapi.dtn_errno(dtn_handle)),
                                 -28)
        else:
            raise PublishFailure("dtn_recv timed out without receiving "
                                 "response bundle", 1)
                           
    dtnapi.dtn_close(dtn_handle)

    # Check the BPQ data is right
    bpq.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_PUBLISH)
    bpq.set_matching_rule(BPQ.BPQ_MATCHING_RULE_EXACT)
    if bpq_data.bpq_kind != BPQ.BPQ_BLOCK_KIND_PUBLISH:
        raise PublishFailure("Returned BPQ block is not PUBLISH kind: %d" %
                             bpq_data.bpq_kind, -29)
    if bpq_data.matching_rule != BPQ.BPQ_MATCHING_RULE_NEVER:
        raise PublishFailure("Returned BPQ block does not have NEVER matching rule: %d" %
                             bpq_data.matching_rule, -30)
    if bpq_data.bpq_id != sent_msgid:
        raise PublishFailure("Returned BPQ block has unmatched msgis %s vs %s" %
                             (bpq_data.bpq_id, sent_msgid), -31)

    # Verify the format of the response (a bit)
    try:
        pfd = open(pfn, "rb")
        payload = pfd.read()
        pfd.close()
        os.remove(pfn)
    except Exception, e:
        raise PublishFailure("Failed to read response from payload file %s" %
                             pfn, -32)

    if rform == "json":
        try:
            payload_json = json.loads(payload)
        except Exception, e:
            raise PublishFailure("Alleged JSON response is not valid JSON string: %s" %
                                 payload, -33)
            
    debug("publish_via_dtn completed")
    
    return (target, payload)

#-------------------------------------------------------------------------------#
def py_nipubalt():
    """
    @brief Command line program to perform a NetInf 'publish' operation using http
    @brief convergence layer.
    
    Uses NIproc global instance of NI operations class

    Run:
    
    >  nipubalt.py --help

    to see usage and options.

    Exit code is 0 for success, 1 if HTTP returned something except 200,
    and negative for local errors.
    """
    
    # Options parsing and verification stuff
    usage = "%%prog %s\n       %%prog %s\n%s\n%s" % \
            ("[-q] [-e] [-j|-v|-w|-p] -f <pathname of content file> -d <digest alg> [-l <FQDN - locator>]{1,2}",
             "[-q] [-e] [-j|-v|-w|-p] [-f <pathname of content file>] -n <ni name> [-l <FQDN - locator>]{0,2}",
             "          -- publish file via NI URI over HTTP and/or DTN",
             "At least one locator must be given either as part of the -n option or via a -l option.\n"
             "Locators given with -l options can optionally be prefixed with the HTTP scheme (http://) or \n"
             "the DTN scheme (dtn://).  If a -l option is given, this is used to determine the initial\n"
             "publication destination and the convergence layer used will be HTPP unless the -l option\n"
             "explicitly gives the DTN scheme prefix.  If there are no -l options but the -n option has\n"
             "a netloc compnent (FQDN or IP address with optional port) the this will be used with the\n"
             "HTTP convergence layer\n"
             "The response will be sent as HTML document (-w), plain text (-p), or JSON (-v or -j)\n"
             "Unless -q is specified, the response is sent to standard output.\n"
             "For a JSON response, it can either be output as a 'raw' JSON string (-j) or pretty printed (-v).\n"
             "If none of  -j, -v, -w or -p are specified, a raw JSON response will be requested.")
    parser = OptionParser(usage)
    
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="Pathname for local file to be published.")
    parser.add_option("-d", "--digest", dest="hash_alg",
                      type="string",
                      help="Digest algorithm to be used to hash content "
                           "and create NI URI. Defaults to sha-256.")
    parser.add_option("-n", "--name", dest="ni_name",
                      type="string",
                      help="Complete ni name. If specified with a file or "
                           "HTTP URL, the digest generated from the content "
                           "will be checked against th digest in the name.")
    parser.add_option("-e", "--ext", dest="ext",
                      type="string",
                      help="A JSON encoded object to be sent as the 'ext' "
                           "parameter for the Publish message.")
    parser.add_option("-l", "--loc", dest="locs", action="append",
                      type="string",
                      help="A locator where NI might be retrieved. Maybe be "
                           "zero to two if -n is present and has a non-empty netloc. "
                           "Otherwise must be one or two. HTTP or DTN is sent to first "
                           "loc if present. Otherwise sent to netloc (authority) in -n."
                           "NOTE: this precedence differs from earlier versions of nipub.")
    parser.add_option("-q", "--quiet", default=False,
                      action="store_true", dest="quiet",
                      help="Suppress textual output")
    parser.add_option("-j", "--json", default=False,
                      action="store_true", dest="json_raw",
                      help="Request response as JSON string and output raw JSON "
                           "string returned on stdout.")
    parser.add_option("-v", "--view", default=False,
                      action="store_true", dest="json_pretty",
                      help="Request response as JSON string and pretty print "
                           "JSON string returned on stdout.")
    parser.add_option("-w", "--web", default=False,
                      action="store_true", dest="html",
                      help="Request response as HTML document and output HTML "
                           "returned on stdout.")
    parser.add_option("-p", "--plain", default=False,
                      action="store_true", dest="plain",
                      help="Request response as plain text document and output text "
                           "returned on stdout.")


    (options, args) = parser.parse_args()

    # Check command line options:
    # Arguments -q, -e, -w, -p, -j and -v are optional; there must be one of a -n with an authority in it or at least one -l.
    # If -n option is specified then there must not be a -d.
    # If -d is specified, there must be a -f.
    # If -n is specified, -f may be specified - otherwise only metadata is published. No leftover arguments allowed.
    # Specifying more than one of -w, -p, -j and -v is inappropriate.
    if len(args) != 0:
        parser.error("Unrecognized arguments %s supplied." % str(args))
        sys.exit(-1)
    if ((options.locs is not None) and (len(options.locs) > 2)):
        parser.error("Initial version only supports two locators (-l/--loc).")
        sys.exit(-1)
    if ((options.ni_name == None) and (options.locs == None)):
        parser.error("Must specify a locator (-l/--loc) or a name (-n/--name) with a netloc component to define where to send the request.")
        sys.exit(-1)
    if ((options.hash_alg != None) and (options.ni_name != None)):
        parser.error("Cannot specify both digest algorithm to be used (-d) and complete ni name with algorithm and digest (-n).")
        sys.exit(-1)
    fc = 0
    for flag in [options.json_raw, options.json_pretty, options.html, options.plain]:
        if flag:
            fc += 1
    if fc > 1:
        parser.error("Should specify at most one response type argument out of -j, -v, -w and -p.")
        sys.exit(-1)

    file_name = None
    
    if options.file_name != None:
        file_name = os.path.abspath(options.file_name)
        # Check the file is readable
        if not os.access(file_name, os.R_OK):
            if verbose:
                print("File to be published %s is not readable" % file_name)
            sys.exit(1)
        full_put = True
    else:
        full_put = False
    debug("full_put: %s" %full_put)

    verbose = not options.quiet

    if ((options.locs is not None) and (len(options.locs) > 2)):
        if verbose:
            print "Warning: only first two -l/--loc locators will be published"

    #  If we have a full ni name (-n option) given..
    if options.ni_name is not None:
        # Check the validity of the ni name
        try:
            ni_name = NIname(options.ni_name)
        except Exception, e:
            if verbose:
                print("Error: value of -n/--name option '%s' is not a valid ni name" %
                      options.ni_name)
            sys.exit(-3)
        rv = ni_name.validate_ni_url()
        if rv != ni_errs.niSUCCESS:
            if verbose:
                print("Error: value of -n/--name option '%s' is not a valid ni name" %
                      options.ni_name)
            sys.exit(-3)

        # Extract the scheme and hash algorithm from the name
        scheme = ni_name.get_scheme()
        hash_alg = ni_name.get_alg_name()

        # If there is a -l option, that is where the request is sent.
        nl = ni_name.get_netloc()
        if ((options.locs is None) and (nl == "")) :
            print("Error: name (-n/--name) must have a netloc if no locator options given,")
            sys.exit(-4)
        # NOTE: The following logic ie reversed from earlier versions so that 
        # can force use of DTN convergence layer with a -l option.
        if nl == "":
            # Already checked this exists
            destination = options.locs[0]
        else:
            destination = nl
        authority = nl
    else:
        # No ni name given.. where to send must be locs[0] and
        # there may be a -d option - use DIGEST_DFLT otherwise
        # Default to ni scheme
        ni_name = None
        destination = options.locs[0]
        authority = ""
        if options.hash_alg is None:
            hash_alg = DIGEST_DFLT
        else:
            hash_alg = options.hash_alg
        scheme = "ni"
        
    # Check if the ext parameter is a valid json string
    if options.ext is not None:
        try:
            ext_json = json.loads(options.ext)
        except Exception, e:
            if verbose:
                print("Error: the -e/--ext parameter value '%s' is not "
                      "a valid JSON encoded object." % options.ext)
            sys.exit(-3)
        ext = options.ext
    else:
        ext_json = {}
        ext = ""
            
    # Determine type of response to request
    if options.html:
        rform = "html"
    elif options.plain:
        rform = "plain"
    else:
        rform = "json"
    debug("Response type requested: %s" % rform)

    # Determine convergence layer to use
    try:
        if destination.startswith(DTN_SCHEME):
            target, payload = publish_with_dtn(ni_name, destination, authority,
                                               hash_alg, ext_json, options.locs,
                                               scheme, full_put, file_name,
                                               rform, verbose)
        else:
            if destination.startswith(HTTP_SCHEME):
                destination = destination[len(HTTP_SCHEME):]
            target, payload = publish_with_http(ni_name, destination, authority,
                                                hash_alg, ext, options.locs,
                                                scheme, full_put, file_name,
                                                rform, verbose)
    except PublishFailure, pf:
        if verbose:
            print(str(pf))
        sys.exit(pf.code)
    except Exception, e:
        print("Unexpected exception: %s" % str(e))
        sys.exit(-4)

    # If output of response is expected, print in the requested format
    if target == None:
        if verbose:
            if payload is None:
                print "Publication failed - no response received"
            else:
                print "Publication failed: response was: %s" % payload
        sys.exit(1)
        
    if verbose:
        print "Publication of %s successful" % target

        if rform == "plain" or rform == "html":
            print payload
        else:
            # JSON cases
            try:
                json_report = json.loads(payload)
            except Exception, e:
                if verbose:
                    print("Error: Could not decode JSON report '%s': %s" % (payload,
                                                                            str(e)))
                sys.exit(-7)

            if options.json_pretty:
                print json.dumps(json_report, indent = 4)
            else:
                # Raw JSON case (default or -j)
                print json.dumps(json_report, separators=(",", ":"))

    sys.exit(0)

#===============================================================================#
if __name__ == "__main__":
    py_nipubalt()
