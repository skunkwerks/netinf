#!/usr/bin/python
"""
@package nilib
@file nipub.py
@brief Command line client to perform a NetInf 'publish' operation using http convergence layer.
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
0.4       12/10/2012 Elwyn Davies   Update comments and change main function name. 
0.3       01/10/2012 Elwyn Davies   Moved to using responses format rather than
                                    multipart response. Canonicalized URIs in
                                    metadata.
0.2	  19/09/2012 Elwyn Davies   First cut at adding JSON encoded metadata
0.1	  31/05/2012 Elwyn Davies   Addition of nih scheme
0.0	  12/02/2012 Elwyn Davies   Created for SAIL codesprint.
@endcode
"""
import sys
import os.path
import  random
from optparse import OptionParser
import urllib2
import magic
import json

import mimetools
import email.parser
import email.message
from ni import ni_errs, ni_errs_txt, NIname, NIproc, NIdigester
from encode import *
import streaminghttp

#===============================================================================#
##@var DIGEST_DFLT
# Default digest hashing algorithm's name in ni.py
DIGEST_DFLT = "sha-256"

#===============================================================================#
def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    #print string
    return

#===============================================================================#
def py_nipub():
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
    usage = "%%prog %s\n       %%prog %s\n%s\n       %%prog %s\n       %%prog %s\n%s\n%s" % \
            ("[-q] [-e] [-j|-v|-w|-p] -f <pathname of content file> -d <digest alg> [-l <FQDN - locator>]{1,2}",
             "[-q] [-e] [-j|-v|-w|-p] [-f <pathname of content file>] -n <ni name> [-l <FQDN - locator>]{0,2}",
             "          -- publish file via NI URI over HTTP",
             "[-q] [-e] [-j|-v|-w|-p] -u <HTTP URI of content file> -d <digest alg> [-l <FQDN - locator>]{1,2}",
             "[-q] [-e] [-j|-v|-w|-p] [-u <HTTP URI of content file>] -n <ni name> [-l <FQDN - locator>]{0,2}",
             "          -- publish web content via NI URI over HTTP",
             "Send response as HTML document (-w), plain text (-p), or JSON (-v or -j)\n"
             "Unless -q is specified, the response is sent to standard output.\n"
             "For a JSON response, it can either be output as a 'raw' JSON string (-j) or pretty printed (-v).\n"
             "If none of  -j, -v, -w or -p are specified, a raw JSON response will be requested.")
    parser = OptionParser(usage)
    
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="Pathname for local file to be published.")
    parser.add_option("-u", "--uri", dest="http_name",
                      type="string",
                      help="HTTP URL for content to be published.")
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
                      help="An FQDN where NI might be retrieved. Maybe be "
                           "zero to two if -n is present and has a non-empty netloc. "
                           "Otherwise must be one or two. HTTP is sent to first "
                           "loc if no authority in -n.")
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
    # Either -d or -n must be specified.
    # If -d is specified, there must be either a -f or a -u but not both at once.
    # If -n is specified, one of -f or -u may be specified. No leftover arguments allowed.
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
    if ((options.hash_alg == None) and (options.ni_name == None)):
        parser.error("Must specify either digest algorithm to be used (-d) or complete ni name with algorithm and digest (-n).")
        sys.exit(-1)
    if ((((options.ni_name == None) and (options.file_name == None) and (options.http_name == None))) or
        ((options.file_name != None) and (options.http_name != None))):
        parser.error("Exactly one of -f/--file and -u/--uri must be specified with -d and optionally with -n.")
        sys.exit(-1)
    fc = 0
    for flag in [options.json_raw, options.json_pretty, options.html, options.plain]:
        if flag:
            fc += 1
    if fc > 1:
        parser.error("Should specify at most one response type argument out of -j, -v, -w and -p.")
        sys.exit(-1)

    file_name = None
    
    # **** -u is not implemented yet
    if options.http_name != None:
        target = options.http_name
        print "Web name as source(-u/--uri option) not yet implemented. Exiting"
        sys.exit(-2)

    if options.file_name != None:
        target = options.file_name
        file_name = options.file_name
        full_put = True
    else:
        target = None
        full_put = False
    debug("full_put: %s" %full_put)

    verbose = not options.quiet

    #  If we have a full ni name (-n option) given..
    if options.ni_name is not None:
        # Check the validity of the ni name
        try:
            ni_name = NIname(options.ni_name)
        except Exception, e:
            if verbose:
                print("Error: value of -n/--name option '%s' is not a valid ni name" % options.ni_name)
            sys.exit(-3)
        rv = ni_name.validate_ni_url()
        if rv != ni_errs.niSUCCESS:
            if verbose:
                print("Error: value of -n/--name option '%s' is not a valid ni name" % options.ni_name)
            sys.exit(-3)

        # Extract the scheme and hash algorithm from the name
        scheme = ni_name.get_scheme()
        hash_alg = ni_name.get_alg_name()

        # If the ni name has a netloc in it then that is where to send; if not must have a loc
        nl = ni_name.get_netloc()
        if ((nl == "") and (options.locs == None)):
            print("Error: name (-n/--name) mist have a netloc if no locator options given,")
            sys.exit(-4)
        if nl != "":
            destination = nl
            authority = nl
        else:
            destination = options.locs[0]
            authority = ""
    else:
        # No ni name given.. where to send must be locs[0] and there must be a -d option
        # Default to ni scheme
        destination = options.locs[0]
        authority = ""
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
        ext = ""
            
    # Determine type of response to request
    if options.html:
        rform = "html"
    elif options.plain:
        rform = "plain"
    else:
        rform = "json"
    debug("Response type requested: %s" % rform)

    # Where to send the publish request.
    http_url = "http://%s/netinfproto/publish" % destination
    debug("Accessing: %s" % http_url)

    # Handle full_put = True cases - we have a file with the octets in it
    if full_put:
        # Create NIdigester for use with form encoder and StreamingHTTP
        ni_digester = NIdigester()

        # Install the template URL built from the scheme, the authority and the digest algorithm
        rv = ni_digester.set_url((scheme, authority, "/%s" % hash_alg))
        if rv != ni_errs.niSUCCESS:
            print("Cannot construct valid ni URL: %s" % ni_errs_txt[rv])
            sys.exit(-4)
        debug(ni_digester.get_url())

        # Open the file if possible
        try:
            f = open(options.file_name, "rb")
        except Exception, e :
            debug("Cannot open file %s: Error: %s" %(options.file_name, str(e)))
            parser.error("Unable to open file %s: Error: %s" % (options.file_name, str(e)))
            sys.exit(-5)

        # Guess the mimetype of the file
        m = magic.Magic(mime=True)
        ctype = m.from_file(options.file_name)
        debug("Content-Type: %s" % ctype)
        if ctype is None:
            # Guessing didn't work - default
            ctype = "application/octet-stream"

        # Set up HTTP form data for publish request
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
        
    if (options.locs is not None):
        param_list.append(("loc1", options.locs[0]))
    else:
        param_list.append(("loc1", ""))
    if ((options.locs is not None) and (len(options.locs) == 2)):
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
            print("Error: Unable to create request for http URL %s: %s" %
                  (http_url, str(e)))
        f.close()
        sys.exit(-4)


    # Get HTTP results
    try:
        http_object = urllib2.urlopen(req)
    except Exception, e:
        if verbose:
            print("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        if full_put:
            f.close()
        sys.exit(-4)
    if full_put:
        f.close()
        target = octet_param.get_url()
    else:
        target = ni_name.get_url()
    debug("Sent request: URL: %s" % target)


    # Get message headers
    http_info = http_object.info()
    http_result = http_object.getcode()
    if verbose:
        print("HTTP result: %d" % http_result)
    debug("Response info: %s" % http_info)
    debug("Response type: %s" % http_info.gettype())

    # Read results into buffer
    payload = http_object.read()
    http_object.close()
    debug(payload)

    # Report outcome
    if (http_result != 200):
        if verbose:
            print("Unsuccessful publish request returned HTTP code %d" %
                  http_result) 
        sys.exit(-3)

    # Check content type of returned message matches requested response type
    ct = http_object.headers["content-type"]
    if rform == "plain":
        if ct != "text/plain":
            if verbose:
                print("Error: Expecting plain text (text/plain) response "
                      "but received Content-Type: %s" % ct)
            sys.exit(-4)
    elif rform == "html":
        if ct != "text/html":
            if verbose:
                print("Error: Expecting HTML document (text/html) response "
                      "but received Content-Type: %s" % ct)
            sys.exit(-5)
    else:
        if ct != "application/json":
            if verbose:
                print("Error: Expecting JSON coded (application/json) "
                      "response but received Content-Type: %s" % ct)
            sys.exit(-6)

    # If output of response is expected, print in the requested format
    if verbose:
        print "Publication of %s successful:" % target

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
    py_nipub()
