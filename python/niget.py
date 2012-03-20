#!/usr/bin/python
"""
@package niget
@file niget.py
@brief Command line client to perform a NetInf 'get' operation using http convergence layer.
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
import urllib
import urllib2
import mimetools
from ni import *

def main():
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
    usage = "%prog [-q] [-f <pathname of content file>] <ni name>"
    parser = OptionParser(usage)
    
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="File to hold retrieved content. Defaults to hash code in current directory if not present")
    parser.add_option("-q", "--quiet", default=False,
                      action="store_true", dest="quiet",
                      help="Suppress textual output")

    (options, args) = parser.parse_args()

    # Check command line options - -q and -f are optional, <ni name> is mandatory
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
        
    # Generate NetInf form access URL
    http_url = "http://%s/.well-known/netinfproto/get" % ni_url.get_netloc()
    """
    if (http_url == None):
        if verbose:
            print("Error: Unable to generate http: transformed URL for ni URL %s" % ni_urlparse.get_url())
        sys.exit(-3)
    """
    
    # Set up HTTP form data for get request
    form_data = urllib.urlencode({ "URI":   ni_url.get_url(),
                                   "msgid": random.randint(1, 32000),
                                   "ext":   "ignored" })

    # Send POST request to destination server
    try:
        http_object = urllib2.urlopen(http_url, form_data)
    except Exception, e:
        if verbose:
            print("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        sys.exit(-4)

    # Get HTTP result code
    http_result = http_object.getcode()

    # Get message headers - an instance of mimetools.Message
    http_info = http_object.info()
    print http_info
    #print http_info.gettype()
    obj_length_str = http_info.getheader("Content-Length")
    if (obj_length_str != None):
        obj_length = int(obj_length_str)
    else:
        obj_length = None

    # Read results into buffer
    buf = http_object.read()
    http_object.close()
    #print buf

    # Verify length and digest if HTTP result code was 200 - Success
    if (http_result != 200):
        if verbose:
            print("Warning: Request returned HTTP code %d - as code is not 200, digest check omitted" % http_result) 
    else:
        if ((obj_length != None) and (len(buf) != obj_length)):
            if verbose:
                print("Warning: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))
        rv = NIproc.checknib(ni_url, buf)
        if (rv != ni_errs.niSUCCESS):
            if verbose:
                print("Error: digest of received data does not match digest in URL %s: %s" % (ni_url.get_url(), ni_errs_txt[rv]))
            sys.exit(-5)

    # Write to file
    try:
        f = open(options.file_name, "wb")
    except Exception, e:
        if verbose:
            print("Error: Unable to open destination file %s: %s" % (os.path.abspath(options.file_name), str(e)))
        sys.exit(-6)

    try:
        f.write(buf)
    except:
        if verbose:
            print("Error: Unable to write data to destination file %s: %s" % (os.path.abspath(options.file_name), str(e)))
        sys.exit(-7)

    f.close()
    if (http_result == 200):
        if verbose:
            print("Success: file %s written with verified contents (length %d) resulting from 'get' from URL %s" % (os.path.abspath(options.file_name),
                                                                                                                    len(buf),
                                                                                                                    ni_url.get_url()))
        sys.exit(0)
    else:
        if verbose:
            print("Check file %s written with message resulting from 'get' from URL %s with HTTP result %d" % (os.path.abspath(options.file_name),
                                                                                                               ni_url.get_url(),
                                                                                                               http_result))
        sys.exit(1)
                                                                                                    
if __name__ == "__main__":
    main()
