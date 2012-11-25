#! /usr/bin/env python
"""
@package nilib
@file test_wsgi_server.py
@brief Standalone tests for wsgishim.py handling a test server that prints
       the environment dictionary asa response.
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
Simple server with wsgishim.py tests overview

Creates a WSGI-based standalone server using the WSGI reference code in the
standard Python distribution designed to test the WSGI version of HTTPRequestShim.

The server runs on localhost port 8054  (as written here). When started in will
serve one request before exiting.

The handles that uses the HTTPRequestShim only serves GET requests.

The URL path is ignored and the response is a plain text document enumerating
the environ dictionary fed to the handler.

It demonstrates the response iterator incorporated into the HTTPRequestHandler
class.

Logging output is written to stderr.

@code
Revision History
================
Version   Date       Author         Notes
1.0       22/11/2012 Elwyn Davies   Created

@endcode
"""

#==============================================================================#
# Test WSGI server
from wsgiref.simple_server import make_server

from nilib.wsgishim import wsgiHTTPRequestShim

#==============================================================================#
# TESTING CODE
#==============================================================================#
#==== TEST CLASS ====
class EnvPrintHandler(wsgiHTTPRequestShim):
    def do_GET(self):
        bl = 0
        for key, value in sorted(self.environ.items()):
            s = "%s: %s\n" % (key, value)
            bl += len(s)
            self.send_string(s)
        self.send_response(200, "OK")
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(bl))
        self.end_headers()
        return
        

#==== TEST FUNCTIONS ====
def application(environ, start_response):

    environ["NETINF_STORAGE_ROOT"] = "/tmp/cache"
    environ["NETINF_GETPUTFORM"] = "/var/niserver/getputform.html"
    environ["NETINF_NRSFORM"] = "/var/niserver/nrsconfig.html"
    environ["NETINF_FAVICON"] = "/var/niserver/favicon.ico"
    environ["NETINF_PROVIDE_NRS"] = "no"
    
    h = EnvPrintHandler(log_stream=environ['wsgi.errors'])
    return h.handle_request(environ, start_response)

#==============================================================================#
# EXECUTE TESTS
#==============================================================================#
# Instantiate the WSGI server.
# It will receive the request, pass it to the application
# and send the application's response to the client
httpd = make_server(
   'localhost', # The host name.
   8054, # A port number where to wait for the request.
   application # Our application object name, in this case a function.
   )

# Wait for a single request, serve it and quit.
httpd.handle_request()
