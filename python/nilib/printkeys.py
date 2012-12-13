#!/usr/bin/python

import redis
import pprint
c = redis.StrictRedis()
print "List of keys in database:"
redis_keys = c.keys()
pprint.pprint(redis_keys)
