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
Version   Date	   Author		 Notes
1.0	  14/01/2012 Elwyn Davies   Created using niget.py as template.
									Incorporate use of feedparser to
@endcode
"""
import sys
import os.path
import math
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
from os.path import join
import tempfile
import logging
from ni import ni_errs, ni_errs_txt, NIname, NIproc
from nifeedparser import DigestFile, FeedParser


#============================================================================#
verbose = False

def debug(string):
	"""
	@brief Print out debugging information string
	@param string to be printed (in)
	"""
	global verbose
	if verbose:
		print string
	return

#===============================================================================#
logger=logging.getLogger("nigetlist")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
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
def getone(ni_url, http_host, dest):
	"""
	@brief Perform a NetInf 'get' from the host for the ni name made with alg and
	@brief digest provided by alg_digest.  If dest is not None leave the output
	@brief in specified path.
	@param ni_url NIname instance with combination of auth, digest algorithm and
						 digest separated
	@param http_host string FQDN or IP address and port of host to send get message to
	@param dest None or string where to put destination contents if received

	Assume that dest provides a directory path into which file can be written
	"""

	# Record start time
	stime= time.time()
	
	# Must be a complete ni: URL with non-empty params field
	rv = ni_url.validate_ni_url(has_params = True)
	if (rv != ni_errs.niSUCCESS):
		nilog("Error: %s is not a complete, valid ni scheme URL: %s" % (ni_url.get_url(), ni_errs_txt[rv]))
		return (False, ni_url.get_url())

	# Generate NetInf form access URL
	ni_url_str = ni_url.get_canonical_ni_url()
	http_url = "http://%s/netinfproto/get" % http_host
	
	# Set up HTTP form data for get request
	form_data = urllib.urlencode({ "URI":   ni_url.get_url(),
								   "msgid": random.randint(1, 32000),
								   "ext":   "" })

	# Send POST request to destination server
	try:
		http_object = urllib2.urlopen(http_url, form_data)
	except Exception, e:
		nilog("Error: Unable to access http URL %s: %s" % (http_url, str(e)))
		return (False, ni_url_str)

	# Get HTTP result code
	http_result = http_object.getcode()

	# Get message headers - an instance of email.Message
	http_info = http_object.info()
	debug("Response type: %s" % http_info.gettype())
	debug("Response info:\n%s" % http_info)

	if (http_result != 200):
		nilog("Get request returned HTTP code %d" % http_result)
		buf = http_object.read()
		debug("HTTP Response: %s" % buf)
		http_object.close()
		return (False, ni_url_str)

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
	if dest is None:
		fd, digested_file = tempfile.mkstemp()
		fo = os.fdopen(fd, "w")
	else:
		digested_file = dest
		fo = None
	debug("Writng content to %s" % digested_file)

	digester = DigestFile(digested_file, fo, ni_url.get_hash_function())

	# Expecting up to three MIME message objects
	# - Top level multipart/mixed,
	# - application/json with metadata, and
	# - any type for content file
	# In dest_list, None results in output being written to a StringIO buffer
	# Other not None items should be filelike objects that can be written to. 
	# If there is only metadata than first ones will cover it
	msg_parser = FeedParser(dest_list=[None, None, digester])

	# Grab and digest the HTTP response body in chunks
	msg_parser.feed(primer)
	payload_len = 0
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
		return (False, ni_url_str)
	# Verify length 
	if ((obj_length != None) and (payload_len != obj_length)):
		nilog("Warning: retrieved contents length (%d) does not match Content-Length header value (%d)" % (len(buf), obj_length))
		return (False, ni_url_str)
		
	debug( msg.__dict__)
	# If the msg is multipart this is a list of the sub messages
	parts = msg.get_payload()
	debug("Multipart: %s" % str(msg.is_multipart()))
	if msg.is_multipart():
		debug("Number of parts: %d" % len(parts))
		if len(parts) != 2:
			nilog("Error: Response from server does not have two parts.")
			return (False, ni_url_str)
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
		return (False, ni_url_str)

	# Extract the JSON structure
	try:
		json_report = json.loads(json_msg.get_payload())
	except Exception, e:
		nilog("Error: Could not decode JSON report '%s': %s" % (json_msg.get_payload(),
																	str(e)))
		return (False, ni_url_str)
	
	debug("Returned metadata for %s:" % ni_url_str)
	debug(json.dumps(json_report, indent = 4))

	msgid = json_report["msgid"]

	# If the content was also returned..
	if ct_msg != None:
		debug(ct_msg.__dict__)
		digest= digester.get_digest()[:ni_url.get_truncated_length()]
		digest = NIproc.make_b64_urldigest(digest)
										  
		# Check the digest
		#print digest, ni_url.get_digest()
		if (digest != ni_url.get_digest()):
			nilog("Digest of %s did not verify" % ni_url.get_url())
			return (False, ni_url_str)
		etime = time.time()
		duration = etime - stime
		nilog("%s,GET rx fine,ni,%s,size,%d,time,%10.10f" %
			  (msgid, ni_url_str, obj_length, duration*1000))

		return(True, ni_url_str)
		
#===============================================================================#
goodlist = []
badlist = []
complete_count = 0

def getres(tuple):
	global goodlist, badlist, complete_count
	complete_count += 1
	if tuple[0]:
		goodlist.append(tuple[1])
	else:
		badlist.append(tuple[1])
	return

#===============================================================================#
def getlist(ndo_list, dest_dir, host, mprocs, limit):
	global complete_count, goodlist, badlist
	count = 0
	# start mprocs client processes, comment out the next 2 lines for single-thread
	multi=False
	if mprocs >1:
			pool = multiprocessing.Pool(mprocs)
			multi=True
	try:
		for ndo in ndo_list.readlines():
			ndo = ndo.strip()
		
			# Create NIname instance for supplied URL 
			if not ndo.startswith("ni:"):
				if host is None:
					nilog("Must provide authority with -n if not included in name: %s" %
						ndo)
					break
				url_str = "ni://%s/%s" % (host, ndo)
			else:
				url_str = ndo
			ni_url = NIname(url_str)
			http_host = ni_url.get_netloc()
			if http_host == "":
				if host is None:
					nilog("Must provide authority with -n if not included in name: %s" %
						ndo)
					break
				ni_url.set_netloc(host)
			elif host is not None:
				http_host = host
	
			if dest_dir is not None:
				dest = "%s/%s" % (dest_dir, ndo)
			else:
				dest = None
			 
			if multi:
				pool.apply_async(getone,args=(ni_url, http_host, dest),callback=getres)
			else:
				getres(getone(ni_url, http_host, dest))
			# count how many we do
			count = count + 1
			# if limit > 0 then we'll stop there
			if count==limit:
					if multi:
							pool.close()
							pool.join()
					return (count, complete_count, goodlist, badlist)
	except KeyboardInterrupt:
		nilog("Keyboard interrupt")
		if multi:
				pool.close()
				pool.join()
		return (count, complete_count, goodlist, badlist)
	except Exception, e:
		nilog("Exception: %s" %  str(e))
		if multi:
				pool.close()
				pool.join()
		return (count, complete_count, goodlist, badlist)
	# Close down the multiprocessing if used
	if multi:
			pool.close()
			pool.join()
	return (count,complete_count, goodlist,badlist)

#===============================================================================#
def getlistzipf(ndo_list, dest_dir, host, mprocs, limit, zipf_s, zipf_count):
	# zipf_s is the distribution parameter
	# zipf_count is the number of times to do a GET
	global complete_count, goodlist, badlist
	count = 0
	pop_size = 0
	# start mprocs client processes, comment out the next 2 lines for single-thread
	multi=False
	if mprocs >1:
			pool = multiprocessing.Pool(mprocs)
			multi=True
	try:
		# first read them in to a list
		ndo_arr = {}
		for ndo in ndo_list.readlines():
			ndo = ndo.strip()
		
			# Create NIname instance for supplied URL 
			if not ndo.startswith("ni:"):
				if host is None:
					nilog("Must provide authority with -n if not included in name: %s" %
						ndo)
					break
				url_str = "ni://%s/%s" % (host, ndo)
			else:
				url_str = ndo
			ni_url = NIname(url_str)
			http_host = ni_url.get_netloc()
			if http_host == "":
				if host is None:
					nilog("Must provide authority with -n if not included in name: %s" %
						ndo)
					break
				ni_url.set_netloc(host)
			elif host is not None:
				http_host = host
	
			if dest_dir is not None:
				dest = "%s/%s" % (dest_dir, ndo)
			else:
				dest = None
			# print "pop_size: %d" % pop_size

			ndo_details= { 'uri': ni_url,'host': http_host,'dest':dest}
			ndo_arr[pop_size]=ndo_details
			pop_size = pop_size + 1

		# now get them but according to the zipf probability
		# index in ndo_arr is rank

		# print "ndo_arr: %s" % ndo_arr

		while count < zipf_count:
			# randomly pick which to get according to zipf distribution
			# 10 isn't random but will do 'till I figure it out
			
			# ind = zg.next() 

			# get an index according to a Zipf distr.
			ind = pop_size+1
			while (ind >= pop_size):
				ind=math.floor(random.expovariate(zipf_s))

			nilog("next zipper,%d" % ind )


			# setup vars
			ni_url=ndo_arr[ind].get('uri')
			http_host=ndo_arr[ind].get('host')
			dest=ndo_arr[ind].get('dest')
			
			# print "ndo_details: %s" % ndo_arr[ind]
			
			if multi:
				pool.apply_async(getone,args=(ni_url, http_host, dest),callback=getres)
			else:
				getres(getone(ni_url, http_host, dest))

			# count how many we do
			count = count + 1
			# if limit > 0 then we'll stop there
			if count==limit:
					if multi:
							pool.close()
							pool.join()
					return (count, complete_count, goodlist, badlist)

	except KeyboardInterrupt:
		nilog("Keyboard interrupt")
		if multi:
				pool.close()
				pool.join()
		return (count, complete_count, goodlist, badlist)
	except Exception, e:
		nilog("Exception: %s" %  str(e))
		if multi:
				pool.close()
				pool.join()
		return (count, complete_count, goodlist, badlist)
	# Close down the multiprocessing if used
	if multi:
			pool.close()
			pool.join()
	return (count,complete_count, goodlist,badlist)

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
	global verbose
	verbose = False
	usage = "%prog [-l <list file name or - (for stdin)>] [-v] [-m <# processes>]\n" + \
			"   [-n <host>] [-c <# max NDOs to get>] [-d <destination dir for files gotten>] [-z <number>]\n" + \
			"The input file should contain lines with any of:\n" + \
			" 1. Complete ni: URI with authority (netloc) component,\n" + \
			" 2. ni: URI with empty authority (netloc) component, or\n" + \
			" 3. just algorithm and digest as alg;val, e.g. sha-256;abc...\n" + \
			"If any of the lines are of types 2 or 3, the -n option MUST be supplied.\n" 
	parser = OptionParser(usage)
	
	parser.add_option("-l", "--list",
					  type="string", dest="list", default="-",
					  help="Name of file with list of name to get or - for stdin (default).")
	parser.add_option("-v", "--verbose",
					  action="store_true", dest="verbose",
					  help="Verbose output selected.")
	parser.add_option("-n", "--node", dest="host",
			  type="string",
			  help="The FQDN where I'll send GET messages.")
	parser.add_option("-d", "--dir", default=None,
					  type="string", dest="dest_dir",
					  help="Destination directory for objects gotten.")
	parser.add_option("-m", "--multiprocess", dest="mprocs", default=1,
					  type="int",
					  help="The number of client processes to use in a pool (default 1)")
	parser.add_option("-c", "--count", dest="count", default=0,
					  type="int",
					  help="The number of files to get (default: all)")
	parser.add_option("-z", "--zipf", dest="zipf_count", default=-1,
					  type="int",
					  help="The number of files to get treating the input list as a 0.5 exponent Zipf rank order") 

	(options, args) = parser.parse_args()

	# Check command line options - -q, -f, -l, -m, -v and -d are optional, <ni name> is mandatory
	if len(args) != 0:
		parser.error("Unrecognixed arguments supplied: %s." % str(args))
		sys.exit(-1)
		
	if options.verbose:
		verbose = True

	if options.list == "-":
		list_chan = sys.stdin
		input_file = "stdin"
	elif os.path.isfile(options.list):
		try:
			list_chan = open(options.list, "r")
			input_file = options.list
		except Exception, e:
			nilog("Unable to open list of NDOs to get: $s" % options.list)
			os._exit(1)

	# Where temprary files will be created
	tempfile.tempdir = "/tmp"


	if options.zipf_count>0:
		nilog("Starting ZIPF nigetlist,list,%s,to,%s,dest_dir,%s,processes,%d,count,%d" 
		  % (input_file, options.host, str(options.dest_dir),
			 options.mprocs,options.count))
		if list_chan == sys.stdin:
			nilog("Waiting for input from stdin")
		# loop over all files below directory and getone() for each we find
		# this uses a zipf distribution to get stuff with an exponent of 0.5
		# and gets things 100 times
		# the 0.5 is the right value for wiki traffic accordng to:
		# https://en.wikipedia.org/wiki/Wikipedia:Does_Wikipedia_traffic_obey_Zipf%27s_law%3F
		cnt, cc, goodlist, badlist = getlistzipf(list_chan, options.dest_dir, options.host,
										 options.mprocs,options.count,0.5,options.zipf_count)
		debug("good: %s" % str(goodlist))
		debug("bad: %s"% str(badlist))
		debug("completed: %d" % cc)
		nilog("Finished ZIPF nigetlist,list,%s,to,%s,dest_dir,%s,processes,%d,count_completed,%d" 
		  	% (input_file, options.host, str(options.dest_dir),
			 	options.mprocs,cc))

	else:
		nilog("Starting nigetlist,list,%s,to,%s,dest_dir,%s,processes,%d,count,%d" 
		  % (input_file, options.host, str(options.dest_dir),
			 options.mprocs,options.count))
		if list_chan == sys.stdin:
			nilog("Waiting for input from stdin")
		# loop over all files below directory and putone() for each we find
		cnt, cc, goodlist, badlist = getlist(list_chan, options.dest_dir, options.host,
										 options.mprocs,options.count)
		debug("good: %s" % str(goodlist))
		debug("bad: %s"% str(badlist))
		debug("completed: %d" % cc)
		nilog("Finished nigetlist,list,%s,to,%s,dest_dir,%s,processes,%d,count_completed,%d" 
		  	% (input_file, options.host, str(options.dest_dir),
			 	options.mprocs,cc))

	os._exit(0)
																							
#===============================================================================#
if __name__ == "__main__":
	py_nigetlist()
