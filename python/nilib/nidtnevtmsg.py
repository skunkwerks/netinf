#!/usr/bin/python
"""
@package nilib
@file nidtnevtmsg.py
@brief Class encapsulating messages sent betweenDTN threads and cache manager.
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
Class encapsulating messages sent between DTN threads and cache manager.

@code
Revision History
================
Version   Date	     Author	    Notes
1.0	  01/01/2013 ElwynDavies    Created.

@endcode
"""

#==============================================================================#
# Standard modules

import dtnapi
from types import *

# Nilib modules
from nidtnbpq import BPQ
from nidtnmetadata import Metadata
from ni import NIname

#==============================================================================#
class HTTPRequest:
    """
    @brief Class to hold data sent by a DTN request to be actioned over HTTP CL
    """

    #--------------------------------------------------------------------------#
    # CONSTANT VALUES USED BY CLASS

    # --- Type of HTTP request to execute ---
    ##@var HTTP_GET
    # string indicating that HTTP should send a NetInf GET message
    HTTP_GET = "http_get"
    ##@var HTTP_PUBLISH
    # string indicating that HTTP should send a NetInf PUBLISH message
    HTTP_PUBLISH = "http_publish"
    ##@var HTTP_SEARCH
    # string indicating that HTTP should send a NetInf SEARCH message
    HTTP_SEARCH = "http_search"

    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var req_type
    # string one of HTTP_GET, HTTP_PUBLISH or HTTP_SEARCH
    ##@var bundle
    # dtnapi.dtn_bundle object instance as delivered over DTN
    ##@var msg_seqno
    # integer message sequence number for message this was sent with
    ##@var bpq_data
    # BPQ object instance with decoded BPQ block from _bundle
    ##@var json_in
    # dictionary with JSON data from JSON metadata block in _bundle
    ##@var has_payload
    # boolean True if the request has a non-empty payload rather than 
    #         a metadata block of ontology ONTOLOGY_PAYLOAD_PLACEHOLDER
    #         Equivalent to full-ndo-flag for PUBLISH requests.
    ##@var ni_name
    # NIname object instance for HTTP_GET and HTTP_PUBLISH requests
    #                       extracted from bpq_data.query_val
    ##@var http_host_list
    # list of HTTP netloc strings to be tried for request
    ##@var http_host_next
    # integer index of next host in _http_host_list to be tried
    #         None if all tried and just waiting for responses
    ##@var http_hosts_pending
    # set of integers representing indices of hosts which have been
    #     sent requests for this request instance
    ##@var http_hosts_not_completed
    # set of integers representing indices of hosts which have not yet
    #                 completed the request - initially has an entry
    #                 for every host in http_host_list - when empty
    #                 this request has been serviced as completely
    #                 as possible.
    ##@var metadata
    # NetInfMetaData object instance representing metadata received so far
    ##@var content
    # string filename of content or response file received from HTTP

    #--------------------------------------------------------------------------#
    def __init__(self, req_type, bundle, bpq_data, json_in,
                 has_payload=False, ni_name = None):
        """
        @brief Constructor - saves parameters and initializes others
        @param req_type string one of HTTP_GET, HTTP_PUBLISH or HTTP_SEARCH
        @param bundle dtnapi.dtn_bundle object instance
        @param bpq_data BPQ object instance with decoded BPQ block
        @param json_in dictionary with JSON data from JSON metadata block
        @param has_payload boolean True if the request has a non-empty payload
        @param ni_name NIname object instance
        """
        if not ((req_type == self.HTTP_GET) or
                (req_type == self.HTTP_PUBLISH) or
                (req_type == self.HTTP_SEARCH)):

            raise ValueError("Inappropriate value for req_type %s" % req_type)

        if not isinstance(bundle, dtnapi.dtn_bundle):
            raise ValueError("Inappropriate value for bundle")

        if not isinstance(bpq_data, BPQ):
            raise ValueError("Inappropriate value for bpq_data")

        if type(json_in) != DictType:
            raise ValueError("Inappropriate value for json_in")

        if not ((ni_name is None) or isinstance(ni_name, NIname)):
            raise ValueError("Inappropriate value for ni_name")

        self.req_type = req_type
        self.msg_seqno = None
        self.bundle = bundle
        self.bpq_data = bpq_data
        self.json_in = json_in
        self.has_payload = has_payload
        self.ni_name = ni_name
        self.http_host_list = []
        self.http_host_next = 0
        self.http_hosts_pending = set()
        self.http_hosts_not_completed = None
        self.metadata = None
        self.content = None
        return

    #--------------------------------------------------------------------------#
    def set_msg_seqno(self, msg_seqno):
        """
        @brief record msg_seqno for this request
        @param msg_seqno integer message sequence number of message
                                 this request was sent with
        """
        self.msg_seqno = msg_seqno
        return

    #--------------------------------------------------------------------------#
    def __repr__(self):
        """
        @brief representation of HTTPRequest
        @return string representation
        """
        return "\n".join(("Request type: %s" % self.req_type,
                          "Message seqno: %d" % self.msg_seqno))

#==============================================================================#
class MsgDtnEvt:
    """
    @brief Queue message encapsulation for bundles
    """
    
    #--------------------------------------------------------------------------#
    # CONSTANT VALUES USED BY CLASS

    # --- Direction of message - or terminate receiving process ---
    ##@var MSG_FROM_DTN
    # string signifies message generated by DTN bundle reception
    MSG_FROM_DTN = "dtn_recv"
    ##@var MSG_TO_DTN
    # string signifies message to request a bundle to be sent by DTN
    MSG_TO_DTN = "dtn_send"
    ##@var MSG_END
    # string signifies the receiving thread should shut itself down
    MSG_END = "end_ops"
    
    #--------------------------------------------------------------------------#
    # CLASS VARIABLES
    ##@var _curr_seqno
    # integer unique sequence number for all messages generated

    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var _msg_seqno
    # integer sequence number of this message obtained from next_seqno()
    ##@var _reply_to
    # integer sequence number of message to which this is replying

    #--------------------------------------------------------------------------#
    @classmethod
    def next_seqno(cls):
        """
        @brief Get next sequential message number
        @return integer next sequence number
        """
        try:
            next_seqno = cls._curr_seqno
        except AttributeError:
            cls._curr_seqno = 0
            next_seqno = 0
        cls._curr_seqno += 1
        return next_seqno
    
    #--------------------------------------------------------------------------#
    def __init__(self, send_type, msg_data, reply_to=None):
        """
        @brief Constructor - record parameters and generate sequence number
        @param send_type one of MSG_FROM_DTN, MSG_TO_DTN, MSG_END
        @param msg_data HTTPRequest object instance information for message
        @param reply_to integer sequence number of message
                                to which this is a reply
        """
        if send_type not in (self.MSG_FROM_DTN, self.MSG_TO_DTN, self.MSG_END):
            raise ValueError
        if not ((send_type == self.MSG_END) or
                ((msg_data is not None) and isinstance(msg_data, HTTPRequest))):
            raise ValueError
        self._send_type = send_type
        self._msg_data = msg_data
        self._msg_seqno = self.next_seqno()
        if (send_type != self.MSG_END):
            self._msg_data.set_msg_seqno(self._msg_seqno)
        self._reply_to = reply_to

    #--------------------------------------------------------------------------#
    def is_last_msg(self):
        return self.send_type == MSG_END

    #--------------------------------------------------------------------------#
    def msg_data(self):
        return self._msg_data

    #--------------------------------------------------------------------------#
    def __repr__(self):
        if self._send_type == self.MSG_END:
            return "Msg %d: Ending operations." % self._msg_seqno
        else:
            return "Msg %d: msg_data %s %s queued" % (self._msg_seqno,
                                                      self._msg_data,
                                                      { self.MSG_FROM_DTN: "from DTN",
                                                        self.MSG_TO_DTN: "to DTN"}[self._send_type])
        
#==============================================================================#
if __name__ == "__main__":
    b = dtnapi.dtn_bundle()
    c = BPQ()
    d = {}
    e = HTTPRequest(HTTPRequest.HTTP_GET, b, c, d)
    evt = MsgDtnEvt(MsgDtnEvt.MSG_TO_DTN, e)
    print evt
    evt = MsgDtnEvt(MsgDtnEvt.MSG_FROM_DTN, e)
    print evt
    evt = MsgDtnEvt(MsgDtnEvt.MSG_END, None)
    print evt
