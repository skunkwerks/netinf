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
from ni import ni_errs, ni_errs_txt, NIname, NIproc

def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    #print string
    return

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
    usage = "%prog [-q] [-l] [-d] [-m|-v] [-f <pathname of content file>] <ni name>\n" + \
            "<ni name> must include location (netloc) from which to retrieve object."
    parser = OptionParser(usage)
    
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="File to hold retrieved content. Defaults to hash code in current directory if not present")
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
    parser.add_option("-d", "--dump", default=False,
                      action="store_true", dest="dump",
                      help="Dump raw HTTP response to stdout.")

    (options, args) = parser.parse_args()

    # Check command line options - -q, -f, -l, -m, -v and -d are optional, <ni name> is mandatory
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
    http_url = "http://%s/netinfproto/get" % ni_url.get_netloc()
    """
    if (http_url == None):
        if verbose:
            print("Error: Unable to generate http: transformed URL for ni URL %s" % ni_urlparse.get_url())
        sys.exit(-3)
    """
    
    # Set up HTTP form data for get request
    form_data = urllib.urlencode({ "URI":   ni_url.get_url(),
                                   "msgid": random.randint(1, 32000),
                                   "ext":   "" })

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

    # The results may be either:
    # - a single application/json MIME item carrying metadata of object
    # - a two part multipart/mixed object with metadats and the content (of whatever type)
    # Parse the MIME object

    # Verify length and digest if HTTP result code was 200 - Success
    if (http_result != 200):
        if verbose:
            print("Get request returned HTTP code %d" % http_result)
        sys.exit(1)

    if ((obj_length != None) and (len(payload) != obj_length)):
        if verbose:
            print("Warning: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))
        sys.exit(-5)
        
    buf_ct = "Content-Type: %s\r\n\r\n" % http_object.headers["content-type"]
    buf = buf_ct + payload
    msg = email.parser.Parser().parsestr(buf)
    debug( msg.__dict__)
    parts = msg.get_payload()
    debug("Multipart: %s" % str(msg.is_multipart()))
    if msg.is_multipart():
        debug("Number of parts: %d" % len(parts))
        if len(parts) != 2:
            if verbose:
                print("Error: Response from server does not have two parts.")
            sys.exit(-6)
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
        print("First or only component (metadata) of result is not of type application/json")
        sys.exit(-7)

    # Extract the JSON structure
    try:
        json_report = json.loads(json_msg.get_payload())
    except Exception, e:
        if verbose:
            print("Error: Could not decode JSON report '%s': %s" % (json_msg.get_payload(),
                                                                    str(e)))
        sys.exit(-8)
    
    if options.view:
        print("Returned metadata for %s:" % args[0])
        print json.dumps(json_report, indent = 4)

    if options.metadata:
        print json.dumps(json_report, separators=(",", ":"))

    # If the content was also returned..
    if ct_msg != None:
        debug( ct_msg.__dict__)
        # Check the digest
        rv = NIproc.checknib(ni_url, ct_msg.get_payload())
        if (rv != ni_errs.niSUCCESS):
            verified = False
            if verbose:
                print("Error: digest of received data does not match digest in URL %s: %s" %
                      (ni_url.get_url(), ni_errs_txt[rv]))
            if not options.lax:
                sys.exit(-9)
        else:
            verified = True

        # Write to file
        try:
            f = open(options.file_name, "wb")
        except Exception, e:
            if verbose:
                print("Error: Unable to open destination file %s: %s" %
                      (os.path.abspath(options.file_name), str(e)))
            sys.exit(-11)

        try:
            f.write(ct_msg.get_payload())
        except:
            if verbose:
                print("Error: Unable to write data to destination file %s: %s" %
                      (os.path.abspath(options.file_name), str(e)))
            sys.exit(-12)

        f.close()
        
        if (http_result == 200):
            if verified:
                if verbose:
                    print("Success: file %s written with verified contents "
                          "(length %d) resulting from 'get' from URL %s" %
                          (os.path.abspath(options.file_name),
                           len(ct_msg.get_payload()),
                           ni_url.get_url()))
                rv = 0
            else:
                if verbose:
                    print("File %s written length %d) resulting from 'get' "
                          "from URL %s but content does not match digest" %
                          (os.path.abspath(options.file_name),
                           len(ct_msg.get_payload()),
                           ni_url.get_url()))
                # Return same value as if hadn't allowed storage with lax option
                rv = -9
        else:
            print("Why did we get here?")
            rv = -13
    else:
        # Succeesful metadata only get
        if verbose:
            print("Success: Metadata only returned for URL %s" % ni_url.get_url())
        rv = 0

    sys.exit(rv)
                                                                                                    
if __name__ == "__main__":
    main()
