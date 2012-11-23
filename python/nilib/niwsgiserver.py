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

This program creates a single threaded server (listening by default on
localhost:8055) and using the WSGI shim interface to the NIHTTPHandler
class in nihandler.py.  This means loading the HTTPRequestShim from
wsgishim.py.

The configuration files designed for the BaseHTTPServer server (see
niserver.py, niserver_main.py and httpshim.py) are *not* used for this
simple server.  The configuration can be done via OS (shell) environment
variables - see the NETINF_DEFAULTS dictionary below.  The defaults use
the same installation directory as the configuration file (/var/niserver)
and the same dwefault cache storage root (/tmp/cache).  However the log
is written to stderr - it is not intended that this server be used for
production.  Instead either install mod_wsgi on an Apache server or use
the BaseHTTPServer version.  It should be quite useful for testing as it
can be stopped and started very readily.

Remember that the storage root directory has to exist and be writeable
before starting the server.

@code
Revision History
================
Version   Date       Author         Notes
1.0       22/11/2012 Elwyn Davies   Created..

@endcode
"""

#==============================================================================#

import os
import sys
import logging
from wsgiref.simple_server import make_server
from nihandler import NIHTTPHandler, check_cache_dirs

#==============================================================================#
NETINF_DEFAULTS = {
    "NETINF_STORAGE_ROOT": "/tmp/cache",
    "NETINF_GETPUTFORM": "/var/niserver/getputform.html",
    "NETINF_NRSFORM": "/var/niserver/nrsconfig.html",
    "NETINF_FAVICON": "/var/niserver/favicon.ico",
    "NETINF_PROVIDE_NRS": "yes",
    # Replace NETINF_LOG_INFO with NET_INF_LOG_ERROR, ..._WARN or ..._DEBUG as
    # seems appropriate
    "NETINF_LOG_LEVEL": "NETINF_LOG_INFO"
}

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

    h = NIHTTPHandler(log_stream=environ['wsgi.errors'])
    return h.handle_request(environ, start_response)
    
#------------------------------------------------------------------------------#    
def py_niwsgiserver():
    """
    @brief Reference standalone WSGI server for NetInf protocol handler

    Designed as a test harness for development work on the nihandler.py code
    using the WSGI reference code supplied as standard with Python 2.[567].

    This harness runs a 

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

    # Create a logger just for check_cache_dirs
    logger = logging.getLogger("WSGI_server")
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler(stream=sys.stderr)
    fmt = logging.Formatter("NetInf_start - %(asctime)s %(levelname)s %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    storage_root_env = "NETINF_STORAGE_ROOT"

    if storage_root_env in os.environ:
        storage_root = os.environ[storage_root_env]
    else:
        storage_root = NETINF_DEFAULTS[storage_root_env]

    if not check_cache_dirs(storage_root, logger):
        logger.error("NetInf Cache diretcories are not correctly initialized")
        sys.exit(1)

    httpd = make_server('localhost', 8055, application)
    # Now it is serve_forever() in instead of handle_request().
    # In Windows you can kill it in the Task Manager (python.exe).
    # In Linux a Ctrl-C will do it.
    httpd.serve_forever()

#==============================================================================#
if __name__ == "__main__":
    py_niwsgiserver()
