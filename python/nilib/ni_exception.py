#!/usr/bin/python
"""
@package nilib
@file ni_exception.py
@brief Exceptions for NI NetInf HTTP convergence layer (CL) server and
@brief NRS server.
@version $Revision: 1.01 $ $Author: elwynd $
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
Definitions of exceptions used in Python NI library.

================================================================================
@code
Revision History
================
Version   Date       Author         Notes
1.1       10/12/2012 Elwyn Davies   Added InconsistentDatabase
1.0       05/12/2012 Elwyn Davies   Created from definitions in various other
                                    modules.
@endcode
"""

#==============================================================================#
__all__ = ['UnvalidatedNIname', 'EmptyParams', 'NonEmptyNetlocOrQuery',
           'InconsistentParams', 'InvalidMetaData', 'CacheEntryExists',
           'NoCacheEntry', 'InconsistentDatabase' ]

#==============================================================================#
#=== Exceptions ===
#------------------------------------------------------------------------------#
#=== Raised by ni library module ===

class UnvalidatedNIname(Exception):
    """
    @brief Raised when an inappropriate operation is done on an unvalidated NIname
    """
    pass

class EmptyParams(Exception):
    """
    @brief Raised when a translation is attempted on an NIname with no params (digest)
    """
    pass

class NonEmptyNetlocOrQuery(Exception):
    """
    @brief Raised when a translation is attempted on an hih with netloc or query
    """
    pass

#------------------------------------------------------------------------------#
#=== Raised by cache manager ===

class InconsistentParams(Exception):
    """
    @brief Raised when parameters have inconsistent or not enough information 
    """
    pass

class NoMetaDataSupplied(Exception):
    """
    @brief Raised when no metadata supplied for new cache entry 
    """
    pass

class InvalidMetaData(Exception):
    """
    @brief Raised when metadata read from file is not of right version  
    """
    pass

class CacheEntryExists(Exception):
    """
    @brief Raised when entry exists unexpectedly 
    """
    pass

class NoCacheEntry(Exception):
    """
    @brief Raised when update or get is tried for non-existent entry 
    """
    pass

class InconsistentDatabase(Exception):
    """
    @brief Raised when it appears the Redis database has got out of sync
    @brief with filessystem
    
    """
    pass

