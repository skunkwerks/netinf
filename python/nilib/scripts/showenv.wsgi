#!/usr/bin/env python
"""
@package nilib
@file showenv.wsgi
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

This is a useful WSGI application useful for testing installation of
mod_wsgi in Apache 2 when prepating for use of netinf.wsgi.

It displays the contents of the environment dictionary supplied to the
application by mod_wsgi which allows you to verify the NETINF environment
variables are getting set and contain what you expected.

@code
Revision History
================
Version   Date       Author         Notes
1.0       25/11/2012 Elwyn Davies   Created..

@endcode
"""

#==============================================================================#

def application(environ, start_response):

   # Sorting and stringifying the environment key, value pairs
   response_body = ['%s: %s' % (key, value)
                    for key, value in sorted(environ.items())]
   response_body = '\n'.join(response_body)

   status = '200 OK'
   response_headers = [('Content-Type', 'text/plain'),
                  ('Content-Length', str(len(response_body)))]
   start_response(status, response_headers)

   return [response_body]

