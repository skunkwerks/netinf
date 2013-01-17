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
import tempfile

import threading
import redis

from ni import ni_errs, ni_errs_txt, NIname, NIproc
from  metadata import NetInfMetaData

#===============================================================================#
# moral equivalent of #define

FWDSUCCESS = 0
FWDERROR = 1
FWDTIMEOUT = 2

#===============================================================================#
# database field names etc
NIROUTER = "nirouter"
GET_FWD = "GET_FWD"
GET_RES = "GET_RES"
PUB_FWD = "PUB_FWD"
PUB_DST = "PUB_DST"
SCH_FWD = "SCH_FWD"
SCH_DST = "SCH_DST"



#===============================================================================#

"""
	Overall forwarding scheme

	We might forward anything, GET, PUBLISH or SEARCH

	If we already "know the answer" locally, we do not
	forward, but "know the answer" is different for 
	different messages.

	The following "roles" exist, these are allo locally configured for
	all relevant requests, i.e. if I'm set to GET_RES then that's true
	for all GETs
	NIROUTER - if set then some of the things below are meaningful
	GET_FWD  - if set then I will forward some GETs
	GET_RES  - if set then I will try to RESolve get responses with locators but no NDO
	PUB_FWD  - if set then I will try to forward PUBLISHes
	PUB_DST  - if set then I consider myself the destination for PUBLISHes
	SCH_FWD  - if set then I will try to forward SEARCHes
	SCH_DST  - if set then I consider myself the destination for SEARCHes

	Rules:
		SCH_FWD = ~SCH_DST one has to be true, the other false
		Both PUB_DST and PUB_FWD can be true, in that case, I handle 
			locally, and then separately ("longer" msg-id)
			re-PUBLISH upstream

	For GET/SEARCH if I have a matching entry locally, then that's the
	final answer

	Stuff below here is earlier, needs to reflect coding as that happens

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

		# setup redis stuff
		# note: we're using our own tables in redis for this so locks
		# etc are just local to the forwarder class
		# another note: even if the main NetInf server is using only
		# file based storage, this class only uses redis, always
		self.db = redis.Redis()
		self.cache_lock = threading.Lock()

		# im_a_router=self.check_role(NIROUTER)

		return

	#===============================================================================#
	"""
		set defaults for rolename values if they don't exist
	"""
	def set_def_roles(self):
		self.loginfo("Inside set_def_roles");

		with self.cache_lock:
			try:
				self.db.set(NIROUTER + "/" + NIROUTER,True)
				self.db.set(NIROUTER + "/" + GET_FWD,True)
				self.db.set(NIROUTER + "/" + GET_RES,False)
				self.db.set(NIROUTER + "/" + PUB_FWD,False)
				self.db.set(NIROUTER + "/" + PUB_DST,False)
				self.db.set(NIROUTER + "/" + SCH_FWD,False)
				self.db.set(NIROUTER + "/" + SCH_DST,False)

				# this is just temporary until we have a real
				# RIB->FIB thing
				nhs={}
				nhs[0]='village.n4c.eu'
				nhs[1]='bollox.example.com'
				self.db.hmset(NIROUTER+"/"+GET_FWD+"/nh",nhs)
			except Exception, e:
				# we're screwed!
				self.loginfo("Exception in set_def_roles, %s" % str(e));
				return False

		return True
	

	#===============================================================================#
	"""
		return setting for that rolename
	"""
	def check_role(self,rolename):
		# self.loginfo("Inside check_role");
		roleset=False

		try:
			roleset=self.db.get(NIROUTER + "/" + rolename)
		except Exception, e:
			# oops, maybe never set? try that and then once more for luck
			self.loginfo("Exception in check_role, %s" % str(e));
			try:
				self.set_def_roles()
				roleset=self.db.get(NIROUTER + "/" + rolename)
			except Exception, e:
				self.loginfo("Exception 2 in check_role, %s" % str(e));
				return FALSE

		if roleset == None:
			# self.loginfo("Bummer 1 in check_role")
			try:
				self.set_def_roles()
				roleset=self.db.get(NIROUTER + "/" + rolename)
			except Exception, e:
				self.loginfo("Exception 2 in check_role, %s" % str(e));
				return False

		if roleset == None:
			self.loginfo("Bummer in check_role")
			return False
			

		return roleset


	#===============================================================================#
	"""
		check if I know where to forward a request (GET, PUBLISH or SEARCH)
		- might use an NRS
	"""
	def check_fwd(self,role,niname,ext):
		self.loginfo("Inside check_fwd");
		if self.check_role(role) != "True":
			self.loginfo("check_fwd bad role %s, got: %s" % (role,self.check_role(role)));
			return False,None

		# check if we have a nexthop for that role
		try:
			nexthops={}
			redis_key=NIROUTER + "/" + role + "/" + "nh"
			all_vals = self.db.hgetall(redis_key)
			nexthops=self.db.hmget(redis_key,all_vals)
		except Exception, e:
			self.loginfo("Exception in check_fwd, %s" % str(e));
			return False,None
		
		# hardcode for now
		# nexthops=['village.n4c.eu','bollox.example.com'];
		return True,nexthops

	#===============================================================================#
	"""
		fwd a request and wait for a response (with timeout)
	"""
	def do_get_fwd(self,nexthops,uri,ext,msgid):
		self.loginfo("Inside do_fwd");
		metadata=""
		fname=""

		for nexthop in nexthops:
			# send form along
			self.loginfo("checking via %s" % nexthop)

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
				self.loginfo("do_fwd: weird http status code %d" % http_result)
				continue
		
			if ((obj_length != None) and (len(payload) != obj_length)):
				self.loginfo("do_fwd: weird lengths payload=%d and obj=%d" % (len(payload),obj_length))
				continue
				
			buf_ct = "Content-Type: %s\r\n\r\n" % http_object.headers["content-type"]
			buf = buf_ct + payload
			msg = email.parser.Parser().parsestr(buf)
			parts = msg.get_payload()
			if msg.is_multipart():
				if len(parts) != 2:
					self.loginfo("do_fwd: funny number of parts: %d" % len(parts))
					continue
				json_msg = parts[0]
				ct_msg = parts[1]
				try:
					temp_fd,fname=tempfile.mkstemp();
					f = os.fdopen(temp_fd, "w")
					f.write(ct_msg.get_payload())
					f.close()
				except Exception,e:
					self.loginfo("do_fwd: file crap: %s" % str(e))
					return FWDERROR,metadata,fname
			else:
				json_msg = msg
				ct_msg = None

			# Extract JSON values from message
			# Check the message is a application/json
			if json_msg.get("Content-type") != "application/json":
				self.loginfo("do_fwd: weird content type: %s" % json_msg.get("Content-type"))
				continue
		
			# Extract the JSON structure
			try:
				json_report = json.loads(json_msg.get_payload())
			except Exception, e:
				self.loginfo("do_fwd: can't decode json: %s" % str(e));
				continue

			curi=NIname(uri)
			curi.validate_ni_url()
			metadata = NetInfMetaData(curi.get_canonical_ni_url())
			self.loginfo("Metadata I got: %s" % str(json_report))
			metadata.insert_resp_metadata(json_report)

			# if I've the role GET_RES and there's locators then 
			# follow those now
			if ct_msg == None and self.check_role(GET_RES):
				self.loginfo("I'm a GET_RES type of node - going to try follow")
				self.loginfo("meta: %s" % str(json_report))
				# check for locators
				locators = metadata.get_loclist()
				self.loginfo("locs: %s" % str(locators))
				# try follow locators
				for loc in locators:
					self.loginfo("GET_RES following: %s" % loc)

					# Send GET request to destination server
					try:
						# Set up HTTP form data for netinf fwd'd get request
						http_object = urllib2.urlopen(loc, "", 1)
					except Exception, e:
						self.loginfo("do_fwd: to %s http exception: %s" % (loc,str(e)));
						continue
					# Get HTTP result code
					http_result = http_object.getcode()
					if http_result != 200:
						continue
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
					try:
						temp_fd,fname=tempfile.mkstemp();
						f = os.fdopen(temp_fd, "w")
						f.write(payload)
						f.close()
					except Exception,e:
						self.loginfo("do_fwd: file crap: %s" % str(e))
						return FWDERROR,metadata,fname
					http_object.close()
					# break out from getting locs
					break;
		
			# all good break out of loop
			break

		# make up stuff to return
		# print "do_fwd: success" 

		return FWDSUCCESS,metadata,fname

if __name__ == "__main__":
	import logging
	logger = logging.getLogger("test")
	logger.setLevel(logging.DEBUG)
	ch = logging.StreamHandler()
	fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
	ch.setFormatter(fmt)
	logger.addHandler(ch)
	fwd = forwarder(logger)
	fwd.loginfo("Starting")
	roleset=fwd.check_role(NIROUTER)
	fwd.loginfo("Done: %s" % roleset)

