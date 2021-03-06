#!/usr/bin/env python
"""
@package nilib
@file niwsgiserver.py
@brief Simple WSGI server using Python wsgiref and nihandler.py.
@version $Revision: 1.00 $ $Author: elwynd $
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
WSGI wsgiref simple server overview

*** Please run this with python -O niwsgiserver.py ***
See note below for explanation.

This program creates a single threaded server (listening by default on
localhost:8055) and using the WSGI shim interface to the NIHTTPRequestHandler
class in nihandler.py.  This means loading the HTTPRequestShim from
wsgishim.py.

The configuration files designed for the BaseHTTPServer server (see
niserver.py, niserver_main.py and httpshim.py) are *not* used for this
simple server.  The configuration can be done via OS (shell) environment
variables - see the NETINF_DEFAULTS dictionary below.  The defaults use
the same installation directory as the configuration file (/var/niserver)
and the same default cache storage root (/tmp/cache).  The log
is written to stderr by default but can be modified to write to a file
or even a syslog stream. It is not intended that this server be used for
production.  Instead either install mod_wsgi on an Apache server or use
the BaseHTTPServer version.  It should be quite useful for testing as it
can be stopped and started very readily.

Remember that the storage root directory has to exist and be writeable
before starting the server.

The log can be sendt to a file by setting NETINF_SYSLOG_FACILITY to a
file name.  The file path needs to be such that the file can be created
if not there and can be written.  The file name "local0" ... "local9" are
treated specially - they are used for syslog streams and the log is sent
via the syslogger.

@code
Revision History
================
Version   Date       Author         Notes
1.4       25/01/2013 Elwyn Davies   Add mechanism for selecting Redis database.
1.3       10/12/2012 Elwyn Davies   Set up for alternative cache mechanisms.
1.2       07/12/2012 Elwyn Davies   Alter logging setup.
1.1       22/11/2012 Elwyn Davies   Updated name of shim class.
1.0       22/11/2012 Elwyn Davies   Created..

@endcode
"""

#==============================================================================#

import os
import sys
import logging
from wsgiref.simple_server import make_server

# Import nihandler after we have decided what caching scheme to use

#==============================================================================#
# GLOBAL VARIABLES

#=== Configuration Defaults ===
##@var NETINF_DEFAULTS
# dictionary default entries to add to environment dictionary if not set by user
NETINF_DEFAULTS = {
    "NETINF_STORAGE_ROOT": "/tmp/cache",
    "NETINF_GETPUTFORM": "/var/niserver/getputform.html",
    "NETINF_NRSFORM": "/var/niserver/nrsconfig.html",
    "NETINF_FAVICON": "/var/niserver/favicon.ico",
    "NETINF_PROVIDE_NRS": "yes",
    "NETINF_SYSLOG_FACILITY": "", # Use stderr by default
    "NETINF_CACHE": "file",
    "NETINF_REDIS_DB_NUM": "0",
    # Replace NETINF_LOG_INFO with NET_INF_LOG_ERROR, ..._WARN or ..._DEBUG as
    # seems appropriate
    "NETINF_LOG_LEVEL": "NETINF_LOG_INFO"
}

##@var WSGI_PORT
# string environment variable specifying port number for this server
WSGI_PORT = "WSGI_PORT"

##@var WSGI_PORT_DEFAULT
# integer default port number on which to run the server
WSGI_PORT_DEFAULT = 8055

##@var request_hdlr_class
# class used for handling the request.  This is a fudge so that we can postpone
# importing the handler class until we know what caching to use.
# It will be the NIHTTPRequestHandler class as imported from nihandler
request_hdlr_class = None

#==============================================================================#
def application(environ, start_response):
    """
    @brief WSGI application function called for each HTTP request

    Add the NetInf environment variables to the environ dictionary
    taking values from the system environment if present and otherwise
    the deafult values in NETINF_DEFAULTS.

    Create an instance of the handler class and have it handle the request.
    """

    for k, v in NETINF_DEFAULTS.items():
        if k in os.environ:
            environ[k] = os.environ[k]
        else:
            environ[k] = v

    h = request_hdlr_class(log_facility=environ["NETINF_SYSLOG_FACILITY"])
    return h.handle_request(environ, start_response)
    
#------------------------------------------------------------------------------#    
def py_niwsgiserver():
    """
    @brief Reference standalone WSGI server for NetInf protocol handler

    Designed as a test harness for development work on the nihandler.py code
    using the WSGI reference code supplied as standard with Python 2.[567].

    This harness runs the application function above whenever an HTTP request
    is received on the port set up in WSGI_TEST_PORT

    NOTE:  There is a strange 'assert' in the debugging code of the standard
    file wsgiref/handlers.py at around line 179.  This objects to some of the
    headers that are inserted into the responses as being 'hop-by-hop'. The
    relevant line is:
        assert not is_hop_by_hop(name),"Hop-by-hop headers not allowed"
    I suggest commenting this out or starting the script using python -O (capital O)
    which sets __debug__ False.

    According to the W3C documentation, the following hedaers are hop-by-hop:
    - Connection
    - Keep-Alive
    - Proxy-Authenticate
    - Proxy-Authorization
    - TE
    - Trailers
    - Transfer-Encoding
    - Upgrade
    W3C specs say these headers should not be stored by caches or forwarded by
    proxies - since the WSGI reference is a straightforward server, it is unclear
    why it should barf on hop-by-hop heasders.
    
    """
    if WSGI_PORT in os.environ:
        try:
            wsgi_port_num = int(os.environ[WSGI_PORT])
        except ValueError:
            print("Environment variable %s (%s) cannot be converted to an integer" %
                  (WSGI_PORT, os.environ[WSGI_PORT]))
            os._exit(1)
    else:
        wsgi_port_num = WSGI_PORT_DEFAULT

    if "NETINF_CACHE" in os.environ:
        cache_mode = os.environ["NETINF_CACHE"]
    else:
        cache_mode = NETINF_DEFAULTS["NETINF_CACHE"]

    if cache_mode == "file":
        import file_store
    elif cache_mode == "redis":
        import redis_store
    else:
        print "Unrecognized cache mode (use 'file' or 'redis')"
        os._exit(1)

    from nihandler import NIHTTPRequestHandler
    global request_hdlr_class
    request_hdlr_class = NIHTTPRequestHandler
        
    print("Serving for localhost on port %d" % wsgi_port_num)
    print("Using cache mechanism: %s" % cache_mode)
    print("Use Ctrl/C to terminate server.")
    
    httpd = make_server('localhost', 8055, application)
    # Start the server to service request indefinitely.
    # In Windows you can kill it in the Task Manager (python.exe).
    # In Linux a Ctrl-C will do it.
    httpd.serve_forever()

#==============================================================================#
if __name__ == "__main__":
    py_niwsgiserver()
