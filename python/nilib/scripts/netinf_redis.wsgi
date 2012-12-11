#!/usr/bin/env python
"""
@package nilib
@file netinf_redis.wsgi
@brief WSGI application script for use with mod_wsgi and nihandler.py.
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
WSGI mod_wsgi application script

This file contains the function named 'application' that is called
to handle an HTTP request via the Apache 2 mod_wsgi module.

It us setup to pull in the rediss_tore module that tells the rest of the system
to use the Redis database to store the metadata. 

It uses the WSGI shim interface to the NIHTTPHandler class in nihandler.py.
This means loading the HTTPRequestShim from wsgishim.py.

All specific configuration for this script is done via SetEnv directives
in the Apache configuration files.  The following variables need to be set:
SetEnv NETINF_STORAGE_ROOT <directory path>
SetEnv NETINF_GETPUTFORM <file path name>
SetEnv NETINF_NRSFORM <file path name>
SetEnv NETINF_FAVICON <file path name>
SetEnv NETINF_PROVIDE_NRS <boolean> [yes/true/1|no/false/0]
SetEnv NETINF_LOG_FACILITY <facility name> (e.g., "local0")
SetEnv NETINF_LOG_LEVEL <log level>
Log level can be any of NETINF_LOG_INFO, ..._ERROR, ..._WARN or ..._DEBUG
Default is NETINF_LOG_INFO if this variable is not defined.

@code
Revision History
================
Version   Date       Author         Notes
1.0       10/12/2012 Elwyn Davies   Cloned from netinf_file.wsgi to use Redis.

@endcode
"""

#==============================================================================#

# Module that indicates we are using Redis to store metadata
# IT IS IMPORTANT THAT THIS IS FIRST!
import nilib.redis_store
from nilib.nihandler import NIHTTPRequestHandler

#==============================================================================#
def application(environ, start_response):
    """
    @brief WSGI application function called for each HTTP request

    Create an instance of the handler class and have it handle the request.
    """
    # Determine which syslog stream to use
    if "NETINF_LOG_FACILITY" in environ:
        lf = environ["NETINF_LOG_FACILITY"]
    else:
        lf = "local0"
        
    h = NIHTTPRequestHandler(log_facility=lf)
    return h.handle_request(environ, start_response)
    
#------------------------------------------------------------------------------#    
