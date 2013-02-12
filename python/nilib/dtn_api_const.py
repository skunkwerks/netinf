#!/usr/bin/python
"""
@package DTN2
@file dtn_api_const.py
@brief Constants used by DTN2 API but not wrapped by SWIG
@version $Revision: 1.00 $ $Author: stephen $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
	   -http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
===============================================================================#

@detail
Conatants ised by DTN2 API but not wrapped by SWIG

@code
Revision History
================
Version   Date	     Author	    Notes
1.0	  14/01/2013 ElwynDavies    Created.

@endcode
"""

#==============================================================================#
# GLOBAL VARIABLES

#------------------------------------------------------------------------------#
# DTN block types

##@var   PRIMARY_BLOCK
# integer   Initial header block - internal only -- not in spec
PRIMARY_BLOCK               = 0x000
##@var   PAYLOAD_BLOCK
# integer   Payload block defined in RFC 5050
PAYLOAD_BLOCK               = 0x001
##@var   BUNDLE_AUTHENTICATION_BLOCK
# integer   Extension block defined in RFC 6257
BUNDLE_AUTHENTICATION_BLOCK = 0x002
##@var   PAYLOAD_SECURITY_BLOCK
# integer   Extension block defined in RFC 6257
PAYLOAD_SECURITY_BLOCK      = 0x003
##@var   CONFIDENTIALITY_BLOCK
# integer   Extension block defined in RFC 6257
CONFIDENTIALITY_BLOCK       = 0x004
##@var   PREVIOUS_HOP_BLOCK
# integer   Extension block defined in RFC 6259
PREVIOUS_HOP_BLOCK          = 0x005
##@var   METADATA_BLOCK
# integer   Extension block defined in RFC 6258
METADATA_BLOCK              = 0x008
##@var   EXTENSION_SECURITY_BLOCK
# integer   Extension block defined in RFC 6257
EXTENSION_SECURITY_BLOCK    = 0x009
##@var   SESSION_BLOCK
# integer   Extension block not in spec yet
SESSION_BLOCK               = 0x00c
##@var   AGE_BLOCK
# integer   Extension block defined in draft-irtf-dtnrg-bundle-age-block-01
AGE_BLOCK                   = 0x00a
##@var   QUERY_EXTENSION_BLOCK
# integer   Extension block defined in draft-irtf-dtnrg-bpq-00
QUERY_EXTENSION_BLOCK       = 0x00b
##@var   SEQUENCE_ID_BLOCK
# integer   Extension block not in spec yet
SEQUENCE_ID_BLOCK           = 0x010
##@var   OBSOLETES_ID_BLOCK
# integer   Extension block not in spec yet
OBSOLETES_ID_BLOCK          = 0x011
##@var   API_EXTENSION_BLOCK
# integer   Extension block - internal only -- not in spec
API_EXTENSION_BLOCK         = 0x100
##@var   UNKNOWN_BLOCK
# integer   Extension block - internal only -- not in spec
UNKNOWN_BLOCK               = 0x101
