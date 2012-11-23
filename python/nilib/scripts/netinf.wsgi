#!/usr/bin/env python
"""
@package nilib
@file netinf.wsgi
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

It uses the WSGI shim interface to the NIHTTPHandler class in nihandler.py.
This means loading the HTTPRequestShim from wsgishim.py.

All specific configuration for this script is done via SetEnv directives
in the Apache configuration files.  The following variables need to be set:
SetEnv NETINF_STORAGE_ROOT <directory path>
SetEnv NETINF_GETPUTFORM <file path name>
SetEnv NETINF_NRSFORM <file path name>
SetEnv NETINF_FAVICON <file path name>
SetEnv NETINF_PROVIDE_NRS <boolean> [yes/true/1|no/false/0]
SetEnv NETINF_LOG_LEVEL <log level>
Log level can be any of NETINF_LOG_INFO, ..._ERROR, ..._WARN or ..._DEBUG
Default is NETINF_LOG_INFO if this variable is not defined.

Currently this script does not check the existence of the NetInf cache
directories to avoid the overhead on every request.  How to handle this
problem is under consideration.

@code
Revision History
================
Version   Date       Author         Notes
1.0       22/11/2012 Elwyn Davies   Created..

@endcode
"""

#==============================================================================#

from nilib.nihandler import NIHTTPHandler, check_cache_dirs

#==============================================================================#
def application(environ, start_response):
    """
    @brief WSGI application function called for each HTTP request

    Create an instance of the handler class and have it handle the request.
    """
    h = NIHTTPHandler(log_stream=environ['wsgi.errors'])
    return h.handle_request(environ, start_response)
    
#------------------------------------------------------------------------------#    
