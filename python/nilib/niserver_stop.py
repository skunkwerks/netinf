#!/usr/bin/python

"""
@package nilib
@file niserver_stop.py
@brief Control application for stopping running niserver NI HTTP convergence layer server.
@version $Revision: 0.02 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
      This is an adjunct to the NI URI library developed as
      part of the SAIL project. (http://sail-project.eu)

      Specification(s) - note, versions may change
          http://tools.ietf.org/html/farrell-decade-ni-00
          http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
       http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

===========================================================================

Trivial command line application to send a random UDP packet to the control
port (2114) of a running niserver.

The main thread of the server hangs up in an indefinite select system call
waiting for a (UDP) packet to be received on the control port.  When such a
packet is received or a signal is sent to the niserver, the select returns.
The main thread then shuts down the niserver which is running in another
thread so that server_shutdown can be used. The contents of the packet are
irrelevant.

@code
Revision History
================
Version   Date       Author         Notes
0.2       11/10/2012 Elwyn Davies   Make the code into a function so distutils
                                    can make a script for it. 
0.1	  17/09/2012 Elwyn Davies   Improved comments - removed history.
0.0	  12/02/2012 Elwyn Davies   Created for SAIL codesprint.
@endcode
"""

import socket
import sys

def stop_niserver(port=2114):
    print "Stopping niserver HTTP daemon..."
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto("stop",("localhost",port))
    s.close()
    print "... stop sent to port {}.".format(port)
    return(0)

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        stop_niserver(int(sys.argv[1]))
    else:
        stop_niserver()
