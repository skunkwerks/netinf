#!/usr/bin/python
"""
@package nilib
@file nidtnbpq.py
@brief Encode and decode routines for RFC 5050 Bundle Protocol BPQ blocks.
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
Uses nistruct to encode and decode DTN Bundle Protocol BPQ blocks between
a dictionary and a string.

Elements of BPQ block on the wire:
Name          Type               Description
bpq_kind      1 octet integer    Describes type of BPQ block
matching_rule 1 octet integer    Identifies matching rule to be used
creation_ts   SDNV               Seconds since epoch when bundle created
creation_seq  SDNV               Sequence number in creating node
src_eid_len   SDNV               Length of Source EID string
src_eid       string             Source EID (length as per src_eid_len)
bpq_id_len    SDNV               Length of BPQ ID string
bpq_id        string             BPQ ID (message id - length as per bpq_id_len)
bpq_val_len   SDNV               Length of BPQ Value string
bpq_val       string             BPQ Value (length as per bpq_val_len)
frag_cnt      SDNV               Number of fragment descriptors following

Per fragment:
frag_desc:
- frag_offset SDNV               Offset of fragment in bundle payload
- frag_len    SDNV               Length of fragment of payload
@code
Revision History
================
Version   Date	     Author	    Notes
1.0	  31/12/2012 ElwynDavies    Created.

@endcode
"""

#==============================================================================#
# Standard modules

# Nilib modules
from _nistruct import pack, pack_into, unpack, unpack_from, struct_error

#==============================================================================#

class BPQ:
    """
    @brief Encapsulation for a RFC 5050 BPQ block

    @detail
    Holds details for a single BPQ block, providing validation, decoding
    from an on-the-wire string and generation of the on-the-wire string.

    """
    #--------------------------------------------------------------------------#
    # CONSTANT VALUES USED BY CLASS

    # --- bpq_kind values ---

    ##@var BPQ_BLOCK_KIND_QUERY
    # integer   Value of bpq_kind for query blocks
    BPQ_BLOCK_KIND_QUERY = 0x00
    ##@var BPQ_BLOCK_KIND_RESPONSE
    # integer   Value of bpq_kind for response blocks
    BPQ_BLOCK_KIND_RESPONSE = 0x01
    ##@var BPQ_BLOCK_KIND_RESPONSE_DO_NOT_CACHE_FRAG
    # integer   Value of bpq_kind for response blocks where recipients are
    #           requested only to cache complete bundles rather than fragments
    BPQ_BLOCK_KIND_RESPONSE_DO_NOT_CACHE_FRAG = 0x02
    ##@var BPQ_BLOCK_KIND_PUBLISH
    # integer   Value of bpq_kind for publish blocks
    BPQ_BLOCK_KIND_PUBLISH = 0x03

    # --- matching_rule values ---

    ##@var BPQ_MATCHING_RULE_EXACT
    # integer   Value of matching_rule when the query ID has to match exactly.
    BPQ_MATCHING_RULE_EXACT = 0x00
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var bpq_kind
    # integer    Describes type of BPQ block
    ##@var matching_rule
    # integer    Identifies matching rule to be used
    ##@var creation_ts
    # integer    Seconds since epoch when bundle created
    ##@var creation_seq
    # integer    Sequence number in creating node
    ##@var src_eid_len
    # integer    Length of Source EID string
    ##@var src_eid
    # string     Source EID (length as per src_eid_len)
    ##@var bpq_id_len
    # integer    Length of BPQ ID string
    ##@var bpq_id
    # string     BPQ ID (message id - length as per bpq_id_len)
    ##@var bpq_val_len
    # integer    Length of BPQ Value string
    ##@var bpq_val
    # string     BPQ Value (length as per bpq_val_len)
    ##@var frag_cnt
    # integer    Number of fragment descriptors following

    ##@var frag_desc
    # Array of dictionaries each with:
    # - frag_offset integer   Offset of fragment in bundle payload
    # - frag_len    integer   Length of fragment of payload
    
    #--------------------------------------------------------------------------#
    def __init__(self):
        """
        @brief Constructor - set default values
        """
        # The bpq_kind and matching_rule are deliberately set illegal
        self.bpq_kind = -1
        self.matching_rule = -1
        self.creation_ts = 0
        self.creation_seq = 0
        self.src_eid_len = 0
        self.src_eid = None
        self.bpq_id_len = 0
        self.bpq_id = None
        self.bpq_val_len = 0
        self.bpq_val = None
        self.frag_cnt = 0
        self.frag_desc = []
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
            (used_len, self.bpq_kind, self.matching_rule,
             self.creation_ts, self.creation_seq,
             self.src_eid_len) = unpack_from("!BBvvv", inputstr,
                                             offset = offset)
            offset = used_len
            if ((offset + self.src_eid_len) > input_len):
                raise struct_error("Input string too short at src_eid")

            self.src_eid = inputstr[offset : (offset + self.src_eid_len)]

            offset += self.src_eid_len
            (used_len, self.bpq_id_len) = unpack_from("!v", inputstr,
                                                      offset = offset)
            offset += used_len
            if ((offset + self.bpq_id_len) > input_len):
                raise struct_error("Input string too short at bpq_id")

            self.bpq_id = inputstr[offset : (offset + self.bpq_id_len)]

            offset += self.bpq_id_len
            (used_len, self.bpq_val_len) = unpack_from("!v", inputstr,
                                                       offset = offset)
            
            offset += used_len
            if ((offset + self.bpq_val_len) > input_len):
                raise struct_error("Input string too short at bpq_va;")

            self.bpq_val = inputstr[offset : (offset + self.bpq_val_len)]

            offset += self.bpq_val_len
            (used_len, self.frag_cnt) = unpack_from("!v", inputstr,
                                                    offset = offset)
            offset += used_len

            self.frag_desc = []

            if self.frag_cnt > 0:
                fmt_str = "!" + ("vv" * self.frag_cnt)
                frag_tuple = unpack_from(fmt_str, inputstr, offset = offset)
                offset += frag_tuple[0]
                i = 0
                j = 1
                while (i < self.frag_cnt):
                    d = {}
                    d["frag_offset"] = frag_tuple[j]
                    j += 1
                    d["frag_len"] = frag_tuple[j]
                    j += 1
                    self.frag_desc.append(d)
                    i += 1
            if (offset != input_len):
                raise struct_error("Input string is wrong length")
        except Exception, e:
            return False

        return self.validate()
                    
    #--------------------------------------------------------------------------#
    def validate(self):
        """
        @brief Check values and lengths are all appropriate
        @return boolean - True if validation succeeds
        """
        if not ((self.bpq_kind == self.BPQ_BLOCK_KIND_QUERY) or
                (self.bpq_kind == self.BPQ_BLOCK_KIND_RESPONSE) or
                (self.bpq_kind == self.BPQ_BLOCK_KIND_RESPONSE_DO_NOT_CACHE_FRAG) or
                (self.bpq_kind == self.BPQ_BLOCK_KIND_PUBLISH)):
            return False

        if not ((self.matching_rule == self.BPQ_MATCHING_RULE_EXACT)):
            return False

        if not (self.src_eid and (len(self.src_eid) == self.src_eid_len)):
            return False

        if not (self.bpq_id and (len(self.bpq_id) == self.bpq_id_len)):
            return False

        if not (self.bpq_val and (len(self.bpq_val) == self.bpq_val_len)):
            return False

        if not (self.frag_cnt == len(self.frag_desc)):
            return False

        for d in self.frag_desc:
            if not (d.has_key("frag_offset") and d.has_key("frag_len")):
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
            result = pack("!BBvvv", self.bpq_kind, self.matching_rule,
                          self.creation_ts, self.creation_seq, self.src_eid_len) + \
                     self.src_eid + \
                     pack("!v", self.bpq_id_len) + \
                     self.bpq_id + \
                     pack("!v", self.bpq_val_len) + \
                     self.bpq_val + \
                     pack("!v", self.frag_cnt) + \
                     "".join(map(lambda d : pack("!vv",
                                                 d["frag_offset"],
                                                 d["frag_len"]), self.frag_desc))
        except Exception, e:
            return None
        
        return result
                 
    #--------------------------------------------------------------------------#
    def set_bpq_kind(self, bpq_kind):
        """
        @brief Set bpq_kind field
        @param bpq_kind integer valid value for bpq_kind field

        @raises ValueError if not a valid value
        """
        if not ((bpq_kind == self.BPQ_BLOCK_KIND_QUERY) or
                (bpq_kind == self.BPQ_BLOCK_KIND_RESPONSE) or
                (bpq_kind == self.BPQ_BLOCK_KIND_RESPONSE_DO_NOT_CACHE_FRAG) or
                (bpq_kind == self.BPQ_BLOCK_KIND_PUBLISH)):
            raise ValueError
        
        self.bpq_kind = bpq_kind
        return         
                      
    #--------------------------------------------------------------------------#
    def set_matching_rule(self, matching_rule):
        """
        @brief Set matching_rule field
        @param matching_rule integer valid value for matching_rule field

        @raises ValueError if not a valid value
        """
        if not ((matching_rule == self.BPQ_MATCHING_RULE_EXACT)):
            raise ValueError
        
        self.matching_rule = matching_rule
        return         
                      
    #--------------------------------------------------------------------------#
    def set_creation_info(self, creation_ts, creation_seq):
        """
        @brief Set creation_ts and creation_seq fields
        @param creation_ts integer timestamp in seconds - must be positive
        @param creation_seq integer sequence serial number at source - must
                                    be positive

        @raises ValueError if not a valid value
        """
        if not (creation_ts and (creation_ts > 0) and
                creation_seq and (creation_seq > 0)):
            raise ValueError
        
        self.creation_ts = creation_ts
        self.creation_seq = creation_seq
        
        return         
                      
    #--------------------------------------------------------------------------#
    def set_src_eid(self, src_eid):
        """
        @brief Set src_eid and src_eid_len fields
        @param src_eid string for source EID

        @raises ValueError if not a valid value
        """
        if not (src_eid and (len(src_eid) > 0)):
            raise ValueError
        
        self.src_eid = src_eid
        self.src_eid_len = len(src_eid)
        
        return         
                      
    #--------------------------------------------------------------------------#
    def set_bpq_id(self, bpq_id):
        """
        @brief Set bpq_id and bpq_id_len fields
        @param bpq_id string for BPQ ID

        @raises ValueError if not a valid value
        """
        if not (bpq_id and (len(bpq_id) > 0)):
            raise ValueError
        
        self.bpq_id = bpq_id
        self.bpq_id_len = len(bpq_id)
        
        return         
                      
    #--------------------------------------------------------------------------#
    def set_bpq_val(self, bpq_val):
        """
        @brief Set bpq_val and bpq_val_len fields
        @param bpq_val string for BPQ Value

        @raises ValueError if not a valid value
        """
        if not (bpq_val and (len(bpq_val) > 0)):
            raise ValueError
        
        self.bpq_val = bpq_val
        self.bpq_val_len = len(bpq_val)
        
        return         
                      
    #--------------------------------------------------------------------------#
    def add_frag_desc(self, frag_offset, frag_len):
        """
        @brief Add a new entry to the end of the frag_desc list
        @param frag_offset integer positive value of fragment offset
        @param frag_len integer positive length of fragment

        @raises ValueError if not a valid value
        """
        if not (frag_offset is not None and (frag_offset >= 0) and
                frag_len is not None and (frag_len > 0)):
            raise ValueError
        
        d = {}
        d["frag_offset"] = frag_offset
        d["frag_len"] = frag_len
        self.frag_desc.append(d)
        self.frag_cnt += 1
        
        return         

    #--------------------------------------------------------------------------#
    def __repr__(self):
        """
        @brief Generate representation of BPQ
        @return string representation

        @raises ValueError if not a valid value
        """
        return "\n".join(("bpq_kind:       %d" % self.bpq_kind,
                          "matching_rule:  %d" % self.matching_rule,
                          "creation_ts:    %d" % self.creation_ts,
                          "creation_eq:    %d" % self.creation_seq,
                          "src_eid_len:    %d" % self.src_eid_len,
                          "src_eid:        %s" % self.src_eid,
                          "bpq_id_len:     %d" % self.bpq_id_len,
                          "bpq_id:         %s" % self.bpq_id,
                          "bpq_val_len:    %d" % self.bpq_val_len,
                          "bpq_val:        %s" % self.bpq_val,
                          "frag_cnt:       %s\n" %self.frag_cnt)) + \
                "".join(map(lambda d : "offset: %d, length: %d\n" % (d["frag_offset"],
                                                                   d["frag_len"]),
                            self.frag_desc))

#==============================================================================#
# === Test code ===
if (__name__ == "__main__"):
    inst = BPQ()
    if inst.validate():
        print("Validation of empty BPQ succeeded incorrectly")
    else:
        print("Validation of empty BPQ failed as expected")

    inst.set_bpq_kind(BPQ.BPQ_BLOCK_KIND_PUBLISH)
    inst.set_matching_rule(BPQ.BPQ_MATCHING_RULE_EXACT)
    inst.set_creation_info(12345678, 765432)
    inst.set_src_eid("dtn://example.com.dtn/example")
    inst.set_bpq_id("random_msg")
    inst.set_bpq_val("ni:///sha-256-32;afghjk")
    inst.add_frag_desc(0, 15)
    inst.add_frag_desc(2980, 741)
    inst.add_frag_desc(3897, 65)

    if not inst.validate():
        print("Validation of loaded BPQ failed incorrectly")
    else:
        print("Validation of loaded BPQ succeeded as expected")

    s = inst.build_for_net()
    if s is None:
        print("Building of net string failed")
    inst2 = BPQ()
    res = inst2.init_from_net(s)
    if res:
        print inst2
    else:
        print("Decoding failed unexpectedly")

    
        
            

    
        
        
    
