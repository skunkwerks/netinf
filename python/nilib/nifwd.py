#!/usr/bin/python
"""
@package nilib
@file nifwd.py
@brief Command line client to perform a NetInf 'get' operation using http convergence layer.
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

@code
Revision History
================
Version   Date       Author         Notes
0.0	  12/14/2012 Stephen Farrell   Created to start forwarding

@endcode
"""
import sys
import os.path
import  random
import urllib
import urllib2
import json
import email.parser
import email.message

from ni import ni_errs, ni_errs_txt, NIname, NIproc

#===============================================================================#
# moral equivalent of #define

FWDSUCCESS = 0
FWDERROR = 1
FWDTIMEOUT = 2

#===============================================================================#

"""
    Overall forwarding scheme

    We might forward anything, GET, PUBLISH or SEARCH

    If we already "know the answer" locally, we do not
    forward, but "know the answer" is different for 
    different messages.

    For all messages:
        - for GET/SEARCH if I have an entry locally, then answer
        - for PUBLISH if I decide I'm a DEST then I make entry and answer
        - for SEARCH if I decide I'm a DEST then I run search as now and answer

        - if not, check if I know where to forward
            - if I don't know where to forward, 404
        - add "being resolved" entry to cache 
        - forward request with timeout (def: 1s?)
        - when get answer:
            - if 4xx, delete "being resolved" entry and 4xx
            - if 2xx, update cache entry and return 2xx
                - "live" check NDI first? (config)
                    - if do check NDI and fail, then 4xx
                    - record that fact in cache
                - if not, run occasional NDI checks on cache as
                    part of cache eviction (TBD) 
        - if 2nd req for same thing arrives whilst 
          resolving then hold req and give same answer
            - only answer if NDI checked (config)

    GET specific:
        - just to note intermediate notes won't now 
            try fetch NDO octets

    PUBLISH specific:
        - do I cache if full ndo if I'm not DEST?
            - yes, cache everything to start with

    SEARCH specific:
        - don't try pre-fetch NDOs that match?

"""

class forwarder: 

    def __init__(self,logger):
        self.logger = logger
        self.loginfo = self.logger.info
        return

    #===============================================================================#
    """
        check if I know where to forward a request (GET, PUBLISH or SEARCH)
        - might use an NRS
    """
    def check_fwd(self,niname):
        self.loginfo("Inside check_fwd");
        nexthops=None
        return False,nexthops
    
    #===============================================================================#
    """
        fwd a request and wait for a response (with timeout)
    """
    def do_fwd(self,handler,nexthops):
        self.loginfo("Inside do_fwd");
        return FWDERROR


