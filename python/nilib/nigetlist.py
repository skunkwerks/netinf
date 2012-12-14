#!/usr/bin/python
"""
@package nilib
@file nigetlist.py
@brief Command line client to perform a NetInf 'get' operation on a list of files.
@version $Revision: 0.05 $ $Author: elwynd $
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

@details
To send 'get' requests to a server to retrieve a whole list of files.


@code
Revision History
================
Version   Date       Author         Notes
1.0	  14/01/2012 Elwyn Davies   Created using niget.py as template.
                                    Incorporate use of feedparser to
@endcode
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
import time
import platform
import multiprocessing
import tempfile
from ni import ni_errs, ni_errs_txt, NIname, NIproc, make_b64_urldigest
from nifeedparser import DigestFile, FeedParser

#============================================================================#
verbose = False

def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    if verbose:
        print string
    return

#===============================================================================#
logger=logging.getLogger('nilog')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def nilog(string):
	"""
	@brief Log the node, time, and the string
	@param string to be printed (in)
	"""
	node=platform.node()
	now=time.time() 
	nano= "%.10f" %now
	utct = time.strftime("%Y-%m-%dT%H:%M:%S")
	
	logger.info('NILOG: ' + node + ',' + nano + ',' + utct + ',' + string)
	
	return

#===============================================================================#
digested_file = None
digested_fileobj = None
hash_fn = None
digester_instance = None

def file_dest_setter(content_type):
    global digester_instance
    print "ct: %s" % content_type
    if ((content_type is None) or
        (content_type.lower().startswith("application/json"))):
        return None
    else:
        digester_instance = DigestFile(digested_file, digested_fileobj, hash_fn)
        return digester_instance

#===============================================================================#
def getone(alg_digest, host, dest):
    """
    @brief Perform a NetInf 'get' from the host for the ni name made with alg and
    @brief digest provided by alg_digest.  If dest is not None leave the output
    @brief in specified path.
    @param alg_digest string combination of digest alogorithm and digest separated by ;
    @param host string FQDN or IP address of host to send get message to
    @param dest None or string where to put destination contents if received

    Assume that dest provides a directory path into which file can be written
    """

    # Record start time
    stime= time.time()
    
    # Create NIname instance for supplied URL and validate it
    url_str = "ni://%s/%s" % (host,alg_digest)
    ni_url = NIname(url_str)
    ni_url_str = ni_url.get_canonical_ni_url()

    # Must be a complete ni: URL with non-empty params field
    rv = ni_url.validate_ni_url(has_params = True)
    if (rv != ni_errs.niSUCCESS):
        nilog("Error: %s is not a complete, valid ni scheme URL: %s" % (ni_url_str, ni_errs_txt[rv]))
        return

    # Generate NetInf form access URL
    http_url = "http://%s/netinfproto/get" % ni_url.get_netloc()
    
    # Set up HTTP form data for get request
    form_data = urllib.urlencode({ "URI":   ni_url.get_url(),
                                   "msgid": random.randint(1, 32000),
                                   "ext":   "" })

    # Send POST request to destination server
    try:
        http_object = urllib2.urlopen(http_url, form_data)
    except Exception, e:
        nilog("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
        return

    # Get HTTP result code
    http_result = http_object.getcode()

    # Get message headers - an instance of email.Message
    http_info = http_object.info()
    if options.dump:
        debug("Response type: %s" % http_info.gettype())
        debug("Response info:\n%s" % http_info)

    if (http_result != 200):
        nilog("Get request returned HTTP code %d" % http_result)
        return

    obj_length_str = http_info.getheader("Content-Length")
    if (obj_length_str != None):
        obj_length = int(obj_length_str)
    else:
        obj_length = None

    # The results may be either:
    # - a single application/json MIME item carrying metadata of object
    # - a two part multipart/mixed object with metadats and the content (of whatever type)
    # Parse the MIME object

    primer = "Content-Type: %s\r\n\r\n" % http_object.headers["content-type"]
    global digested_file, digested_fileobj, hash_fn
    if dest is None:
        digested_fileobj, digested_file = tempfile.mkstemp()
    else:
        digested_file = dest

    msg_parser = FeedParser(_filer=file_dest_setter)
    msg_parser.feed(primer)
    payload_lengh = 0
    blk_size = 4096
    while True:
        buf = http_object.read(blk_size)
        if len(buf) == 0:
            break
        msg_parser.feed(buf)
        payload_len += len(buf)
    
    msg = msg_parser.close()
    http_object.close()

    if len(msg.defects) > 0:
        nilog("Response was not a correctly formed MIME object")
        return
    # Verify length 
    if ((obj_length != None) and (payload_len != obj_length)):
        nilog("Warning: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))
        return
        
    debug( msg.__dict__)
    # If the msg is multipart this is a list of the sub messages
    parts = msg.get_payload()
    debug("Multipart: %s" % str(msg.is_multipart()))
    if msg.is_multipart():
        debug("Number of parts: %d" % len(parts))
        if len(parts) != 2:
            nilog("Error: Response from server does not have two parts.")
            return
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
        nilog("First or only component (metadata) of result is not of type application/json")
        return

    # Extract the JSON structure
    try:
        json_report = json.loads(json_msg.get_payload())
    except Exception, e:
        nilog("Error: Could not decode JSON report '%s': %s" % (json_msg.get_payload(),
                                                                    str(e)))
        return
    
    debug("Returned metadata for %s:" % args[0])
    debug(json.dumps(json_report, indent = 4))

    # If the content was also returned..
    if ct_msg != None:
        debug(ct_msg.__dict__)
        digest= digester_instance.get_digest()[:ni_url.get_truncated_length()]
        digest = make_b64_urldigest(digest)
                                          
        # Check the digest
        if (digest != ni_url.get _digest()):
            nilog("Digest of %s did not verify" % ni_url.get_ni_url())
            return
        etime = time.time()
        duration = etime - stime
        nilog("%s,GET rx fine,ni,%s,size,%d,time,%10.10f" %
              (msgid, ni_url_str, obj_length, duration*1000))

        return ni_url_str
        
#===============================================================================#
resuri=None
def getres(uri)
    resuri = uri
#===============================================================================#
def getlist(ndo_list, dest_dir, host, mprocs, limit):
	from os.path import join
	count = 0
	goodlist = []
	badlist = []
	# start mprocs client processes, comment out the next 2 lines for single-thread
	multi=False
	if mprocs >1:
		pool = multiprocessing.Pool(mprocs)
		multi=True

	for ndo in ndo_list:
            if dest_dir is not None:
                dest = "%s/%s" % (dest_dir, ndo)
            else:
                dest = None
            if multi:
                    pool.apply_async(getone,args=(ndo, host, dest),callback=getres)
                    niuri=resuri
            else:
                    niuri=getone(ndo, host, dest)
            if niuri is None:
                    badlist.append(ndo)
            else:
                    goodlist.append(niuri)
            # count how many we do
            count = count + 1
            # if limit > 0 then we'll stop there
            if count==limit:
                    if multi:
                            pool.close()
                            pool.join()
                    return (count,goodlist,badlist)

	# Close down the multiprocessing if used
	if multi:
		pool.close()
		pool.join()
	return (count,goodlist,badlist)

#===============================================================================#
def py_nigetlist():
    """
    @brief Command line program to perform a NetInf 'get' operation using http
    @brief convergence layer.
    
    Uses NIproc global instance of NI operations class

    Run:
    
    >  nigetlist.py --help

    to see usage and options.

    Exit code is 0 for success, 1 if HTTP returned something except 200,
    and negative for local errors.
    """
    
    # Options parsing and verification stuff
    usage = "%prog [-q] [-l] [-d] [-m|-v] [-f <pathname of content file>] <ni name>\n" + \
            "<ni name> must include location (netloc) from which to retrieve object."
    parser = OptionParser(usage)
    
    parser.add_option("-l", "--list", default=False,
                      action="store_true", dest="list",
                      help="Name of file with list of name to get or - for stdin.")
    parser.add_option("-v", "--verbose", default=False,
                      action="store_true", dest="verbose",
                      default="False"
                      help="Verbose output selected.")
    parser.add_option("-n", "--node", dest="host",
		      type="string",
		      help="The FQDN where I'll send GET messages.")
    parser.add_option("-d", "--dir", default=False,
                      type="string", dest="dest_dir",
                      help="Destination directory for objects gotten.")
    parser.add_option("-m", "--multiprocess", dest="mprocs", default=1,
                      type="int",
                      help="The number of client processes to use in a pool (default 1)")
    parser.add_option("-c", "--count", dest="count", default=0,
                      type="int",
                      help="The number of files to get (default: all)")

    (options, args) = parser.parse_args()

    # Check command line options - -q, -f, -l, -m, -v and -d are optional, <ni name> is mandatory
    if len(args) != 0:
        parser.error("Unrecognixed arguments supplied: %s." str(args))
        sys.exit(-1)
    verbose = not options.quiet


    sys.exit(rv)
                                                                                                    
#===============================================================================#
if __name__ == "__main__":
    py_nigetlist()
