#!/usr/bin/python
# PyMail DTN Nomadic Mail System
# Copyright (C) Folly Consulting Ltd, 2009, 2010
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
# 
#        http://www.apache.org/licenses/LICENSE-2.0
# 
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#


"""
Postfix to DTN Interface - Program to stop the PyMail daemon

The main thread in the PyMail daemon (see dp_main/dp_outstation) hangs up
waiting for (any) input on UDP port 2112 or a signal (like SIGINT).

This short program writes a string (what it is is irrelevant) on port 2112
of the local host which should stop the daemon.

Revision History
================
Version   Date       Author         Notes
0.0	  24/06/2010 Elwyn Davies   Created for N4C Summer tests 2010
"""
#!/usr/bin/python
"""
@package ni
@file niserver_stop.py
@brief Control application for stopping running niserver NI HTTP server.
@version $Revision: 0.01 $ $Author: elwynd $
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

Trivial application to send a randowm UDP packet to the control port (2114)
of a running niserver.

The main thread of the server hangs up in an indefinite select system call
waiting for a (UDP) packet to be received on the control port.  When such a
packet is received or a signal is sent to the niserver, the select returns.
The main thread then shuts down the niserver which is running in another
thread so that server_shutdown can be used. The contents of the packet are
irrelevant.

Revision History
================
Version   Date       Author         Notes
0.0	  12/02/2012 Elwyn Davies   Created for SAIL codesprint.
"""

import socket
print "Stopping niserver HTTP daemon..."
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto("stop",("localhost",2114))
s.close()
print "... stop sent."
