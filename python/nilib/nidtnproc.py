#!/usr/bin/python
"""
@package nilib
@file nidtnproc.py
@brief NetInf DTN Convergence layer terminal and gateway to HTTP convergence layer.
@version $Revision: 0.05 $ $Author: stephen $
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

@detail
NetInf DTN Convergence layer terminal and gateway to HTTP convergence layer.

@code
Revision History
================
Version   Date	     Author	    Notes
1.0	  01/01/2013 ElwynDavies    Created.

@endcode
"""

#==============================================================================#
# Standard modules
from threading import Thread
import logging
import Queue
import time
import json
import socket
from select import select
from copy import copy # Shallow copy operation

import pprint

import dtnapi
from dtn_api_const import QUERY_EXTENSION_BLOCK, METADATA_BLOCK

# Nilib modules
from ni import NIname, ni_errs
from nidtnbpq import BPQ
from nidtnmetadata import Metadata
from nidtnevtmsg import MsgDtnEvt, HTTPRequest
from ni_exception import DtnError


#==============================================================================#
# List of classes/global functions in file
__all__ = ['DtnReceive', 'DtnSend'] 
#==============================================================================#
# GLOBAL VARIABLES

##@var NETINF_SERVICE
# string basic service tag for NetInf DTN application interface
NETINF_SERVICE = "netinfproto/service/"

##@var NETINF_SERVICE_ANY
# string service tag pattern for generic NetInf service
NETINF_SERVICE_ANY = NETINF_SERVICE + "*"

##@var NETINF_SERVICE_GET
# string service tag for NetInf GET service
NETINF_SERVICE_GET = NETINF_SERVICE + "get"

##@var NETINF_SERVICE_SEARCH
# string service tag for NetInf SEARCH service
NETINF_SERVICE_SEARCH = NETINF_SERVICE + "search"

##@var NETINF_SERVICE_PUBLISH
# string service tag for NetInf PUBLISH service
NETINF_SERVICE_PUBLISH = NETINF_SERVICE + "publish"

##@var NETINF_SERVICE_RESPONSE
# string service tag for NetInf service actioning all kinds of responses
NETINF_SERVICE_RESPONSE = NETINF_SERVICE + "response"

##@var NETINF_SERVICE_REPORT
# string service tag for NetInf service DTN report destination
NETINF_SERVICE_REPORT = NETINF_SERVICE + "report"

#==============================================================================#

class DtnReceive(Thread):
    """
    @brief Class for handling incoming DTN bundles that contain BPQ blocks

    Registers to receive bundles sent to dtn://<local eid>/netinf_service/*

    Dismantle bundle...
    - Check has BPQ block
    - If so convert to structure; if not ignore bundle
    - Examine BPQ bundle type
    - case type:
      + QUERY
        o is either GET or SEARCH
        o if match_rule is EXACT_MATCH assume GET
          = Save msgid and other data in HTTPRequest structure,
            form NIname object out of name in BPQ query value,
            and pass to HTTP action thread to acquire an HTTP response.
            HTTP action will check local cache and otherwise attempt to
            forward request to other locators.
        o if match_rule is TOKEN_MATCH assume SEARCH
          = Save msgid and other data in HTTPRequest structure and pass
            to HTTP action thread to acquire HTTP response
            possibly including local search
      + RESPONSE
        o check if msgid is in internal data awaiting DTN response list
        o if so send back to HTTP loop
      + PUBLISH
        o is a PUBLISH message
          = build HTTPRequest  structure and pass to HTTP action thread

    In all case the response will (hopefully) eventaully com e back to the
    DtnSend thread (see below).
    """

    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var receive_run
    # boolean set False to end the run of the DTN receive thread

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
    def __init__(self, http_action, logger):
        Thread.__init__(self, name="netinf-dtn-receive")

        # Remember http_action which is where incoming requests are despatched
        assert(http_action is not None)
        self.http_action = http_action

        # Set up logging functions
        self.logger = logger
        self.loginfo = logger.info
        self.logdebug = logger.debug
        self.logerror = logger.error
        self.logwarn = logger.warn

        # Flag to keep the loop running
        self.receive_run = True

    #--------------------------------------------------------------------------#
    def end_run(self):
        self.receive_run = False

     #--------------------------------------------------------------------------#
    def run(self):
        """
        @brief This function loops forever (well more or less) waiting for
               incoming bundles containing BPQ blocks or DTN status reports
               
        This requires it to poll the DTN daemon (yawn).
        The poll periodically drops out in order to check if the thread has
        been terminated (this may not be necessary - check if threads hung
        up in select terminate naturally if the thread is terminated because
        it is a daemon (but the check is cleaner really).
        """
        
        # Create a connection to the DTN daemon
        dtn_handle = dtnapi.dtn_open()
        if dtn_handle == -1:
            raise DtnError("unable to open connection with daemon")

        # Generate the EID and service tag for this service
        self.service_eid = dtnapi.dtn_build_local_eid(dtn_handle,
                                                      NETINF_SERVICE_ANY)
        self.logdebug("Service EID: %s" % self.service_eid)

        # Check if service_eid registration exists and register if not
        # Otherwise bind to the existing registration
        regid = dtnapi.dtn_find_registration(dtn_handle, self.service_eid)
        if (regid == -1):
            # Need to register the EID.. make it permanent with 'DEFER'
            # characteristics so that bundles are saved if theye arrive
            # while the handler is inactive
            # Expire the registration a long time in the future
            exp = 365 * 24 * 60 * 60
            # The registration is immediately active
            passive = False
            # We don't want to execute a script
            script = ""
            
            regid = dtnapi.dtn_register(dtn_handle, self.service_eid,
                                        dtnapi.DTN_REG_DEFER,
                                        exp, passive, script)
            print "Regid 2 %d" % regid
        else:
            dtnapi.dtn_bind(dtn_handle, regid)

        # Wait for 5 seconds before looping
        recv_timeout = 5

        self.loginfo("Entering NetInf DTN receive loop")

        # Now sit and wait for incoming BPQ bundles
        # Note that just using dtn_recv with a timeout doesn't work.
        # The blocking I/O upsets the threading seemingly.
        receive_fd = dtnapi.dtn_poll_fd(dtn_handle)
        while (self.receive_run):
            # Poll currently sets timeout in ms - this is a bug
            dtnapi.dtn_begin_poll(dtn_handle, 5000)
            # The timeout on select is much longer than the dtn_begin_poll
            # timeout, so there is a problem if there is nothing to read
            rd_fd, wr_fd, err_fd = select([receive_fd], [], [], 10)
            if (len(rd_fd) != 1) or (rd_fd[0] != receive_fd):
                # Cancel the poll anyway
                dtnapi.dtn_cancel_poll(dtn_handle)
                raise DtnError("Report select call timed out")
            
            """
            There should always be something to read
            Put in a timeout just in case
            The call to dtn_recv terminates the poll
            NOTE: On receiving the file, the file name is in the bundle
            payload as a NULL terminated string.  Python leaves the terminating
            byte in place.
            """
            self.logdebug("Getting bundle or time out from dtn_recv")
            bpq_bundle = dtnapi.dtn_recv(dtn_handle, dtnapi.DTN_PAYLOAD_FILE,
                                         recv_timeout)
            # If bpq_bundle is None then either the dtn_recv timed out or
            # there was some other error.
            self.logdebug("Got from dtn_recv %s" % str(bpq_bundle))
            if bpq_bundle != None:
                # Filter out report bundles
                stp = bpq_bundle.dest.find(NETINF_SERVICE)
                service_tag = bpq_bundle.dest[stp:]
                self.logdebug("servicing DTN request for service %s" % service_tag)
                if service_tag.startswith(NETINF_SERVICE_REPORT): 
                    self.logdebug("Received alleged status report bundle")
                    if bpq_bundle.status_report != None:
                        self.logdebug("Received status report")
                        if bpq_bundle.status_report.flags == dtnapi.STATUS_DELIVERED:
                            self.loginfo( "Received delivery report re from %s sent %d seq %d" %
                                          (bpq_bundle.status_report.bundle_id.source,
                                           bpq_bundle.status_report.bundle_id.creation_secs,
                                           bpq_bundle.status_report.bundle_id.creation_seqno))
         
                        elif bpq_bundle.status_report.flags == dtnapi.STATUS_DELETED:
                            self.loginfo("Received deletion report re from %s sent %d seq %d" %
                                         (bpq_bundle.status_report.bundle_id.source,
                                          bpq_bundle.status_report.bundle_id.creation_secs,
                                          bpq_bundle.status_report.bundle_id.creation_seqno))

                    else:
                        self.loginfo("Received unexpected report: Flags: %d" %
                                     bpq_bundle.status_report.flags)
                    continue

                # Check the payload really is in a file
                if not bpq_bundle.payload_file:
                    self.logerror("Received bundle payload not in file - ignoring bundle")
                    continue
                
                fn = bpq_bundle.payload
                l = len(fn)
                if fn[l-1] == "\x00":
                    fn = fn[:-1]
                self.logdebug("Got incoming bundle in file %s" % fn)

                # Does the bundle have a BPQ block
                bpq_data = None
                if bpq_bundle.extension_cnt > 0:
                    for blk in bpq_bundle.extension_blks:
                        if blk.type == QUERY_EXTENSION_BLOCK:
                            bpq_data = BPQ()
                            if not bpq_data.init_from_net(blk.data):
                                self.logwarn("Bad BPQ block received")
                                bpq_data = None
                            break

                # Does the bundle have a Metadata block of type JSON or
                # PAYLOAD_PLACEHOLDER
                json_data = None
                has_payload_placeholder = False
                if bpq_bundle.metadata_cnt > 0:
                    self.logdebug("Metadata count for bundle is %d" %
                                  bpq_bundle.metadata_cnt)
                    for blk in bpq_bundle.metadata_blks:
                        if blk.type == METADATA_BLOCK:
                            md = Metadata()
                            if not md.init_from_net(blk.data):
                                self.loginfo("Bad Metadata block received")
                                break
                            if md.ontology == Metadata.ONTOLOGY_JSON:
                                json_data = md
                            elif md.ontology == Metadata.ONTOLOGY_PAYLOAD_PLACEHOLDER:
                                has_payload_placeholder = True
                                self.logdebug("Have placeholder: %s" %
                                              md.ontology_data)
                            else:
                                self.logwarn("Metadata (type %d) block not processed" %
                                             md.ontology)

                bad_json = False
                if ((json_data is not None) and (json_data != "")):
                    self.logdebug("JSON data: %s" % json_data)
                    od = json_data.ontology_data
                    if od[-1:] == '\x00':
                        od = od[:-1]
                    try:
                        json_dict = json.loads(od)
                    except Exception, e:
                        self.loginfo("Bundle had malformed JSON metadata: %s" %
                                     str(e))
                        bad_json = True
                else:
                    json_dict = {}

                # Check if bundle has a (non-empty) payload
                has_payload = (bpq_bundle.payload_len > 0)

                if (bpq_data is None) or bad_json:
                    self.logdebug("Skipping this bundle as no BPQ block or bad JSON")
                    # Need to free payload file
                    os.remove(fn)
                    continue

                print bpq_data
                # Set up reponse parameters for GET, SEARCH and PUBLISH requests
                # Response to DTN request sent back to DTN source
                make_response = True
                response_destn = bpq_bundle.source
                content = None

                # Determine what sort of a request this is and that BPQ is right
                if service_tag.startswith(NETINF_SERVICE_GET):
                    if ((bpq_data.bpq_kind == BPQ.BPQ_BLOCK_KIND_QUERY) and
                        (bpq_data.matching_rule == BPQ.BPQ_MATCHING_RULE_EXACT)):
                        req_type = HTTPRequest.HTTP_GET
                    else:
                        self.loginfo("Ignoring bundle for GET service with inappropriate BPQ kinds")
                        continue
                    if has_payload:
                        self.loginfo("GET Request had non-empty payload")
                elif service_tag.startswith(NETINF_SERVICE_SEARCH):
                    if ((bpq_data.bpq_kind == BPQ.BPQ_BLOCK_KIND_QUERY) and
                        (bpq_data.matching_rule == BPQ.BPQ_MATCHING_RULE_TOKEN)):
                        req_type = HTTPRequest.HTTP_SEARCH
                    else:
                        self.loginfo("Ignoring bundle for SEARCH service with "
                                     "inappropriate BPQ kinds")
                        continue
                        self.loginfo("SEARCH Request had non-empty payload")
                        continue
                elif service_tag.startswith(NETINF_SERVICE_PUBLISH):
                    if bpq_data.bpq_kind == BPQ.BPQ_BLOCK_KIND_PUBLISH:
                        req_type = HTTPRequest.HTTP_PUBLISH
                    else:
                        self.loginfo("Ignoring bundle for PUBLISH service with "
                                     "inappropriate BPQ kinds")
                        continue
                    if json_dict is None:
                        self.loginfo("Ignoring bundle for PUBLISH service without "
                                     "JSON metadata")                        
                        continue
                    if (has_payload and has_payload_placeholder):
                        self.loginfo("Ignoring bundle for PUBLISH with non-empty "
                                     "payload and placeholder")
                        continue
                    if (has_payload and
                        (json_dict.has_key("fullPut") and not json_dict["fullPut"])):
                        self.loginfo("Ignoring bundle for PUBLISH with non-empty "
                                     "payload and fullPut False")
                        continue
                    if not has_payload_placeholder:
                        content = fn # For not very obvious reasons have lose trailing null
                    else:
                        has_payload = False
                elif service_tag.startswith(NETINF_SERVICE_RESPONSE):
                    if ((bpq_data.bpq_kind == BPQ.BPQ_BLOCK_KIND_RESPONSE) or
                        (bpq_data.bpq_kind ==
                             BPQ.BPQ_BLOCK_KIND_RESPONSE_DO_NOT_CACHE_FRAG)):
                        req_type = HTTPRequest.HTTP_RESPONSE
                        make_response = False
                        response_destn = None
                        # XXX Add code here to give this RESPONSE back to
                        # HTTP server amd skip using http_action
                        self.logdebug("Got response bundle")
                        continue
                    else:
                        self.loginfo("Ignoring bundle for RESPONSE service with inappropriate BPQ kinds")
                        continue
                else:
                    self.loginfo("Ignoring bundle sent to unknown NetInf service: %s" %
                                 bpq_bundle.dest)
                    continue
               
                # Create ni_name if appropriate
                if (req_type in [HTTPRequest.HTTP_GET, HTTPRequest.HTTP_PUBLISH]):
                    ni_name = NIname(bpq_data.bpq_val)
                    
                    # Replace the authority if sent in JSON metadata
                    if ((json_dict is not None) and
                        (json_dict.has_key("http_auth"))):
                        rv = ni_name.set_netloc(json_dict["http_auth"])
                        if rv != ni_errs.niSUCCESS:
                            ni_name = None
                            self.loginfo("Unable to insert netloc %s in ni_name - ignoring bundle"  %
                                         json_dict["http_auth"])
                            continue
                    rv = ni_name.validate_ni_url(has_params = True)
                    if rv != ni_errs.niSUCCESS:
                        ni_name = None
                        self.loginfo("Ignoring bundle with invalid ni URL: %s" %
                                     bpq_data.bpq_val)
                        continue
                else:
                    ni_name = None
                    
                # Send request for HTTP action
                bpq_msg = HTTPRequest(req_type, bpq_bundle, bpq_data, json_dict,
                                      has_payload, ni_name, make_response,
                                      response_destn, content)
                self.http_action.add_new_req(bpq_msg)
                    
            elif dtnapi.dtn_errno(dtn_handle) != dtnapi.DTN_ETIMEOUT:
                raise DtnError("Report: dtn_recv failed with error code %s" %
                               dtnapi.dtn_strerror(dtnapi.dtn_errno(dtn_handle)))
            else:
                self.logdebug("dtn_recv timeout - checking for end run")
                pass
                               
        dtnapi.dtn_close(dtn_handle)
        self.loginfo("dtn_receive exiting")
        return

#==============================================================================#
class DtnSend(Thread):
    """
    @brief Class for sending bundles cointaining BPQ blocks.
    """
    #--------------------------------------------------------------------------#
    # CLASS CONSTANTS

    ##@var NETINF_EXPIRY
    # integer time to expiry for NetInf bundles in seconds (try 1 day).
    NETINF_EXPIRY = (24 *60 * 60)
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var receive_run
    # boolean set False to end the run of the DTN receive thread

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
    def __init__(self, resp_q, logger):
        Thread.__init__(self, name="netinf-dtn-send")

        # Remember Queue with messages to be processed 
        assert(resp_q is not None)
        self.resp_q = resp_q

        # Set up logging functions
        self.logger = logger
        self.loginfo = logger.info
        self.logdebug = logger.debug
        self.logerror = logger.error
        self.logwarn = logger.warn

        # Flag to keep the loop running
        self.send_run = True

    #--------------------------------------------------------------------------#
    def end_run(self):
        self.send_run = False

     #--------------------------------------------------------------------------#
    def run(self):
        """
        @brief This function loops forever (well more or less) waiting for
               notification of requirement to send a response to an incoming
               request or forwarded request
               
        
        This function loops forever (well more or less) waiting for
        queued send requests.  So all the variables can be local.

        The loop is terminated when a special 'end me' message is received.
        """
        
        # Create a connection to the DTN daemon
        dtn_handle = dtnapi.dtn_open()
        if dtn_handle == -1:
            raise DtnError("unable to open connection with daemon")

        # Generate the EIDs
        get_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_GET)
        search_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_SEARCH)
        publish_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_PUBLISH)
        response_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_RESPONSE)
        report_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_REPORT)
        # Yuck! There is no way to trivially get just the local EID
        # Build an EID with an empty service tag and strip off the trailing /
        local_eid = dtnapi.dtn_build_local_eid(dtn_handle, "")[:-1]
        if ((get_eid == None) or (search_eid == None) or (publish_eid == None) or
            (response_eid == None) or (report_eid == None) or
            (local_eid == None)):
            raise DtnError("failure while building response EIDs")

        # Build dictionary mapping request types to source EIDs
        src_dict = { HTTPRequest.HTTP_GET:      get_eid,
                     HTTPRequest.HTTP_SEARCH:   search_eid,
                     HTTPRequest.HTTP_PUBLISH:  publish_eid,
                     HTTPRequest.HTTP_RESPONSE: response_eid }
            
        # Open the database connection
        dbconn = None

        # - We always send the payload as a permanent file unless
        #   there is an empty payload when it is sent as memory
        # Specify a basic bundle spec
        # - The source address is the appropriate one of get_eid, etc
        #   depending on the type of request which we are responding to.
        # - The report address is always the report_eid
        # - The registration id needed in dtn_send is only relevant when
        #   dealing with publish/subscribe case.  We don't use this.
        #   Reports will come back through the receive thread so use no regid
        regid = dtnapi.DTN_REGID_NONE
        # - We want delivery reports (and maybe deletion reports?)
        dopts = dtnapi.DOPTS_DELIVERY_RCPT
        # - Send with normal priority.
        pri = dtnapi.COS_NORMAL
        # NetInf bundles should last a while..
        exp = self.NETINF_EXPIRY

        self.logdebug("Entering DTN send Queue loop")

        # Process responses
        # The thread sits waiting for queued events forever.
        # The thread is terminated by sending a special MSG_END event
        while (self.send_run):
            evt = self.resp_q.get()
            if evt.is_last_msg():
                break

            self.logdebug("Processing message %d for req type %s" %
                          (evt.msg_seqno(), evt.msg_data().req_type))

            # Retrieve the request structure that triggered this response
            req = evt.msg_data()
            assert(isinstance(req, HTTPRequest))

            # Select the source EID
            src_eid = src_dict[req.req_type]

            # Destination is copied from source of request
            destn_eid = req.response_destn
            assert(destn_eid is not None)

            # Report EID is always (our) report_eid

            # Create the BPQ block to send with the response
            # Start with a (shallow) copy of the request BPQ block
            #bpq_data = copy(req.bpq_data)
            bpq_data = BPQ()

            # BPQ kind is PUBLISH if req_type is PUBLISH
            #             RESPONSE if make_response is True or
            #             otherwise QUERY if req_type is GET or SEARCH
            #
            if req.req_type == HTTPRequest.HTTP_PUBLISH:
                bpq_data.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_PUBLISH)
            elif req.make_response:
                bpq_data.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_RESPONSE)
            else:
                bpq_data.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_QUERY)

            # BPQ matching rule is copied except for response
            # to PUBLISH when it is BPQ_MATCHING_RULE_NEVER
            # so that no attempt is made to cache the PUBLISH response
            # (it isn't very interesting and not accessible with an ni name)
            if req.make_response and (req.req_type == HTTPRequest.HTTP_PUBLISH):
                bpq_data.set_matching_rule(BPQ.BPQ_MATCHING_RULE_NEVER)
            else:
                bpq_data.set_matching_rule(req.bpq_data.matching_rule)

            # The creation timestamp and sequence number are generated
            # automatically by the DTN2 API.  One could argue that in the case
            # of a GET response being forwarded from HTTP this is not
            # really the right answer.  However the JSON data has another
            # idea that is propagated so we won't worry here.

            # Likewise with the source EID of the NDO.  The best we can do
            # is the local EID of this node
            bpq_data.set_src_eid(local_eid)

            # The bpq_id and bpq_val fields are just copied from the original
            # request.  This gets you the right msgid and the ni name or
            # token string
            bpq_data.set_bpq_id(req.bpq_data.bpq_id)
            bpq_data.set_bpq_val(req.bpq_data.bpq_val)

            # There will be no fragments to deal with
            # Note that this doesn't damage anything there was in
            # shallow copied original.
            bpq_data.clear_frag_desc()

            self.logdebug("BPQ block to be sent:\n%s" % str(bpq_data))

            # Build an extension blocks structure to hold the block
            ext_blocks =  dtnapi.dtn_extension_block_list(1)

            # Construct the extension block
            bpq_block = dtnapi.dtn_extension_block()
            bpq_block.type = QUERY_EXTENSION_BLOCK
            bpq_block.flags = 0
            bpq_block.data = bpq_data.build_for_net()
            ext_blocks.blocks.append(bpq_block)

            # Build an extension blocks structure to hold the block
            meta_blocks =  dtnapi.dtn_extension_block_list(2)
            
            # Construct the JSON metadata block (if any)
            if req.metadata is not None:
                md = Metadata()
                md.set_ontology(Metadata.ONTOLOGY_JSON)
                md.set_ontology_data(json.dumps(req.metadata.summary("http://example.com")))
                json_block = dtnapi.dtn_extension_block()
                json_block.type = METADATA_BLOCK
                json_block.flags = 0
                json_block.data = md.build_for_net()
                meta_blocks.blocks.append(json_block)

            # Construct a payload placeholder for GET case with no content
            # This distinguishes an empty payload file from the no content case
            if (req.make_response and
                (req.req_type == HTTPRequest.HTTP_GET) and
                (req.content == None)):
                md = Metadata()
                md.set_ontology(Metadata.ONTOLOGY_PAYLOAD_PLACEHOLDER)
                md.set_ontology_data("No content available")
                pp_block = dtnapi.dtn_extension_block()
                pp_block.type = METADATA_BLOCK
                pp_block.flags = 0
                pp_block.data = md.build_for_net()
                meta_blocks.blocks.append(pp_block)

            # If there aren't any metadata blocks make the meta_blocks None
            if len(meta_blocks.blocks) == 0:
                meta_blocks = None

            # Set the payload type
            payload = req.result if req.make_response else req.content
            print "payload: %s" % payload
            if payload is None:
                # Send an empty string via memory
                pt = dtnapi.DTN_PAYLOAD_MEM
                pv = ""
            else:
                # Send a permanent file
                pt = dtnapi.DTN_PAYLOAD_FILE
                pv = payload
                
            self.loginfo("Sending bundle to %s" % destn_eid)

            # Send the bundle
            bundle_id = dtnapi.dtn_send(dtn_handle, regid, src_eid, destn_eid,
                                        report_eid, pri, dopts, exp, pt,
                                        pv, ext_blocks, meta_blocks, "", "")
            if bundle_id == None:
                self.logwarn("Sending of message to %s failed" % destn_eid)
            else:
                # Store the details of the sent bundle
                self.loginfo("%s sent at %d, seq no %d" %(bundle_id.source,
                                                          bundle_id.creation_secs,
                                                          bundle_id.creation_seqno))
        dtnapi.dtn_close(dtn_handle)
        self.loginfo("dtn_send exiting")
        return

#==============================================================================#
# === Test code ===
if (__name__ == "__main__"):
    f = open("/tmp/test_json", "w")
    f.write('{ "a": "b" }')
    f.close()
    class HTTPActionTest:
        def __init__(self):
            return
        def add_new_req(self, in_req):
            print "Received req: %s" % str(in_req)

            if in_req.response_destn.find("netinfproto/service") != -1:
                return

            # This has come in from an app
            print "sending back to app"
            req = HTTPRequest(in_req.req_type, in_req.bundle,
                              in_req.bpq_data, json_in,
                              has_payload=True, ni_name=in_req.ni_name,
                              make_response=True,
                              response_destn=in_req.response_destn,
                              content="/etc/group")
            req.metadata = None
            req.result = "/tmp/test_json"

            evt = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, req)
            print "sending message %s" % str(evt)
            dtn_send_q.put_nowait(evt)
   
            return
        
    logger = logging.getLogger("test2")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    dtn_send_q = Queue.Queue()
    http_action = HTTPActionTest()

    dtn_handle = dtnapi.dtn_open()
    if dtn_handle == -1:
        print "unable to connect to dtnd."
        os._exit(1)
    local_eid = dtnapi.dtn_build_local_eid(dtn_handle,"")[:-1]
    get_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_GET)
    search_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_SEARCH)
    publish_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_PUBLISH)
    response_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_RESPONSE)
    report_eid = dtnapi.dtn_build_local_eid(dtn_handle, NETINF_SERVICE_REPORT)
    
    # Sending thread
    dtn_send_handler = DtnSend(dtn_send_q, logger)
    dtn_send_handler.setDaemon(True)
    dtn_send_handler.start()    

    time.sleep(0.1)
    logger.info("Send handler running: %s" % dtn_send_handler.getName())

    # Build a response message to send
    # Note that we don't actually need the original bundle to do this
    # This is deliberate so that can use this for forwarding.
    # BPQ data structure
    # digest used here is for a snapshot of the /etc/group
    # file that is specified as content later. It is irrelevant
    # for internal testing as the digest is not checked but
    # you might wish to modify it if using this test code to
    # test the nigetalt.py module.
    nis = "ni:///sha-256-32;IEtLRQ"
    bndl = dtnapi.dtn_bundle()
    bpq = BPQ()
    bpq.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_QUERY)
    bpq.set_matching_rule(BPQ.BPQ_MATCHING_RULE_EXACT)
    bpq.set_src_eid(local_eid)
    bpq.set_bpq_id("msgid_zzz")
    bpq.set_bpq_val(nis)
    bpq.clear_frag_desc()
    print "BPQ block:\n%s" % str(bpq)

    json_in = { "http_auth": "rosebud.folly.org.uk:8080" }

    nin = NIname(nis)
    nin.validate_ni_url()

    req = HTTPRequest(HTTPRequest.HTTP_RESPONSE, bndl, bpq, json_in,
                      has_payload=True, ni_name=nin,
                      make_response=True, response_destn=response_eid,
                      content="/etc/group")
    req.metadata = { "d": "e" }

    evt = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, req)
    print "sending message %s" % str(evt)
    dtn_send_q.put_nowait(evt)
   
    # Build a response to a GET request with no content payload
    req = HTTPRequest(HTTPRequest.HTTP_GET, bndl, bpq, json_in,
                      has_payload=False, ni_name=nin,
                      make_response=True, response_destn=response_eid,
                      content=None)

    req.metadata = { "d": "e" }

    evt = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, req)
    print "sending message %s" % str(evt)
    dtn_send_q.put_nowait(evt)

    # Build a GET request
    req = HTTPRequest(HTTPRequest.HTTP_GET, bndl, bpq, json_in,
                      has_payload=False, ni_name=nin,
                      make_response=False, response_destn=get_eid,
                      content=None)

    evt = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, req)
    print "sending message %s" % str(evt)
    dtn_send_q.put_nowait(evt)

    time.sleep(2)
   
    # Receiving thread
    dtn_recv_handler = DtnReceive(http_action, logger)
    dtn_recv_handler.setDaemon(True)
    dtn_recv_handler.start()
    logger.info("Receive handler running: %s" % dtn_recv_handler.getName())

    try:
        while True:
            pass
    except:
        evt = MsgDtnEvt(MsgDtnEvt.MSG_END, None)
        dtn_send_q.put_nowait(evt)
    dtn_recv_handler.end_run()
    time.sleep(1)

    
        
            

    
        
        
    
