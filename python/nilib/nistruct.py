#!/usr/bin/python
"""
@package nilib
@file nistruct.py
@brief Python wrapper for _nistruct C language extension module.
@version $Revision: 0.05 $ $Author: stephen $
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
   
	   -http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
===============================================================================#

@detail
Provides a trvial weapper for the C language _nistruct extension module.

This module is derived from the standard 'struct' module provided with
Python (in this case 2.7.3) with support added for SDNVs in network (or
big-endian) format).  Code 'v' can be used in format strings to represent
an SDNV.  SDNVs are packed and unpacked as (long) integers.

To cater for the variable length nature of SDNVs the hard constraints on buffer
and input string widths have been relaxed and more dynamic checking is
done instead.

The Python interface has been alterd compared with the basic 'struct' as follows:
- the unpack methods return an extra entry in the tuple at index 0, which
  contains the number of octets unpacked from the input string to satisfy the
  format.
- the 'calcsize' method returnas a 2-tuple with minimum and maximum string sizes
  when using the specified format.


@code
Revision History
================
Version   Date	     Author	    Notes
0.0	  30/12/2012 ElwynDavies    Created.

@endcode
"""
from nilib._nistruct import *
from nilib._nistruct import _clearcache
from nilib._nistruct import __doc__
