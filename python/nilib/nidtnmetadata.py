#!/usr/bin/python
"""
@package nilib
@file nidtnmetadata.py
@brief Encode and decode routines for RFC 5050 Bundle Protocol Metadata blocks.
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
Uses nistruct to encode and decode DTN Bundle Protocol Metadata blocks between
a dictionary and a string.

Elements of BPQ block on the wire:
Name           Type               Description
ontology       SDNV               Metadata ontology type
ontoloogy_data string             Data for this ontology

@code
Revision History
================
Version   Date	     Author	    Notes
1.0	  14/01/2013 ElwynDavies    Created.

@endcode
"""

#==============================================================================#
# Standard modules
from types import *

# Nilib modules
from _nistruct import pack, pack_into, unpack, unpack_from, struct_error

#==============================================================================#

class Metadata:
    """
    @brief Encapsulation for a RFC 5050 Metadata block

    @detail
    Holds details for a single Metadata block, providing validation, decoding
    from an on-the-wire string and generation of the on-the-wire string.

    """
    #--------------------------------------------------------------------------#
    # CONSTANT VALUES USED BY CLASS

    # --- Ontology values ---

    ##@var ONTOLOGY_URI
    # integer   Value of ontology for Metadata block carrying a URI string
    ONTOLOGY_URI				= 0x01
    ##@var ONTOLOGY_JSON
    # integer   Value of ontology for Metadata block carrying a JSON string
    ONTOLOGY_JSON				= 0xc0
    ##@var ONTOLOGY_PAYLOAD_PLACEHOLDER
    # integer   Value of ontology for Metadata block representing
    #           a payload placeholder
    ONTOLOGY_PAYLOAD_PLACEHOLDER		= 0xc1

    ##@var ONTOLOGY_EXPT_MIN
    # integer   Low end of experimental range for Ontology types
    ONTOLOGY_EXPT_MIN			= 0xc0
    ##@var ONTOLOGY_EXPT_MAX
    # integer   High end of experimental range for Ontology types
    ONTOLOGY_EXPT_MAX			= 0xff
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var ontology
    # integer    Ontology type for Metadata block
    ##@var ontology_data
    # string     Data associated with this ontology
    
    #--------------------------------------------------------------------------#
    def __init__(self):
        """
        @brief Constructor - set default values
        """
        # The ontology is deliberately set illegal
        self.ontology = 0
        self.ontology_data = None
        return

    #--------------------------------------------------------------------------#
    def init_from_net(self, inputstr):
        """
        @brief Unpack string into instance variables - validation later
        @param inputstr string block as received from network
        @return boolean - True if initialization succeeds
        """
        offset = 0
        input_len = len(inputstr)
        used_len = 0

        try:
            (used_len, self.ontology) = unpack_from("!v", inputstr,
                                                    offset = offset)
            offset = used_len
            if (offset > input_len):
                raise struct_error("Input string too short at ontology")

            self.ontology_data = inputstr[offset : ]

        except Exception, e:
            return False

        return self.validate()
                    
    #--------------------------------------------------------------------------#
    def validate(self):
        """
        @brief Check values and lengths are all appropriate
        @return boolean - True if validation succeeds
        """
        if not ((self.ontology == self.ONTOLOGY_URI) or
                (self.ontology == self.ONTOLOGY_JSON) or
                (self.ontology == self.ONTOLOGY_PAYLOAD_PLACEHOLDER) or
                (self.ontology == self.ONTOLOGY_JSON) or
                ((self.ontology >= self.ONTOLOGY_EXPT_MIN) and
                 (self.ontology <= self.ONTOLOGY_EXPT_MAX))):
            return False

        return True

    #--------------------------------------------------------------------------#
    def build_for_net(self):
        """
        @brief Pack instance variables into string ready for sending to net
        @return packed string or None if failure
        """
        if not self.validate():
            return None

        try:
            result = pack("!v", self.ontology) + \
                     self.ontology_data
        except Exception, e:
            return None
        
        return result
                 
    #--------------------------------------------------------------------------#
    def set_ontology(self, ontology):
        """
        @brief Set ontology field
        @param ontology integer valid value for ontology field

        @raises ValueError if not a valid value
        """
        if not ((ontology == self.ONTOLOGY_URI) or
                (ontology == self.ONTOLOGY_JSON) or
                (ontology == self.ONTOLOGY_PAYLOAD_PLACEHOLDER) or
                (ontology == self.ONTOLOGY_JSON) or
                ((ontology >= self.ONTOLOGY_EXPT_MIN) and
                 (ontology <= self.ONTOLOGY_EXPT_MAX))):
            raise ValueError
        
        self.ontology = ontology
        return         
                      
    #--------------------------------------------------------------------------#
    def set_ontology_data(self, ontology_data):
        """
        @brief Set ontology_data field
        @param ontology_data string for onteology_data field

        @raises ValueError if not a valid value
        """
        if not (ontology_data and (type(ontology_data) == StringType)):
            raise ValueError
        
        self.ontology_data = ontology_data
        
        return         
                      
    #--------------------------------------------------------------------------#
    def __repr__(self):
        """
        @brief Generate representation of Metadata
        @return string representation

        """
        return "\n".join(("ontology:       %d" % self.ontology,
                          "ontology_data:  %s" % self.ontology_data))

#==============================================================================#
# === Test code ===
if (__name__ == "__main__"):
    inst = Metadata()
    if inst.validate():
        print("Validation of empty BPQ succeeded incorrectly")
    else:
        print("Validation of empty BPQ failed as expected")

    inst.set_ontology(Metadata.ONTOLOGY_URI)
    inst.set_ontology_data("abcdefrg")

    if not inst.validate():
        print("Validation of loaded BPQ failed incorrectly")
    else:
        print("Validation of loaded BPQ succeeded as expected")

    s = inst.build_for_net()
    if s is None:
        print("Building of net string failed")
    inst2 = Metadata()
    res = inst2.init_from_net(s)
    if res:
        print inst2
    else:
        print("Decoding failed unexpectedly")

