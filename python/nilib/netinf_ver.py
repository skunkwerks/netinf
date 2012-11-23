#!/usr/bin/python
"""
@package nilib
@file netinf_ver.py
@brief NetInf and NIserver version strings for package
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

@code
Revision History
================
Version   Date       Author         Notes
1.0       21/11/2012 Elwyn Davies   Contains just the version information for NetInf

@endcode
"""
#==============================================================================#
# List of classes/global functions/global data in file
__all__ = ['NETINF_VER', 'NISERVER_VER'] 
#==============================================================================#
# GLOBAL VARIABLES

##@var NETINF_VER
# Version of NetInf implemented - written into metadata instances and
# HTTP responses. 
NETINF_VER = "NetInf/v0.3_Elwyn"

#==============================================================================#
##@var NISERVER_VER
# Version string for niserver
NISERVER_VER = "NIserver_Python/1.4"



