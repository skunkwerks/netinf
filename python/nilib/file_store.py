#!/usr/bin/env python
"""
@package nilib
@file file_store.py
@brief Dummy module that indicates that the cache should use all filesystem
@brief for both content and metadata.
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
Dummy module that is used by other modules to control the loading of the
correct NetInfCache class version. With this module imported, it is expected
that the cache will use the filesystem to store both metadata and
content files.

@code
Revision History
================
Version   Date       Author         Notes
1.0       10/12/2012 Elwyn Davies   Created.

@endcode
"""

#==============================================================================#
# Dummy module - filesystem storage is the default.
use_redis_meta_cache = False
use_file_meta_cache = True
