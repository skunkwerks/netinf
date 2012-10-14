"""
@package ni
@file __init__.py
@brief Python package __init__ file  for Python nilib.
@version $Revision: 0.00 $ $Author: elwynd $
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

===============================================================================#

Currently nothing is required here.  The modules in the Python nilib
package are:

Command line utilities:
- nicl.py -            basic command line tool to make and check digests using ni.py.
- niget.py -           command line tool to perform NetInf get requests over HTTP.
- nipub.py -           command line tool to perform NetInf publish requests over HTTP.
- nisearch.py -        command line tool to perform NetInf search requests over HTTP.
- pynilib_test.sh -    shell script used for checking ni.py and nicl.py.

Lightweight NI NDO cache server:
 - niserver_main.py -  the main server controller
 - niserver.py -       the guts of the server
 - niserver.conf -     main configuration file - specifies locations for logs, cache
 - niserver_log.conf - configuration file for Python logging system for server
 - niserver_stop.py -  command line utility to stop the server (only from the
                       same host as it was started on)

Support modules:
- ni.py -              library of ni: and nih: URL processing and digest
                       making/checking functions.
- ni_urlparse.py -     slightly hacked version of urlparse.py supporting ni scheme.
- encode.py -          improved mechanism for constructing multipart/form 
                       (extensively modified).
- streaminghttp.py -    allows large uploads to be handled without requiring 
                        equally large memory buffers by allowing iterables and coping
                        with Python generators (essentially as-is from Poster site).
Data Files:
 - README -             Package README file
 - LICENSE -            Package LICENSE file (Apache 2.0)
 - getputform.html -    Form script for NetInf browser GET/PUBLISH/SEARCH forms
 - nrsconfig.html -     Form script for NRS configuration forms
 - niserver.conf -      Main configuration file for pyniserver HTTP CL server
 - niserver_log.conf -  Logging configuration for pyniserver
 - favicon.ico -        Icon file requested by browsers to display in heasders

@code
Revision History
================
Version   Date       Author         Notes
0.0	  13/10/2012 Elwyn Davies   Created.
@endcode
"""
