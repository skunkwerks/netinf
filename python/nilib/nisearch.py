#!/usr/bin/python
"""
@package nilib
@file nisearch.py
@brief Command line client to perform a NetInf 'search' operation using http convergence layer.
@version $Revision: 0.01 $ $Author: elwynd $
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
0.1       12/10/2012 Elwyn Davies   Update comments and change main function name. 
0.0	  21/09/2012 Elwyn Davies   Created.
@endcode
"""
import sys
import os.path
import  random
from optparse import OptionParser
import urllib
import urllib2
import json
#from ni import NIname, NIproc

#===============================================================================#
def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    #print string
    return

#===============================================================================#
def py_nisearch():
    """
    @brief Command line program to perform a NetInf 'get' operation using http
    @brief convergence layer.
    
    Uses NIproc global instance of NI operations class

    Run:
    
    >  nisearch.py --help

    to see usage and options.

    Exit code is 0 for success, 1 if HTTP returned something except 200,
    and negative for local errors.
    """
    
    # Options parsing and verification stuff
    usage = "%prog [-q] [-d] [-w|-j|-p|-v] -l <locator (FQDN) to search>\n" + \
            "<search keywords sent verbatim to server>\n" + \
            "Response format can be HTML document (-w), JSON (-v or -j, the default)\n" + \
            "or plain text (-p)" 
        
    parser = OptionParser(usage)
    
    parser.add_option("-l", "--loc", dest="loc",
                      type="string",
                      help="Locator (FQDN) to which search request is sent.")
    parser.add_option("-q", "--quiet", default=False,
                      action="store_true", dest="quiet",
                      help="Suppress informational message output")
    parser.add_option("-w", "--web", default=False,
                      action="store_true", dest="html",
                      help="Request response as HTML document")
    parser.add_option("-j", "--json", default=False,
                      action="store_true", dest="json",
                      help="Request response as JSON string, compact output")
    parser.add_option("-p", "--plain", default=False,
                      action="store_true", dest="plain",
                      help="Request response as plain text document")
    parser.add_option("-v", "--view", default=False,
                      action="store_true", dest="view",
                      help="Request response as JSON string, pretty printed output.")
    parser.add_option("-d", "--dump", default=False,
                      action="store_true", dest="dump",
                      help="Dump raw HTTP response to stdout.")

    (options, args) = parser.parse_args()

    # Check command line options - -q and -d are optional, <loc> is mandatory
    # Exactly one of response format options (-w, -j, -p and -v) must be specified,
    # There must be at least one keyword.
    verbose = not options.quiet

    if (args is None) or (len(args) == 0):
        if verbose:
            parser.error("No search keywords specified.")
        sys.exit(-1)
        
    # Determine responses format
    rform = None
    fc = 0

    if options.html:
        rform = "html"
        fc += 1
    if options.json:
        rform = "json"
        fc += 1
    if options.plain:
        rform = "plain"
        fc += 1
    if options.view:
        rform = "json"
        fc += 1
    if fc > 1:
        if verbose:
            print("Must specifify exactly one response format from -h, -j, -p and -v")
        sys.exit(-2)

    if rform == None:
        rform = "json"
        
    if options.loc == None:
        if verbose:
            print("Must specify a locator to search (-l/--loc).")
        sys.exit(-3)
        
    # Generate NetInf form access URL
    http_url = "http://%s/netinfproto/search" % options.loc
    
    # Set up HTTP form data for get request
    tokens = " ".join(args)
    debug("rform: %s" % rform)
    debug("keywords: %s" % tokens)
    form_data = urllib.urlencode({ "tokens":   tokens,
                                   "msgid":    random.randint(1, 32000),
                                   "rform":    rform,
                                   "ext":      "" })

    # Send POST request to destination server
    try:
        http_object = urllib2.urlopen(http_url, form_data)
    except Exception, e:
        if verbose:
            print("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        sys.exit(-4)

    # Get HTTP result code
    http_result = http_object.getcode()

    # Get message headers - an instance of email.Message
    http_info = http_object.info()
    if options.dump:
        print("Response type: %s" % http_info.gettype())
        print("Response info:\n%s" % http_info)

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
    if options.dump:
        print("Response payload:\n=================\n")
        print(payload)
        print("=================\n")

    # The results is expected to be a single object with alternative MIME types that can be
    # - application/json with (up to) 10 JSON encoded ni name results
    # - text/html with the results in a HTML document
    # = text/plain with the results as a plain text document

    # Verify length and digest if HTTP result code was 200 - Success
    if (http_result != 200):
        if verbose:
            print("Get request returned HTTP code %d" % http_result)
        sys.exit(1)

    if ((obj_length != None) and (len(payload) != obj_length)):
        if verbose:
            print("Warning: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))
        sys.exit(-5)

    # Check requested and returned types match and output responses in appropriate form
    ct = http_info.getheader("Content-Type").lower()
    if options.html:
        if ct != "text/html":
            if verbose:
                print("HTML document requested but '%s' content returned" % ct)
            sys.exit(-6)
        print payload

    fake_plain = False
    if options.plain:
        if ct == "text/plain":
            print payload
        elif ct == "application/json":
            # Maybe simulate plain when get default JSON?
            fake_plain = True
            pretty = True
        else:
            if verbose:
                print("Plain text document requested but '%s' content returned" % ct)
            sys.exit(-7)

    if rform == "json" or fake_plain:
        if ct != "application/json":
            if verbose:
                print("JSON coding requested but '%s' content returned" % ct)
            sys.exit(-8)
            
        # Extract the JSON structure
        try:
            json_report = json.loads(payload)
        except Exception, e:
            if verbose:
                print("Error: Could not decode JSON response '%s': %s" % (payload,
                                                                          str(e)))
            sys.exit(-9)
        
        if options.view or fake_plain:
            print("Search resultss for keywords '%s':\n" % tokens)
            print json.dumps(json_report, indent = 4)
        else:
            print json.dumps(json_report, separators=(",", ":"))

    sys.exit(0)
                                                                                                    
#===============================================================================#
if __name__ == "__main__":
    py_nisearch()
