#!/usr/bin/python
"""
@package nilib
@file metadata.py
@brief Metadata manager class for NDOs cached by nilib infrastructure
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
Class for building and holding the metadata of a Named Data Object in memory.

================================================================================
@code
Revision History
================
Version   Date       Author         Notes
1.2       10/01/2013 Elwyn Davies   Add routine to internal JSON from incoming
                                    GET-RESP JSON object.
1.1       04/12/2012 Elwyn Davies   Add merge_latest_details. Change so that
                                    local host URL is added to summary rather
                                    than in initial metadata to avoid creating
                                    multiple instances when metadata is updated
                                    by new cache mechanism - remove myloc from
                                    __init__ and append_locs
1.0       30/11/2012 Elwyn Davies   Move version string to netinf_ver.py.
0.0       21/10/2012 Elwyn Davies   Factored out of nilib.
@endcode
"""

import json
from types import *
import datetime

#=== Local package modules ===

from netinf_ver import NETINF_VER
from ni import NIname, ni_errs, ni_errs_txt
from ni_exception import InvalidNIname, MetadataMismatch

#==============================================================================#
# List of classes/global functions in file
__all__ = ['NetInfMetaData']

#==============================================================================#
# GLOBAL VARIABLES


#==============================================================================#
class NetInfMetaData:
    """
    @brief Class holding the data from a metadata file.
    The metadata file holds a serialized version of a JSON object that is
    read/written to the json_obj held in the class.

    The structure of the JSON object is:
    - NetInf    Version string for NetInf specification applied
    - ni        ni[h] name of NDO to which metadata applies
    - ct        MIME content type of NDO (if known)
    - size      Length of content in octets or -1 if not known
    - details   Array of JSON objects containing:
       - ts         UTC timestamp for object, format "%y-%m-%dT%H:%M:%S+00:00"
       - metadata   JSON object with arbitrary contents
       - loc        Array of locators for this NDO
       - publish    Information about how this was published - string or object
       - search     JSON object describing search that flagged this NDO with
          - searcher    The system that did the search (e.g., this code)
          - engine      The search engine used to perform the search
          - tokens      The search query run by the engine to flag this NDO

    The initial entries are made when an instance is first created.
    Subsequent 'details' entries are added whenever the metadata is updated.
    The content type may not be known on initial creation if the publisher
    only sent metadata.  It may be updated later if the content is added to
    the cache together with the size of the object.

    The instance variable curr_detail holds the most recent details item
    at all times.
    """

    #--------------------------------------------------------------------------#
    # CONSTANT VALUES USED BY CLASS
    
    ##@var METADATA_TIMESTAMP_TEMPLATE
    # Template as used by datetime strftime for timestanps in metadata files
    METADATA_TIMESTAMP_TEMPLATE = "%y-%m-%dT%H:%M:%S+00:00"
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var json_obj
    # A JSON object holding the representation of the metadata.

    ##@var curr_detail
    # The most recent (last) JSON object in the array of "details" objects

    #--------------------------------------------------------------------------#
    @classmethod
    def metadata_timestamp_for_now(cls):
        """
        @brief Format timestamp recording time 'now' as string for metadata files.
        @return string with formatted timestamp for time at this instant
                as expressed using UTC time.
        """
        return datetime.datetime.utcnow().strftime(NetInfMetaData.METADATA_TIMESTAMP_TEMPLATE)

    #--------------------------------------------------------------------------#
    def __init__(self, ni_uri="", timestamp=None, ctype=None, file_len=-1,
                 loc1=None, loc2=None, extrameta=None):
        """
        @brief Create a new metadata object from parameters
        
        If all the parameters are omitted an empty object will be created
        that can be populated from a file using the 'set_json_val' method.
        @param ni_uri string The ni[h]: name to which the metadata applies
        @param timestamp string initial creation timestamp (format: see class header)
        @param ctype string MIME type of NDO (may be empty string if not yet known)
        @param file_len integer Length of content in octets or -1 if not yet known
        @param loc1 string locator for NDO or None
        @param loc2 string locator for NDO or None
        @param extrameta dictionary JSON object with other objects for 'details'

        Creates JSON dictionary for json_obj with initial 'details' object 
        """
        self.json_obj = {}
        self.json_obj["NetInf"] = NETINF_VER
        self.json_obj["ni"]     = ni_uri
        if ctype is None:
            self.json_obj["ct"] = ""
        else:
            self.json_obj["ct"] = ctype
        self.json_obj["size"] = file_len
        self.json_obj["details"] = []
        self.add_new_details(timestamp, loc1, loc2, extrameta)
        return
    
    #--------------------------------------------------------------------------#
    def add_new_details(self, timestamp, loc1, loc2, extrameta):
        """
        @brief Append a new details entry to the array of objects

        @param timestamp string initial creation timestamp (format: see class header)
        @param ctype string MIME type of NDO (may be empty string if not yet known)
        @param loc1 string locator for NDO
        @param loc2 string locator for NDO
        @param extrameta dictionary JSON object with other objects for 'details'
        @return dictionary with new details

        Creates JSON object dictionary to append to 'details' array from
        parameters:
        - The timestamp is used directly via set_timestamp
        - The parameters myloc, loc1, and loc2 are added to loclist if not None
        - All the key-value pairs in extrameta are copied to 'metadata'

        Reset the curr_detail instance object to point to new detail item.

        Note: we assume that the 'details' are in timestamp order, i.e., that
        added details entries have later timestamps.  This is not currently
        checked and might look odd if the system clock is rest backwards.
        It doesn't have any significant effect since the output from this
        object is generally the summary or bits of the most recently added
        entry - the timestamp is just for convenience.
        """
        
        self.curr_detail = {}
        self.json_obj["details"].append(self.curr_detail)
        self.set_timestamp(timestamp)
        self.append_locs(loc1, loc2)
        metadata = {}
        self.curr_detail["metadata"] = metadata
        
        if extrameta != None:
            try:
                for k in extrameta.keys():
                    metadata[k] = extrameta[k]
            except AttributeError, e:
                print("Error: extrameta not a dictionary (%s)" % type(extrameta))
                pass
        return self.curr_detail

    #--------------------------------------------------------------------------#
    def merge_latest_details(self, metadata_with_extra):
        """
        @brief Copy curr_detail entry from parameter to this instance
        @param metadata_with_extra NetInfMetdata instance with details to copy
        @return boolean True if two instances have matching ni field with size
                             and content type consistent

        Check for consistency.
        Add curr_detail from metadata_with_extra to this metadata and
        set ctype and size in this metadata if present in metadata_with extra
        """
        if self.json_obj["ni"] != metadata_with_extra.json_obj["ni"]:
            return False
        my_ct = self.get_ctype()
        xtra_ct = metadata_with_extra.get_ctype()
        
        if (my_ct != "") and (xtra_ct != ""):
            if my_ct != xtra_ct:
                return False
        my_size = self.get_size()
        xtra_size = metadata_with_extra.get_size()
        if (my_size != (-1)) and (xtra_size != (-1)):
            if my_size != xtra_size:
                return False
        self.curr_detail = metadata_with_extra.curr_detail
        self.json_obj["details"].append(self.curr_detail)
        if xtra_ct != "":
            self.set_ctype(xtra_ct)
        if xtra_size != (-1):
            self.set_size(xtra_size)
        return True
    
    #--------------------------------------------------------------------------#
    def json_val(self):
        """
        @brief Access JSON object representing metadata as Python dictionary
        @return json_obj
        """
        return self.json_obj
    
    #--------------------------------------------------------------------------#
    def set_json_val(self, json_val):
        """
        @brief Set json_obj to a dictionary typically derived from
        @brief an NDO metadata file
        @param json_val dictionary JSON object in correct form
        @return booleans indicating if load was successful

        Currently the format of the dictionary is not checked,
        but we do check that the "NetInf" entry matches with
        the current NETINF_VER string.
        TO DO: add more checking and deal with backwards compatibility.

        The curr_detail instance variable is set to the last
        item in the 'details' array.
        """
        if json_val["NetInf"] != NETINF_VER:
            return False
        self.json_obj = json_val
        # Set the current details to be the last entry
        self.curr_detail = self.json_obj["details"][-1]
        return True

    #--------------------------------------------------------------------------#
    def append_locs(self, loc1=None, loc2=None):
        """
        @brief Build loclist array from parameters
        @param loc1 string locator for NDO
        @param loc2 string locator for NDO
        @return (none)

        Build 'loc' array of strings and put into 'curr_detail'
        object dictionary.  The parameters are only added to the
        list if they are not None and not the empty string.
        """
        loclist = []
        self.curr_detail["loc"] = loclist
        if loc1 is not None and loc1 is not "":
            if not loc1 in loclist: 
                loclist.append(loc1)
        if loc2 is not None and loc2 is not "":
            if not loc2 in loclist: 
                loclist.append(loc2)
        return
    
    #--------------------------------------------------------------------------#
    def get_ni(self):
        """
        @brief Accessor for NDO ni name in metadata
        @retval string Value of "ni" item in json_obj.
        """
        return self.json_obj["ni"]
    
    #--------------------------------------------------------------------------#
    def get_timestamp(self):
        """
        @brief Accessor for NDO most recent update timestamp
        @retval string Value of "ts" item in curr_detail.

        For format of timestamp see class header
        """
        return self.curr_detail["ts"]

    #--------------------------------------------------------------------------#
    def set_timestamp(self, timestamp):
        """
        @brief Set the timestamp item ("ts") in curr_detail
        @param string timestamp (for format see class header)
        @return (none)
        """
        if timestamp is None:
            self.curr_detail["ts"] = "(unknown)"
        else:
            self.curr_detail["ts"] = timestamp
        return

    #--------------------------------------------------------------------------#
    def get_ctype(self):
        """
        @brief Accessor for NDO content type in metadata
        @retval string Value of "ct" item in json_obj.
        """
        return self.json_obj["ct"]

    #--------------------------------------------------------------------------#
    def set_ctype(self, ctype):
        """
        @brief Set the content type item ("ct") in json_obj.
        @param ctype string MIME content type for NDO
        @return (none)

        Setting is skipped if parameter is None.
        """
        if ctype is not None:
            self.json_obj["ct"] = ctype
        return

    #--------------------------------------------------------------------------#
    def get_size(self):
        """
        @brief Accessor for NDO content file size in metadata
        @retval integer Value of "size" item in json_obj.
        """
        return self.json_obj["size"]

    #--------------------------------------------------------------------------#
    def set_size(self, file_len):
        """
        @brief Set the content file size item ("size") in json_obj.
        @param file_len integer content file size for NDO in octets
        @return (none)

        Setting is skipped if parameter is None.
        """
        if file_len is not None:
            self.json_obj["size"] = file_len
        return

    #--------------------------------------------------------------------------#
    def get_loclist(self):
        """
        @brief Scan all the details entries and get the set of all
        @brief distinct entries in loc entries
        @retval array of strings set of all different locators from "details" entries
        """
        loclist = []
        for d in self.json_obj["details"]:
            for l in d["loc"]:
                if not l in loclist:
                    loclist.append(l)
        #print("Summarized loclist: %s" % str(loclist))
        
        return loclist
        
    #--------------------------------------------------------------------------#
    def get_metadata(self):
        """
        @brief Scan all the details entry and get the set of all
        @brief distinct entries in metadata entries
        @retval 2-tuple: dictionary JSON object with summary of metadata,
                         array of searches

        Scan the 'metadata' entries from the objects in the
        'details' array to create a summary object from all the entries.

        For every different key found in the various 'metadata' objects,
        copy the key-value pair into the summary, except for the
        'search' keys.

        Treat 'search' key specially - combine the values from any
        search keys recorded into an array, omitting duplicates.
        Search key values are deemed to be duplicates if they have the
        same 'engine' and 'tokens' key values (i.e., the 'searcher' key
        value is ignored for comparison purposes).  Write the resulting
        array as the value of the 'searches' key in the summary object.

        For other keys, if their are duplicates, just take the most
        recently recorded one (they are recorded in time order)
        """
        metadict = {}
        srchlist = []
        n = -1
        for d in self.json_obj["details"]:
            curr_meta = d["metadata"]
            n += 1
            for k in curr_meta.keys():
                if k == "search":
                    se = curr_meta[k]
                    if type(se) == DictType:
                        se = [ se ]
                    # In case somebody put in a non-standard search entry
                    for sem in se:
                        try:
                            eng = sem["engine"]
                            tok = sem["tokens"]
                            dup = False
                            for s in srchlist:
                                if ((s["engine"] == eng) and (s["tokens"] == tok)):
                                    dup = True
                                    break
                            if not dup:
                                srchlist.append(sem)
                        except:
                            # Non-standard search entry - leave it in place
                            metadict[k] = curr_meta[k]
                else:
                    metadict[k] = curr_meta[k]
        if len(srchlist) == 0:
            srchlist = None
            
        #print("Summarized metadata: %s" % str(metadict))
        
        return (metadict, srchlist)

    #--------------------------------------------------------------------------#
    def summary(self, myloc):
        """
        @brief Generate a JSON object dictionary containing summarized metadata.
        @param myloc string locator derived from authority in ni name (i.e., local server)
        @retval dictionary JSON object containing summarized data

        The summary JSON object dictionary contains:
        - the 'NetInf', 'ni', 'ct' and 'size' entries copied from json_obj
        - the timestamp 'ts' from the most recent (last element) of the 'details'
        - the summarized locator list 'loclist' derived by get_loclist with
          myloc added
        - the summarized 'metadata' object derived by get_metadata.
        """
        sd = {}
        for k in ["NetInf", "ni"]:
            sd[k] = self.json_obj[k]
        if self.json_obj["ct"] != "":
            sd["ct"] = self.json_obj["ct"]
        if self.json_obj["size"] != -1:
            sd["size"] = self.json_obj["size"]
        sd["ts"] = self.get_timestamp()
        sd["loclist"] = self.get_loclist()
        if myloc is not None:
            sd["loclist"].append(myloc)
        sd["metadata"], srchlist = self.get_metadata()
        if srchlist != None:
            sd["searches"] = srchlist
        return sd

    #--------------------------------------------------------------------------#
    def insert_resp_metadata(self, response):
        """
        @brief Insert metadata from GET-RESP message into internal form.
        @param response Either JSON format dict or JSON format string
                        in format of of GET-RESP metadata.
        @retval None.

        The response is converted to a JSON dictionary and/or checked
        to verify that it is in good shape.

        Can be used either with an 'empty' NetInfMetaData instance
        identified by the 'ni' field being the empty string or with
        a previously populated entry.

        For an empty instance, the header fields ('ni', 'ct' and 'size')
        are populated from the response where possible (may be no 'ct' or 'size'
        in the response).

        The remainder of the information is converted into a new 'details'
        entry which is either used as the first entry or appended to the
        list if there are existing entries.
        
        @raises Exceptions if cannot parse response
        """

        if type(response) == StringType:
            resp_dict = json.loads(response)
        elif type(response) == DictType:
            resp_dict = response
            # Check the response is really a JSON dictionary
            js = json.dumps(response)
        else:
            raise TypeError("Parameter 'response' is not a string or dictionary")

        curr_ni = self.get_ni()
        if curr_ni == "" :
            # Empty metadata case
            # Validate the "ni" field
            curr_ni = resp_dict["ni"]
            ni_name = NIname(curr_ni)
            ret = ni_name.validate_ni_url()
            if ret != ni_errs.niSUCCESS:
                raise InvalidNIname(ni_errs_txt[ret])
            self.json_obj["ni"] = resp_dict["ni"]
            if resp_dict.has_key("ct"):
                self.json_obj["ct"] = resp_dict["ct"]
            if resp_dict.has_key("size"):
                self.json_obj["size"] = resp_dict["size"]
            self.json_obj["details"] = []
        elif curr_ni == resp_dict["ni"]:
            # Update with data about same ni name
            if resp_dict.has_key("ct") and (resp_dict["ct"] != ""):
                if self.json_obj["ct"] == "":
                    self.json_obj["ct"] = resp_dict["ct"]
                elif self.json_obj["ct"] != resp_dict["ct"]:
                    raise MetadataMismatch("Content Type fields are unmatched")
            if resp_dict.has_key("size") and (resp_dict["size"] >= 0):
                if self.json_obj["size"] == -1:
                    self.json_obj["size"] = resp_dict["size"]
                elif self.json_obj["size"] != resp_dict["size"]:
                    raise MetadataMismatch("Size fields are unmatched")
        else:
            raise MetadataMismatch("NI name fields are unmatched")

        new_detail = {}
        for loc_key in ("loc", "loclist"):
            if resp_dict.has_key(loc_key):
                if type(resp_dict[loc_key]) == ListType:
                    new_detail["loc"] = resp_dict[loc_key]
                else:
                    raise TypeError("Response '%s' value is not a list" % loc_key)
                
        if resp_dict.has_key("metadata"):
            if type(resp_dict["metadata"]) == DictType:
                new_detail["metadata"] = resp_dict["metadata"]
            else:
                raise TypeError("Response metadata is not an object dictionary")


        if resp_dict.has_key("searches"):
            if not new_detail.has_key("metadata"):
                new_detail["metadata"] = {}
            new_detail["metadata"]["search"] = resp_dict["searches"]

        new_detail["ts"] = self.metadata_timestamp_for_now()
        
        self.json_obj["details"].append(new_detail)
        self.curr_detail = new_detail
        return 
        
    #--------------------------------------------------------------------------#
    def __repr__(self):
        """
        @brief Output compact string representation of json_obj.
        @retval string JSON dump of json_obj in maximally compact form.
        """
        return json.dumps(self.json_obj, separators=(',',':'))
        
    #--------------------------------------------------------------------------#
    def __str__(self):
        """
        @brief Output pretty printed string representation of json_obj.
        @retval string JSON dump of json_obj with keys sorted and indent 4.
        """
        return json.dumps(self.json_obj, sort_keys = True, indent = 4)

#==============================================================================#
# === Test Code ===
if __name__ == "__main__" :
    # Test insert_resp_metadata
    ni_name = "ni:///sha-256-32;abcd12"
    resp = { "ni": ni_name, "ct": "text/plain", "size": 23,
             "loclist": [ "abcde", "xyzdr", "dfgsh"],
             "metadata": { "publish": "Python" },
             "searches": [ {"engine": "wikipedia",
                            "tokens": "cabbage",
                            "searcher": "Python"}
                         ]
             }
    md = NetInfMetaData()
    md.insert_resp_metadata(resp)

    print md
    print md.summary("me.here")

    resp["loclist"] = [ "rtfm", "bummer", "stuff", "nonsense"]
    md.insert_resp_metadata(resp)

    print md
    print md.summary("me.here")

    resp["ni"] = "ni:///sha-256-32;abcd23"
    try:
        md.insert_resp_metadata(resp)
        print "Fault: Bad response not detected"
    except Exception, e:
        print "Bad response correctly detected: %s" % str(e)

    resp["ni"] = ni_name
    resp["size"] = 57
    try:
        md.insert_resp_metadata(resp)
        print "Fault: Bad response not detected"
    except Exception, e:
        print "Bad response correctly detected: %s" % str(e)

    resp["size"] = 23
    resp["ct"] = "application/json"
    try:
        md.insert_resp_metadata(resp)
        print "Fault: Bad response not detected"
    except Exception, e:
        print "Bad response correctly detected: %s" % str(e)

    resp["ni"] = "zzzz"
    me = NetInfMetaData()
    try:
        me.insert_resp_metadata(resp)
        print "Fault: Bad ni not detected"
    except Exception, e:
        print "Bad ni correctly detected: %s" % str(e)

    resp["ni"] = ni_name
    resp["ct"] = ""
    resp["size"] = -1
    me = NetInfMetaData()
    me.insert_resp_metadata(resp)
    print me
    print me.summary("somewhere.else")

    resp["ct"] = "text/html"
    resp["size"] = 34
    me.insert_resp_metadata(resp)
    print me
    print me.summary("not.here")
    
    

        
    
