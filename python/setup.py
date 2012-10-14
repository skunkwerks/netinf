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
0.0	  13/10/2012 Elwyn Davies   Created.
@endcode
"""

from setuptools import setup

setup(name='nilib',
      version='1.0',
      description='Library, HTTP CL server and clients for Nilib NetInf protocol package',
      author='Elwyn Davies',
      author_email='davieseb@scss.tcd.ie',
      url='https://sourceforge.net/p/netinf/',
      packages=['nilib'],
      install_requires=['redis', 'python-stdnum', 'PyDNS',
                        'python-magic', 'qrcode'],
      scripts=['nilib/scripts/pynilib_test.sh'],
      entry_points={
                      'console_scripts': [
                           'pyniserver = nilib.niserver_main:py_niserver',
                           'pystopniserver = nilib.niserver_stop:stop_niserver',
                           'pynicl = nilib.nicl:py_nicl',
                           'pyniget = nilib.niget:py_niget',
                           'pynipub = nilib.nipub:py_nipub',
                           'pynisearch = nilib.nisearch:py_nisearch']
                    },
      data_files=[('/var/niserver',
                      ['nilib/data/LICENSE',
                       'nilib/data/README',
                       'nilib/data/niserver.conf',
                       'nilib/data/niserver_log.conf',
                       'nilib/data/getputform.html',
                       'nilib/data/nrsconfig.html',
                       'nilib/data/favicon.ico'])],
      license='Apache License, Version 2.0',
      platforms=['Linux', 'Mac OS', 'Windows'],
      long_description='Python scripts and modules used to provide an HTTP \n' +
      'convergence layer implementation for the NetInf IBN protocol.\n' +
      'Includes a library that manages ni URI scheme names and provides \n' +
      'routines to generate and check the hash digests of files that \n' +
      'are given names from the ni URI scheme.\n\n' +

      "Also included is an implementation of a 'lightweight' NetInf/HTTP/TCP \n" +
      'server and command line clients that can send GET, PUBLISH and SEARCH \n' +
      'NetInf messages to the server, together with a command line tool for \n' +
      'constructing ni URIs for files to be published using the client.\n\n' +

      'The library code is installed as the module nilib in the Python site \n' +
      "library. The command line scripts are installed as 'pynicl', 'pyniserver', \n" +
      "'pyniget', 'pynipublish' and 'pynisearch'.\n"
      )
