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
import threading
import logging
import Queue
import time
import json
import socket
from select import select

import pprint

import dtnapi
from dtn_api_const import *

# Nilib modules
from ni import NIname, ni_errs
from nidtnbpq import BPQ
from nidtnmetadata import Metadata
from nidtnevtmsg import MsgDtnEvt, HTTPRequest


# Exception resulting from DTN problems
class DtnError(Exception):
    def __init__(self, reason):
        self.reason = reason
    def __str__(self):
        return "Error communication with DTN daemon: %s" % (repr(self.reason),)

#==============================================================================#

class DtnReceive(threading.Thread):
    """
    @brief Class for handling incoming DTN bundles that contain BPQ blocks

    Registers to receive bundles sent to dtn://<local eid>/netinf_service

    Dismantle bundle...
    - Check has BPQ block
    - If so convert to structure; if not ignore bundle
    - Examine BPQ bundle type
    - case type:
      + QUERY
        o is either GET or SEARCH
        o if match_rule is EXACT_MATCH assume GET
          = if ni name in local HTTP cache build GET_RESP with local stuff
          = Otherwise save msgid and other data in Redis awaiting HTTP response
          = and attempt to forward -  get metadata if any and build
            structure to put in queue
        o if match_rule is TOKEN_MATCH assume SEARCH
          = Save msgid and other data in Redis awaiting HTTP response
          = forward search request (might be done locally also?)
      + RESPONSE
        o check if msgid is in Redis awaiting DTN response list
        o if so send back to HTTP loop
    """

    NETINF_SERVICE = "netinf_service"

    #--------------------------------------------------------------------------#
    def __init__(self, recv_q, logger):
        threading.Thread.__init__(self, name="netinf-dtn-receive")

        # Remember Queue for sending incoming bundle info
        self.recv_q = recv_q

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
               incoming bundles containing BPQ blocks
               
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
                                                      self.NETINF_SERVICE)
        self.logdebug("Service EID: %s" %self.service_eid)

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
            bpq_bundle = dtnapi.dtn_recv(dtn_handle, dtnapi.DTN_PAYLOAD_FILE, 1)
            if bpq_bundle != None:
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
                                self.loginfo("Bad BPQ block received")
                                bpq_data = None
                            break

                # Does the bundle have a Metadata block of type JSON
                json_data = None
                if bpq_bundle.metadata_cnt > 0:
                    for blk in bpq_bundle.metadata_blks:
                        if blk.type == METADATA_BLOCK:
                            json_data = Metadata()
                            if not json_data.init_from_net(blk.data):
                                self.loginfo("Bad Metadata block received")
                                json_data = None
                            if not json_data.ontology == Metadata.ONTOLOGY_JSON:
                                self.loginfo("Metadata (type %d) is not type JSON" %
                                             json_data.ontology)
                                json_data = None
                            break

                    
                if bpq_data is None:
                    self.logdebug("Skipping this bundle")
                    # Need to free payload if any
                    continue

                print bpq_data
                print json_data
                od = json_data.ontology_data
                if od[-1:] == '\x00':
                    od = od[:-1]
                json_dict = json.loads(od)

                # Determine what sort of a request this is
                if bpq_data.bpq_kind == BPQ.BPQ_BLOCK_KIND_QUERY:
                    if bpq_data.matching_rule == BPQ.BPQ_MATCHING_RULE_EXACT:
                        req_type = HTTPRequest.HTTP_GET
                    else:
                        req_type = HTTPRequest.HTTP_SEARCH
                elif bpq_data.bpq_kind = BPQ.BPQ_BLOCK_KIND_PUBLISH:
                    req_type = HTTPRequest.HTTP_PUBLISH
                else:
                    req_type = HTTPRequest.HTTP_RESPONSE

                # Create ni_name if appropriate
                ni_name = NIname(bpq_data.bpq_val)
                rv = ni_name.validate_ni_url(has_params = True)
                if rv != ni_errs.niSUCCESS:
                    ni_name = None

                dtnapi.dtn_bundle.
                

                
                
                bpq_msg = HTTPRequest(req_type, bpq_bundle, bpq_data, json_dict)
                                      

                if self.recv_q != None:                             
                    # Put message on the queue to send it on to cache manager
                    evt = MsgDtnEvt(MsgDtnEvt.MSG_FROM_DTN, bpq_msg)
                    self.recv_q.put_nowait(evt)
                    
            elif dtnapi.dtn_errno(dtn_handle) != dtnapi.DTN_ETIMEOUT:
                raise DtnError("Report: dtn_recv failed with error code %d" %
                               dtnapi.dtn_errno(dtn_handle))
            else:
                pass
                               
        dtnapi.dtn_close(dtn_handle)
        self.loginfo("dtn_receive exiting")
#==============================================================================#

def test_send(logger):
    
    # This function loops forever (well more or less) waiting for
    # queued send requests.  So all the variables can be local.
    # Create a connection to the DTN daemon
    dtn_handle = dtnapi.dtn_open()
    if dtn_handle == -1:
        raise DtnError("unable to open connection with daemon")

    # Specify a basic bundle spec
    # - We always send the payload as a string
    pt = dtnapi.DTN_PAYLOAD_MEM
    # - The source address is always the email_addr
    # - The report address is always the report_addr
    # - The registration id needed in dtn_send is the place
    #   where reports come back to.. we always want reports
    #   but it is unclear why we need to subscribe to the 'session'
    #   just to do the send.The reports will come back through
    #   another connection. Lets try with no regid
    regid = dtnapi.DTN_REGID_NONE
    # - The destination address has to be synthesized (later)
    # - We want delivery reports (and maybe deletion reports?)
    dopts = dtnapi.DOPTS_DELIVERY_RCPT
    # - Send with normal priority.
    pri = dtnapi.COS_NORMAL
    # Bundles should last a while..
    exp = (5 * 60)

    # Build the destination EID
    destn = "dtn://mightyatom.dtn/recv_test"
    src = "dtn://mightyatom.dtn/send_test"

    e1 = dtnapi.dtn_extension_block()
    e1.type = 9
    e1.flags = 0
    e1.data = "abcde"
    f = dtnapi.dtn_extension_block_list(1)
    f.blocks.append(e1)
    e2 = dtnapi.dtn_extension_block()
    e2.type = 8
    e2.flags = 0
    e2.data = "\x01metadata1"
    g = dtnapi.dtn_extension_block_list(2)
    g.blocks.append(e2)
    e3 = dtnapi.dtn_extension_block()
    e3.type = 8
    e3.flags = 0
    e3.data = "\x01metadata2"
    g.blocks.append(e3)
    
    
    # Send the bundle
    bundle_id = dtnapi.dtn_send(dtn_handle, regid, src, destn, src,
                                pri, dopts, exp, pt,
                                "payload", f, g, "", "")
    if bundle_id == None:
        logger.error("Sending of message to %s failed" % destn)
    else:
        logger.info("Bundle sent OK")
    dtnapi.dtn_close(dtn_handle)
    logger.info("dtn_send exiting")
    return
        
#==============================================================================#
# === Test code ===
if (__name__ == "__main__"):
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # test_send(logger)
    
    #dtn_send_q = Queue.Queue()
    dtn_recv_q = Queue.Queue()

    """
    # Sending thread
    dtn_send_handler = dtn_send(nomadic_domain, dtn_send_q, logger)
    dtn_send_handler.setDaemon(True)
    dtn_send_handler.start()
    """

    # Receiving thread
    dtn_recv_handler = DtnReceive(dtn_recv_q, logger)
    dtn_recv_handler.setDaemon(True)
    dtn_recv_handler.start()

    """
    # Report handler thread
    dtn_report_handler = dtn_report(nomadic_domain, logger)
    dtn_report_handler.setDaemon(True)
    dtn_report_handler.start()
    """

    time.sleep(0.1)
    #logger.info("Send handler running: %s" % dtn_send_handler.getName())
    logger.info("Receive handler running: %s" % dtn_recv_handler.getName())
    #logger.info("Report handler running: %s" % dtn_report_handler.getName())
    """
    evt = msg_send_evt(MSG_DTN,
                       "/etc/group",
                       MSG_NEW,
                       ["elwynd@nomadic.n4c.eu"])
    dtn_send_q.put_nowait(evt)
    """
    
    logger.info("Waiting for incoming bundles")
    evt = dtn_recv_q.get()
    logger.info("Bundle received: %s" % evt.msg_data())
    print evt.msg_data().json_in
    b = evt.msg_data().bundle
    print b.metadata_cnt
    if b.metadata_cnt > 0:
        print b.metadata_blks[0].type
        print b.metadata_blks[0].flags
        print b.metadata_blks[0].data
    time.sleep(5)

    """
    try:
        while True:
            pass
    except:
        evt = msg_send_evt(MSG_END,
                           "",
                           MSG_NEW,
                           "")
        dtn_send_q.put_nowait(evt)
        """
    dtn_recv_handler.end_run()
    #dtn_report_handler.end_run()
    time.sleep(1)

    
        
            

    
        
        
    
