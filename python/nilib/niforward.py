#!/usr/bin/env python
"""
@package nilib
@file niforward.py
@brief CL-independent NetInf routing module
@version Copyright (C) 2013 SICS Swedish ICT AB
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

===========================================================================

@code
Revision History
================
Version   Date       Author         Notes
0.1       08/11/2013 Bengt Ahlgren  Implemented default route as a start
@endcode
"""

#==============================================================================#
#=== Standard modules for Python 2.[567].x distributions ===
import os
import stat
import sys
import socket
import threading
#import itertools
import logging
#import shutil
import json
import random
import tempfile
#import re
#import time
#import datetime
#import textwrap
# try:
#     from cStringIO import StringIO
# except ImportError:
#     from StringIO import StringIO

# import cgi
import urllib
import urllib2
# import hashlib
# import xml.etree.ElementTree as ET
# import base64
import email.parser
import email.message

# import magic
# import DNS
# import qrcode

#=== Local package modules ===

from netinf_ver import NETINF_VER, NISERVER_VER
from ni import NIname, NIdigester, NIproc, NI_SCHEME, NIH_SCHEME, ni_errs, ni_errs_txt
from  metadata import NetInfMetaData


DEBUG = True

def dprint(who, string):
    """
    @brief Debug print function
    """
    if DEBUG:
        print "DEBUG({}): {}".format(who, string)
    return


#==============================================================================#
# CONSTANTS

# Enumerate convergence layers (CLs) - used for NextHop.cl_type
NICLHTTP = 1
#NICLDTN = 2
#NICLUDP = 3

# Enumerate router features - used in set NetInfRouterCore.features
NIFWDNAME = 1                   # ni-name-based forwarding
NIFWDLOOKUPHINTS = 2            # perform additional routing hint lookup
NIFWDHINT = 3                   # hint-based forwarding
NIFWDDEFAULT = 4                # default forwarding

#==============================================================================#
# CLASSES

class NextHop:
    """
    @brief Class for one nexthop entry
    """

    def __init__(self, cl_type, nexthop_address):
        self.cl_type = cl_type
        self.cl_address = nexthop_address
        # May want other info here, for example, pointers to methods
        # for queuing a message for output, or a pointer to a CL class
        # that has methods for the CL
        return

class NextHopTable(dict):
    """
    @brief Class for a table with nexthops, mapping an index to a nexthop entry
    """

    # Choosing the dictionary type for now - may not be the best wrt
    # performance?  convert to list?

    def __setitem__(self, index, entry):
        """
        @brief add an entry to the nexthop table
        @param index integer index of the entry to add
        @param entry NextHop next hop entry to add
        @return (none)
        """

        if not isinstance(index, int):
            raise TypeError("'index' needs to be of type 'int'")

        if not isinstance(entry, NextHop):
            raise TypeError("'entry' needs to be of type 'NextHop'")

        if index in self:
            dprint("NextHopTable.__setitem__", "Overwriting index {}".format(index))

        dict.__setitem__(self, index, entry)
        return

# Note: the type of a routing hint is assumed to be an ascii string
# There might be reasons to change to integer for the lookup in the
# forwarding table, but for now it seems simplest to just use the 
# ASCII string from the GET message directly without any conversion

class HintForwardTable(dict):
    """
    @brief Class for a routing hint forwarding table
    """

    def __setitem__(self, hint, nexthop_index):
        """
        @brief add a forwarding entry
        @param hint string the routing hint to add
        @param nexthop_index integer the index of the next hop to use
        @return (none)
        """

        if not isinstance(hint, str):
            raise TypeError("'hint' needs to be of type 'str'")

        if not isinstance(nexthop_index, int):
            raise TypeError("'nexthop_index' needs to be of type 'int'")

        if hint in self:
            dprint("HintForwardTable.__setitem__",
                   "Overwriting entry for hint {}".format(str(hint)))
            
        dict.__setitem__(self, hint, nexthop_index)
        return


class NetInfRouterCore:

    def __init__(self, config, logger, features):
        self.logger = logger
        self.features = features # Set of features

        # Initialise next hop table and default
        # TODO: get info from config instead of letting parent set things up
        self.nh_table = NextHopTable()
        self.nh_default = -1

        return

    # These lookup functions could instead for flexibility be
    # implemented as part of separate classes that are configured as
    # some sort of plug-ins.
    def do_name_forward_lookup(self, message, meta, incoming_handle):
        return []               # XXX

    def do_lookup_hints(self, message, meta, incoming_handle):
        pass                    # XXX

    def do_hint_forward_lookup(self, message, meta, incoming_handle):
        return []               # XXX


    # This method has the main forwarding logic
    def do_forward_nexthop(self, msgid, uri, ext, incoming_handle = None):
        """
        @brief perform forwarding functions to select next hop(s) for the
        @brief message and call CL to forward to the selected next hop(s)
        @param msgid str message id of NetInf message
        @param uri str uri format ni name for NDO
        @param ext str ext field of NetInf message
        @param incoming_handle object XXX - handle to the connection
        @param   receiving the message
        @return bool success status
        @return object the response to the message - to be returned to
        @return   the source of the message
        """

        next_hops = []

        # XXX - all but NIFWDDEFAULT very sketchy...
        if NIFWDNAME in self.features: # if ni-name forwarding
            next_hops = self.do_name_forward_lookup(uri, ext, incoming_handle)

        # XXX - should extract hints from ext, and then add possible new hints
        if (next_hops == []) and (NIFWDLOOKUPHINTS in self.features):
            # can do_lookup_hints just add hints to the meta
            # variable???  or should it add to the message itself (ext
            # parameter)???
            self.do_lookup_hints(uri, ext, incoming_handle)

        if (next_hops == []) and (NIFWDHINT in self.features):
            next_hops = self.do_hint_forward(uri, ext, incoming_handle)

        if (next_hops == []) and (NIFWDDEFAULT in self.features):
            if self.nh_default != -1:
                next_hops = [ self.nh_table[self.nh_default] ]

        if next_hops != []:
            # we have some next hops - call appropriate CL to send
            # outgoing message; need to go through some next hop
            # structure that is initialised by niserver at startup

            status, metadata, filename = do_get_fwd(self.logger, next_hops,
                                                    uri, ext)
            return status, metadata, filename

        else:
            return False, None


#--------------------------------------------------------------------------#
# copied and adapted from nifwd.py. / bengta
#
# the actual forwarding should be independent from how the next hops
# are computed so that different schemes can be accomodated.
#
# TODO (later...):
# - next-hop state to reuse existing next-hop connection
# - composing and sending a message should be extracted to another
#   library function (common to other code), also the router code
#   needs some sort of output queues
#
def do_get_fwd(logger,nexthops,uri,ext):
    """
    @brief fwd a request and wait for a response (with timeout)
    @param nexthops list a list with next hops to try forwarding to
    @param uri str the ni name from the GET message
    @param ext str the ext field from the GET message
    @return 3-tuple (bool - True if successful,
                     NetInfMetaData instance with object metadata
                     str - filename of file with NDO content)
    """

    logger.info("Inside do_fwd");
    metadata=None
    fname=""

    for nexthop in nexthops:
        # send form along
        logger.info("checking via %s" % nexthop.cl_address)

        # Only http CL for now...
        if nexthop.cl_type != NICLHTTP:
            continue

        # Generate NetInf form access URL
        http_url = "http://%s/netinfproto/get" % nexthop.cl_address
        try:
            # Set up HTTP form data for get request
            new_msgid = random.randint(1, 32000) # need new msgid!
            form_data = urllib.urlencode({ "URI":   uri,
                                           "msgid": new_msgid,
                                           "ext":   ext})
        except Exception, e:
            logger.info("do_get_fwd: to %s form encoding exception: %s"
                        % (nexthop.cl_address,str(e)));
            continue
        # Send POST request to destination server
        try:
            # Set up HTTP form data for netinf fwd'd get request
            http_object = urllib2.urlopen(http_url, form_data, 1)
        except Exception, e:
            logger.info("do_fwd: to %s http POST exception: %s" %
                        (nexthop.cl_address,str(e)));
            continue
        # Get HTTP result code
        http_result = http_object.getcode()

        # Get message headers - an instance of email.Message
        http_info = http_object.info()
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

        # The results may be either:
        # - a single application/json MIME item carrying metadata of object
        # - a two part multipart/mixed object with metadats and the content (of whatever type)
        # Parse the MIME object

        # Verify length and digest if HTTP result code was 200 - Success
        if (http_result != 200):
            logger.info("do_fwd: weird http status code %d" % http_result)
            continue

        if ((obj_length != None) and (len(payload) != obj_length)):
            logger.info("do_fwd: weird lengths payload=%d and obj=%d" %
                        (len(payload),obj_length))
            continue

        buf_ct = "Content-Type: %s\r\n\r\n" % http_object.headers["content-type"]
        buf = buf_ct + payload
        msg = email.parser.Parser().parsestr(buf)
        parts = msg.get_payload()
        if msg.is_multipart():
            if len(parts) != 2:
                logger.info("do_fwd: funny number of parts: %d" % len(parts))
                continue
            json_msg = parts[0]
            ct_msg = parts[1]
            try:
                temp_fd,fname=tempfile.mkstemp();
                f = os.fdopen(temp_fd, "w")
                f.write(ct_msg.get_payload())
                f.close()
            except Exception,e:
                logger.info("do_fwd: file crap: %s" % str(e))
                return True,metadata,fname
        else:
            json_msg = msg
            ct_msg = None

        # Extract JSON values from message
        # Check the message is a application/json
        if json_msg.get("Content-type") != "application/json":
            logger.info("do_fwd: weird content type: %s" %
                        json_msg.get("Content-type"))
            continue

        # Extract the JSON structure
        try:
            json_report = json.loads(json_msg.get_payload())
        except Exception, e:
            logger.info("do_fwd: can't decode json: %s" % str(e));
            continue

        curi=NIname(uri)
        curi.validate_ni_url()
        metadata = NetInfMetaData(curi.get_canonical_ni_url())
        logger.info("Metadata I got: %s" % str(json_report))
        metadata.insert_resp_metadata(json_report) # will do json.loads again...

        # removed GET_RES handling present in do_get_fwd in nifwd.py / bengta

        # all good break out of loop
        break

    # make up stuff to return
    # print "do_fwd: success"
    if metadata is None:
        return False, metadata, fname

    return True,metadata,fname

#----------------------------------------------------------------------
#
# main program for testing

if __name__ == "__main__":
    print len(sys.argv)
    if len(sys.argv) > 1:
        print int(sys.argv[1])

    # well, doesn't do anything...
