#!/usr/bin/env python
"""
@package ni
@file setup.py
@brief Python distutils setup file  for Python nilib.
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

@code
Revision History
================
Version   Date       Author         Notes
0.6       06/12/2012 Elwyn Davies   Add requirement for Python posix_ipc module.
0.5       06/12/2012 Elwyn Davies   Add location for syslog log file.
0.4       25/11/2012 Elwyn Davies   Add requirement for PIL (Python Imaging Library).
                                    Organize directory image for mod_wsgi setup.
                                    Provide for specification of data installation
                                    directory via environment variable NETINF_DAT_DIR.
0.3       22/11/2012 Elwyn Davies   Version 2.0: Modify nihandler.py, http_shim.py, add 
                                    wsgishim.py, netinf_ver.py, niwsgiserver.py and test
                                    code for WSGI server to allow NIHTTPHandler to be 
                                    driven form any one of BaseHTTPServer, wsgiref server
                                    or the mod_wsgi in an Apache server. 
0.2       19/11/2012 Elwyn Davies   Split nihandler.py and httpshim.py out of niserver.py. 
0.1       15/10/2012 Elwyn Davies   Moved README and LICENSE files to doc directory.
0.0	  13/10/2012 Elwyn Davies   Created.
@endcode
"""

from setuptools import setup
import os
datadir_envvar = "NILIB_DATA_DIR"
if datadir_envvar in os.environ:
	datadir = os.environ[datadir_envvar]
	print("Installing NI server data files in %s" % datadir)
else:
	datadir = "/var/niserver"
	print("Installing NI server fata files in default location (%s)" %datadir)

setup(name='nilib',
      version='r2.0',
      description='Library, HTTP CL server and clients for Nilib NetInf protocol package',
      author='Elwyn Davies',
      author_email='davieseb@scss.tcd.ie',
      url='https://sourceforge.net/p/netinf/',
      packages=['nilib'],
      install_requires=['redis', 'python-stdnum', 'PyDNS', 'posix_ipc',
                        'python-magic', 'qrcode', 'pil', 'doxypy'],
      scripts=['nilib/scripts/pynilib_test.sh'],
      entry_points={
                      'console_scripts': [
                           'pyniserver = nilib.niserver_main:py_niserver',
                           'pystopniserver = nilib.niserver_stop:stop_niserver',
                           'pynicl = nilib.nicl:py_nicl',
                           'pyniget = nilib.niget:py_niget',
                           'pynipub = nilib.nipub:py_nipub',
                           'pynisearch = nilib.nisearch:py_nisearch',
			   'pyniwgsiserver = nilib.niwsgiserver.py:py_niwsgiserver']
                    },
      include_package_data=True,
      data_files=[(datadir,
                      ['nilib/data/niserver.conf',
                       'nilib/data/niserver_log.conf',
                       'nilib/data/getputform.html',
                       'nilib/data/nrsconfig.html',
                       'nilib/data/help.html',
                       'nilib/data/favicon.ico'
                       ]),
                  (datadir+"/wsgi/wsgi-apps",
                      ['nilib/scripts/netinf.wsgi',
                       'nilib/scripts/test.wsgi',
                       'nilib/scripts/showenv.wsgi'
                       ]),
                  (datadir+"/wsgi/www",
                      ['nilib/data/getputform.html',
                       'nilib/data/nrsconfig.html',
                       'nilib/data/help.html',
                       'nilib/data/favicon.ico'
                       ]),
                  (datadir+"/wsgi/doc",
                      [ # Create empty directory ready for Doxygen documentation.
                       ]),
                  (datadir+"/wsgi/log",
                      [ # Create empty directory ready for syslog log.
                       ]),
                  (datadir+"/wsgi/cache",
                      [ # Create empty directory ready for cache
                       ])],
      license='Apache License, Version 2.0',
      platforms=['Linux', 'Mac OS', 'Windows'],
      long_description='Python scripts and modules used to provide an HTTP \n' +
      'convergence layer implementation for the NetInf IBN protocol.\n' +
      'Includes a library that manages ni URI scheme names and provides \n' +
      'routines to generate and check the hash digests of files that \n' +
      'are given names from the ni URI scheme.\n\n' +

      "Also included is an implementation of a 'lightweight' multithreaded \n" +
      'NetInf/HTTP/TCP server using the standard Python BaseHTTPServer framework, \n' +
      'a simple Python WSGI server using the standard Python wsgiref framework \n' +
      "intended primarily for testing the handler code and a 'wsgi' script that \n" +
      'allows the handler to be invoked from an Apache 2  mod_wsgi WSGI module. \n' +
      "All of these server implementations use a common handler module 'nihandler.py'. \n" +
      'Also provided are command line clients that can send GET, PUBLISH and SEARCH \n' +
      'NetInf messages to the servers, together with a command line tool for \n' +
      'constructing ni URIs for files to be published using the client.\n\n' +

      'The library code is installed as the module nilib in the Python site \n' +
      "library. The command line scripts are installed as 'pynicl', 'pyniserver', \n" +
      "'pyniwsgiserver', 'pyniget', 'pynipublish' and 'pynisearch'.\n" +

      "There is some testing code bth at the end of various modules and in the  \n" +
      "'text' directory.  The code in the 'test' directory  is not copied during \n" +
      "installation process." 
      )
