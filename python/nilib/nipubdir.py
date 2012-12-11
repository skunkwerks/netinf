#!/usr/bin/python
"""
@package nilib
@file nipubdir.py
@brief Command line client to perform a NetInf 'publish' operation using http convergence layer over an entire directory tree and then fetch all those back via HTTP and keep timing information on all that's happened
@version $Revision: 0.04 $ $Author: stephen $
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
Version   Date	   Author		 Notes
0.0	  30/11/2012 Stephen Farrell Started by copying Elwyn's nipub.py and hacking from there
@endcode
"""
import sys
import os
import  random
from optparse import OptionParser
import urllib2
import magic
import json
import platform
import time
import multiprocessing
from multiprocessing import Pool, Lock
import logging


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
# verbose = True
verbose = False

def debug(string):
	"""
	@brief Print out debugging information string
	@param string to be printed (in)
	"""
	if verbose:
		print string
	return



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
def pubone(file_name,alg,host):
	"""
	@brief Do a NetInf PUBLISH for one file
	@param file_name is the file to do now
	"""

	hash_alg=alg
	scheme="ni"
	rform="json"
	ext="{ \"meta\": { \"pubdirs\" : \"yep\" } }"

	# record start time of this
	stime=time.time()

	# Create NIdigester for use with form encoder and StreamingHTTP
	ni_digester = NIdigester()
	# Install the template URL built from the scheme, the authority and the digest algorithm
	rv = ni_digester.set_url((scheme, host, "/%s" % hash_alg))
	if rv != ni_errs.niSUCCESS:
	   nilog("Cannot construct valid ni URL: %s" % ni_errs_txt[rv])
	   return
	debug(ni_digester.get_url())
	# Open the file if possible
	try:
	   f = open(file_name, "rb")
	except Exception, e :
	   debug("Cannot open file %s: Error: %s" %(file_name, str(e)))
	   return
	# Guess the mimetype of the file
	m = magic.Magic(mime=True)
	ctype = m.from_file(file_name)
	debug("Content-Type: %s" % ctype)
	if ctype is None:
		# Guessing didn't work - default
		ctype = "application/octet-stream"
	# Set up HTTP form data for publish request
	# Make parameter for file with digester
	octet_param = MultipartParam("octets",
									 fileobj=f,
									 filetype=ctype,
									 filename=file_name,
									 digester = ni_digester)
	# Make dictionary that will dynamically retrieve ni URI when it has been made
	uri_dict = { "generator": octet_param.get_url,
					 "length": (len(ni_digester.get_url()) + len(";") +
								ni_digester.get_b64_encoded_length())}
	msgid=str(random.randint(1, 2**64)) 
	param_list = [octet_param,
					  ("URI",	   uri_dict),
					  ("msgid",	 msgid),
					  ("ext",	   ext),
					  ("fullPut",   "yes"),
					  ("rform",	 rform)]
	# Construct data generator and header strings
	datagen, headers = multipart_encode(param_list)
	if verbose:
		debug("Parameters prepared: %s"% "".join(datagen))

	# Set up streaming HTTP mechanism - register handlers with urllib2
	# get out for now, don't do it
	opener = streaminghttp.register_openers()
	# Where to send the publish request.
	http_url = "http://%s/netinfproto/publish" % host
	# debug("Accessing: %s" % http_url)
	# Send POST request to destination server
	fsize=os.path.getsize(file_name)
	nilog("%s,PUBLISH tx,file,%s,size,%d,to,%s" % (msgid,file_name,fsize,host))
	try:
		req = urllib2.Request(http_url, datagen, headers)
	except Exception, e:
		nilog("%s,PUBLISH tx error" % msgid);
		if verbose:
			nilog("Error: Unable to create request for http URL %s: %s" %
				  (http_url, str(e)))
		f.close()
		return
	# Get HTTP results
	try:
		http_object = urllib2.urlopen(req)
	except Exception, e:
		nilog("%s,PUBLISH rx error" % msgid);
		if verbose:
			nilog("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
		f.close()
		return
	f.close()
	if verbose:
		nilog("Digester result: %s" % octet_param.get_url())
	# Get message headers
	http_info = http_object.info()
	http_result = http_object.getcode()
	if verbose:
		debug("HTTP result: %d" % http_result)
		debug("Response info: %s" % http_info)
		debug("Response type: %s" % http_info.gettype())

	# Read results into buffer
	payload = http_object.read()
	http_object.close()
	# debug(payload)
	# Report outcome
	if (http_result != 200):
		if verbose:
			debug("Unsuccessful publish request returned HTTP code %d" %
				  http_result) 
		nilog("%s,PUBLISH rx error bad response status,%d" % (msgid,http_result));
		return
	# Check content type of returned message matches requested response type
	ct = http_object.headers["content-type"]
	if ct != "application/json":
		if verbose:
			debug("Error: Expecting JSON coded (application/json) "
					  "response but received Content-Type: %s" % ct)
		nilog("%s,PUBLISH rx error bad content type,%s" % (msgid,ct));
		return
	# If output of response is expected, print in the requested format
	if verbose:
		nilog( "Publication of %s successful:" % target)

	# JSON cases
	try:
		json_report = json.loads(payload)
	except Exception, e:
		if verbose:
			nilog("Error: Could not decode JSON report '%s': %s" % (payload,
																			str(e)))
			nilog("%s, PUBLISH rx error bad json decode" % msgid);
		return

	if verbose: 
		print json.dumps(json_report, indent = 4)
	etime=time.time()
	duration=etime-stime
	niuri=json_report["ni"]
	nilog("%s,PUBLISH rx fine,ni,%s,size,%d,time,%10.10f" % (msgid,niuri,fsize,duration*1000))

	return niuri


#===============================================================================#
resuri=""
def getres(uri):
	resuri=uri
	

#===============================================================================#
def pubdirs(path,alg,host,mprocs):
	from os.path import join
	count = 0
	# to just publish a few files uncomment set max to something >0
	max = 4
	# max = -1
	goodlist = []
	badlist = []
	# start 10 client processes, comment out the next 2 lines for single-thread
	multi=False
	if mprocs >1:
		pool = multiprocessing.Pool(mprocs)
		multi=True

	for root, dirs, files in os.walk(path):
		for name in files:
			if multi:
				pool.apply_async(pubone,args=(join(root,name),alg,host),callback=getres)
				niuri=resuri
			else:
				niuri=pubone(join(root,name),alg,host)
			if niuri is None:
				badlist.append(join(root,name))
			else:
				goodlist.append(niuri)
			# count how many we do
			count = count + 1
			# uncomment these if you just want a few published
			if count==max:
				if multi:
					pool.close()
					pool.join()
				return (count,goodlist,badlist)

	# comment out the next two lines for single-threaded
	if multi:
		pool.close()
		pool.join()
	return (count,goodlist,badlist)

#===============================================================================#
def py_nipubdir():
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
	usage = "%%prog -d <pathname of content directory> -n <FQDN of netinf node> [-a <hash alg>] [-m NN]"

	parser = OptionParser(usage)
	
	parser.add_option("-d", "--dir", dest="dir_name",
					  type="string",
					  help="Pathname for directory to be published.")
	parser.add_option("-a", "--alg", dest="hash_alg", default="sha-256",
					  type="string",
					  help="Hash algorithm to be used for NI URIs. Defaults to sha-256.")
	parser.add_option("-n", "--node", dest="host",
					  type="string",
					  help="The FQDN where I'll send PUBLISH messages.")
	parser.add_option("-m", "--multiprocess", dest="mprocs", default=1,
					  type="int",
					  help="The number of client processes to use in a pool (default 1)")

	(options, args) = parser.parse_args()

	# Check command line options:
	# Arguments -h is optional, all others needed


	# Specifying more than one of -w, -p, -j and -v is inappropriate.
	if len(args) != 0:
		parser.error("Unrecognized arguments %s supplied." % str(args))
		sys.exit(-1)
	if options.dir_name == None:
		parser.error("You must supply a directory name with -d")
		sys.exit(-1)
	if options.host == None: 
		parser.error("You must supply a host name with -n")
		sys.exit(-1)

	nilog("Starting nipubdir,dir,%s,to,%s,alg,%s,processes,%d,count,0" 
			% (options.dir_name,options.host,options.hash_alg,options.mprocs))

	# loop over all files below directory and putone() for each we find
	count,goodlist,badlist=pubdirs(options.dir_name,options.hash_alg,options.host,options.mprocs)

	# print goodlist
	# print badlist

	nilog("Finished nipubdir,dir,%s,to,%s,alg,%s,processes,%d,count,%d" 
		% (options.dir_name,options.host,options.hash_alg,options.mprocs,count))

	sys.exit(0)

#===============================================================================#
if __name__ == "__main__":
 
	loginitted=False
	py_nipubdir()
