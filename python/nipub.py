#!/usr/bin/python
"""
@package ni
@file nipub.py
@brief Command line client to perform a NetInf 'publish' operation using http convergence layer.
@version $Revision: 0.01 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
      This is an adjunct to the NI URI library developed as
      part of the SAIL project. (http://sail-project.eu)

      Specification(s) - note, versions may change
          http://tools.ietf.org/html/farrell-decade-ni-00
          http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
       http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import sys
import os.path
import  random
from optparse import OptionParser
import urllib2
import mimetypes

import mimetools
from ni import *
from encode import *
import streaminghttp

def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    print string
    return

def main():
    """
    @brief Command line program to perform a NetInf 'publish' operation using http
    @brief convergence layer.
    
    Uses NIproc global instance of NI operations class

    Run:
    
    >  nipub.py --help

    to see usage and options.

    Exit code is 0 for success, 1 if HTTP returned something except 200,
    and negative for local errors.
    """
    
    # Options parsing and verification stuff
    usage = "%%prog %s\n%s\n       %%prog %s\n%s" %("[-q] -f <pathname of content file> [-a <authority>] [-d <digest alg>] [-l <FQDN - locator>]+",
                                                    "          -- publish file via NI URI over HTTP",
                                                    "[-q] -w <HTTP URI of content file> [-a <authority>] [-d <digest alg>] [-l <FQDN - locator>]+",
                                                    "          -- publish web content via NI URI over HTTP")
    parser = OptionParser(usage)
    
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="Pathname for local file to be published.")
    parser.add_option("-w", "--web", dest="http_name",
                      type="string",
                      help="HTTP URL for content to be published.")
    parser.add_option("-a", "--authority", dest="authority",
                      type="string",
                      help="FQDN to be placed in authority component of NI name published.")
    parser.add_option("-l", "--loc", dest="locs", action="append",
                      type="string",
                      help="An FQDN where NI might be retrieved. One is required (and is where object is published to) but may be several.")
    parser.add_option("-d", "--digest", dest="hash_alg", default="sha-256",
                      type="string",
                      help="Digest algorithm to be used to hash content and create NI URI. Defaults to sha-256.")
    parser.add_option("-q", "--quiet", default=False,
                      action="store_true", dest="quiet",
                      help="Suppress textual output")

    (options, args) = parser.parse_args()

    # Check command line options - -a and -q are optional, must be at least one -l ,
    # must be either a -f or a -w but not both at once.  No leftover arguments allowed.
    if len(args) != 0:
        parser.error("Unrecognized arguments %s supplied." % str(args))
        sys.exit(-1)
    if (options.locs == None):
        parser.error("Must supply at least one locator (-l/--loc) argument")
        sys.exit(-1)
    if (len(options.locs) > 2):
        parser.error("Initial version only supports two locators (-l/--loc).")
        sys.exit(-1)
    if (((options.file_name == None) and (options.http_name == None)) or
        ((options.file_name != None) and (options.http_name != None))):
        parser.error("Exactly one of -f/--file and -w/--web must be specified")

    verbose = not options.quiet

    if (options.authority == None):
        authority = ""
    else:
        authority = options.authority
    
    # Create NIdigester for use with form encoder and StreamingHTTP
    ni_digester = NIdigester()

    # Install the template URL built from the authority and the digest algorithm
    rv = ni_digester.set_url((authority, options.hash_alg))
    if rv != ni_errs.niSUCCESS:
        print("Cannot construct valid ni URL: %s" % ni_err_txt[rv])
        sys.exit(-1)
    debug(ni_digester.get_url())

    # Where to send the publish request.
    http_url = "http://%s/.well-known/netinfproto/publish" % options.locs[0]
    debug("Accessing: %s" % http_url)

    # Open the file if possible
    try:
        f = open(options.file_name, "rb")
    except Exception, e :
        debug("Cannot open file %s: Error: %s" %(options.file_name, str(e)))
        parser.error("Unable to open file %s: Error: %s" % (options.file_name, str(e)))
        sys.exit(-1)

    # Guess the mimetype of the file
    ctype, encoding = mimetypes.guess_type(options.file_name)
    if ctype is None:
        # Guessing didn't work - default
        ctype = "application/octet-stream"

    # Set up HTTP form data for get request
    # Make parameter for file with digester
    octet_param = MultipartParam("octets",
                                 fileobj=f,
                                 filetype=ctype,
                                 filename=options.file_name,
                                 digester = ni_digester)
    # Make dictionary that will dynamically retrieve ni URI when it has been made
    uri_dict = { "generator": octet_param.get_url,
                 "length": (len(ni_digester.get_url()) + len(";") +
                            ni_digester.get_b64_encoded_length())}

    param_list = [octet_param,
                  ("URI",       uri_dict),
                  ("msgid",     str(random.randint(1, 32000))),
                  ("ext",       "ignored"),
                  ("fullPut",   "yes"),
                  ("loc1",      options.locs[0])]
    if (len(options.locs) == 2):
        param_list.append(("loc2", options.locs[1]))
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
        if verbose:
            print("Error: Unable to create request for http URL %s: %s" % (http_url, str(e)))
        f.close()
        sys.exit(-4)


    # Get HTTP results
    try:
        http_object = urllib2.urlopen(req)
    except Exception, e:
        if verbose:
            print("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        f.close()
        sys.exit(-4)
    f.close()
    debug("Sent request: URL: %s" % octet_param.get_url())


    # Get message headers - an instance of mimetools.Message
    http_info = http_object.info()
    http_result = http_object.getcode()
    if verbose:
        print("HTTP result: %d" % http_result)
    debug("Response info: %s" % http_info)
    debug("Response type: %s" % http_info.gettype())

    # Read results into buffer
    buf = http_object.read()
    http_object.close()
    if verbose:
        print "Read: %s" % buf

    # Report outcome
    if (http_result != 200):
        if verbose:
            print("Publish request returned HTTP code %d" % http_result) 
        sys.exit(-3)
    if verbose:
        print("Object published as %s" % octet_param.get_url())
    sys.exit(0)
if __name__ == "__main__":
    main()
