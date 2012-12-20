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
Version   Date	   Author		 Notes
0.0	  12/14/2012 Stephen Farrell   Created to start forwarding

@endcode
"""
import sys
import os.path
import  random
import cgi
import urllib
import urllib2
import json
import email.parser
import email.message

from ni import ni_errs, ni_errs_txt, NIname, NIproc
from  metadata import NetInfMetaData

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
		
		# hardcode for now
		nexthops=['village.n4c.eu','bollox.example.com'];
		return True,nexthops

	#===============================================================================#
	"""
		fwd a request and wait for a response (with timeout)
	"""
	def do_fwd(self,nexthops,uri,ext,msgid):
		self.loginfo("Inside do_fwd");

		for nexthop in nexthops:
			# send form along

			# Generate NetInf form access URL
			http_url = "http://%s/netinfproto/get" % nexthop
	
			try:
				# Set up HTTP form data for get request
				form_data = urllib.urlencode({ "URI":   uri,
					"msgid": msgid,
					"ext":   ext})
			except Exception, e:
				self.loginfo("do_fwd: to %s form encoding exception: %s" % (nexthop,str(e)));
				continue

			# Send POST request to destination server
			try:
				# Set up HTTP form data for netinf fwd'd get request
				http_object = urllib2.urlopen(http_url, form_data, 1)
			except Exception, e:
				self.loginfo("do_fwd: to %s http POST exception: %s" % (nexthop,str(e)));
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
				continue
		
			if ((obj_length != None) and (len(payload) != obj_length)):
				continue
				
			buf_ct = "Content-Type: %s\r\n\r\n" % http_object.headers["content-type"]
			buf = buf_ct + payload
			msg = email.parser.Parser().parsestr(buf)
			parts = msg.get_payload()
			if msg.is_multipart():
				if len(parts) != 2:
					continue
				json_msg = parts[0]
				ct_msg = parts[1]
			else:
				json_msg = msg
				ct_msg = None
		
			# Extract JSON values from message
			# Check the message is a application/json
			if json_msg.get("Content-type") != "application/json":
				continue
		
			# Extract the JSON structure
			try:
				json_report = json.loads(json_msg.get_payload())
			except Exception, e:
				continue

			curi=NIname(uri)
			curi.validate_ni_url()
			metadata = NetInfMetaData(curi.get_canonical_ni_url())
			metadata.set_json_val(json_report)

			# all good break out of loop
			break

		# make up stuff to return
		# print "do_fwd: success" 

		return FWDSUCCESS,metadata,ct_msg


