#!/usr/bin/python
"""
@package nilib
@file redisflush.py
@brief To flush the entire Redis database used by niserver.
@version $Revision: 1.01 $ $Author: elwynd $
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

================================================================================

@details
Clear out the Redis database and the corresponding object storage cache.

@code
Revision History
================
Version   Date       Author         Notes
1.0       13/12/2012 Elwyn Davies   Create.

@endcode
"""

#==============================================================================#

import redis
import os

STORAGE_ROOT_KEY = "NISERVER_STORAGE_ROOT"
try:
    ans = raw_input("This will flush the Redis database.  Are you sure you want to continue? [y/n] " )
except:
    print "Interrupted"
    os._exit(1)
if ans == "y":
    c = redis.StrictRedis()
    try:
        storage_root = c.get(STORAGE_ROOT_KEY)
        if c.flushdb():
            print "Database flushed"
            # Now go delete the object cache
        else:
            print "Database flushing failed"
            os._exit(1)
    except Exception, e:
        print "Connection to database failed: %s" % str(e)
        os._exit(1)
else:
    print "Abandoned flushing"
    os._exit(1)

if storage_root is None:
    print "Key %s was not set in database - need to manually remove object cache" % \
          STORAGE_ROOT_KEY
    os._exit(1)

if os.path.isdir(storage_root):
    ans = raw_input("OK to delete storage cache from %s? [y/n] " % storage_root)
    if ans == "y" :
        os.system("rm -rf %s/*" % storage_root)
        os._exit(0)
    else:
        print "Abandoned deleteing object cache"
        os._exit(1)
else:
    print "Storage root directory %s does not exist" % storage_root
    os._exit(1)


