#!/usr/bin/python
"""
@package ni
@file ni.py
@brief This is the external interface for the NI URI handling library
@version $Revision: 0.2 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin

    This is the NI URI library developed as
    part of the SAIL project. (http://sail-project.eu)

    Specification(s) - note, versions may change
            http://tools.ietf.org/html/farrell-decade-ni-00
            http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00

Copyright 2012 Trinity College Dublin

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
 
import base64
import hashlib
import array
import re
from exceptions import *
import ni_urlparse
from encode import ParamDigester
from stdnum import luhn

def debug(string):
    """
    @brief Print out debugging information string
    @param string to be printed (in)
    """
    #print string
    return

class _Enum(set):
    """
    @brief Class to support pseudo-enums in Python subclassed from set
    The constructor for the enum is supplied with a list of strings.
    The strings are used to initialize the underlying set.
    The implementation of __getattr__ allows the text of each string
    to be used as an attribute, returning a string that is just the
    original defining string (wow!).. thus
    enum = _Enum([ "a", "b" ])
    val = enum.a
    print val, type(val) outputs --> a, <type 'str'>
    """
    def __getattr__(self, name):
        """
        @brief override standard object method to access items in set as attributes
        @param name - item in enum to access (in)
        @return string with value equal to parameter name or raise AttributeError if name not in set
        """
        if name in self:
            return name
        raise AttributeError

## ni_errs Error codes for NI operations
# @brief Enumeration of possible return codes from NI class functions.
#
# niSUCCESS       Function was successful.
#
# niBADALG        The ni name supplied either didn't contain a recognizable hash
#                 algorithm identifier or the name was for an algorithm that we
#                 don't implement.  The name has to be at an appropriate point 
#                 in the ni name URL: viz.
#                  -  as the file part of the URL (last component of URL path -
#                     i.e. segment after netloc, followed by parameter
#                     introducer (;),
#                     e.g., ni://folly.org.uk/sha-256;gfsghfa...  ; or
#                  -  as the next hierarchical component in path after a
#                     '.well-known/ni' component of an http: transform of the ni:,
#                     e.g., http://folly.org.uk/.well-known/ni/sha-256/gadaasd...
#                 In each case the next segment of the name would be the
#                 hash digest(either as the path params (first case) or
#                 the next lower level in the path hierarchy (second case).
#
# niBADFILE       The content file name supplied cannot be found or cannot be read.
#
# niBADHASH       The digest in the supplied URL does not match the digest 
#                 calculated from the file.
#
# niHASHTOOLONG   The digest in the supplied URL is longer than the length of the
#                 digest according to the selected hash algorithm.
#
# niHASHFAIL      The output from the hashlib function has an unexpected length.
#
# niBADSCHEME     Scheme specifier in URL is not ni:
#
# niBADURL        Other problem with URL format (non-empty path, params non-empty
#                 in template URL or empty i non-template URL).
#
ni_errs = _Enum(["niSUCCESS", "niBADALG", "niBADFILE",
                 "niBADHASH", "niHASHTOOLONG", "niHASHFAIL",
                 "niBADSCHEME", "niBADPARAMS", "niNOFRAG",
                 "niNOAUTHORITY", "niNOQUERY", "niBADURL"])


## @brief ni_errs_txt - Dictionary with textual error strings corresponding to error texts.
ni_errs_txt = { ni_errs.niSUCCESS:      "Successful",
                ni_errs.niBADALG:       "Name does not contain recognized hash algorithm selector",
                ni_errs.niBADFILE:      "Unable to open content file",
                ni_errs.niBADHASH:      "Hash code in name does not match hash code of content",
                ni_errs.niHASHTOOLONG:  "Hash code in name is longer than it should be",
                ni_errs.niHASHFAIL:     "Hashlib output has unexpected length",
                ni_errs.niBADSCHEME:    "Scheme in URL is not ni: or nih:",
                ni_errs.niBADPARAMS:    "Params part of URL is wrong length or bad format",
                ni_errs.niNOFRAG:       "Name contains a fragment component - not allowed",
                ni_errs.niNOAUTHORITY:  "Names in nih scheme should not have authority",
                ni_errs.niNOQUERY:      "Names in nih scheme should not have query",
                ni_errs.niBADURL:       "URL is not in expected form"}


class NIname:
    """
    @brief Encapsulation for an ni: name
    Uses ni_urlparse to dismantle URL

    Note that constructor does not validate URL - user must call
    validate_ni_url before attempting to retrieve hash algorithm info
    """

    ## @brief The class variable hash_algs is a dictionary specifying possible digest algs.
    #
    # The entries are keyed by the name of the hash algorithm which will be in the
    # file part of the ni: scheme URL.
    # The value for each entry is a 5-tuple containing:
    # - a callable for the constructor of the appropriate hash digest class
    # - the length of resulting binary digest in octets
    # - the length to which the binary digest should be truncated in octets
    # - the length of the base64url encoded digest
    # - the suite numbered registered for this encoding - None if there isn't one
    
    hash_algs = { "sha-256-32" : (hashlib.sha256, 32,  4,  6, 6),
                  "sha-256-64" : (hashlib.sha256, 32,  8, 11, 5),
                  "sha-256-96" : (hashlib.sha256, 32, 12, 16, 4),
                  "sha-256-120": (hashlib.sha256, 32, 15, 20, 3),
                  "sha-256-128": (hashlib.sha256, 32, 16, 22, 2),
                  "sha-256"    : (hashlib.sha256, 32, 32, 43, 1) }

    ## @brief Index for NI.hash_algs value tuples.
    #
    # Hashlib hashing function
    AF = 0
    ## @brief Index for NI.hash_algs value tuples.
    #
    # Hash function output length
    HL = 1
    ## @brief Index for NI.hash_algs value tuples.
    #
    # Length of digest after truncation
    TL = 2  
    ## @brief Index for NI.hash_algs value tuples
    #
    # Length of digest after url-safe base64 encoding
    EL = 3  
    ## @brief Index for NI.hash_algs value tuples
    #
    # Suite index number for this encoding
    SI = 4

    ## @brief Mapping from suite numbers to hash algs
    suite_index = None
    
    @classmethod
    def list_algs(cls):
        """
        @brief classmethod returning a printable string listing the recognized hash algorithm identifiers
        @return string of available hash algorithms for usage strings
        """
        NIname.construct_suite_index()
        l = ""
        for k in sorted(NIname.suite_index.keys()):
            l = l + "%s (%d), " % (NIname.suite_index[k], k)
        return l[:-2]

    @classmethod
    def get_all_algs(cls):
        """
        @brief classmethod returning a list of the recognized hash algorithm identifiers
        @return list of available hash algorithms as text strings    
        """
        return NIname.hash_algs.keys()

    @classmethod
    def get_ni_alphabet(cls):
        """
        @brief ni alphabet contains the set of symbols used in ni names
        Used in validating hi names
        @return alphabet used for ni: base64 encoded digests 
        """
        return "0123456789abcdefghijklmnopqrstuv"
    
    @classmethod
    def get_nih_alphabet(cls):
        """
        @brief nih alphabet contains the set of symbols used in nih names
        Used in generating the luhn-mod-16 checkdigit that is optionally
        appended to nih human readable ni names.  Luhn-mod-16 operations
        are done using the Python luhn module from the Python stdnum suite
        available from http://pypi.python.org/pypi/python-stdnum.
        @return alphabet used for nih: base15 encoded digests 
        """
        return "0123456789abcdef"     
 
    def __init__(self, url):
        """
        @brief Constructor
        @param url string or tuple (in)

        If the argument is a tuple, the elements are strings:
        scheme (ni or nih)
        authority (netloc),
        algorithm,
        [digest],
        [query]

        Note: neither ni or nih scheme allows fragments so these aren't provided for.

        The url string is made by calling ni_urlparse.urlunparse,
        using empty strings for any missing items.
        """
        NIname.construct_suite_index()
        
        debug("Constructing from %s" % str(type(url)))
        self.alg_name = None
        if (type(url) == str):
            self.set_url(url)
        elif (type(url) == tuple):
            l = len(url)
            if ((l < 3) or (l > 5)):
                raise
            # Allow for the fragment field but make it always empty
            url_compts = [url[0], url[1], url[2], "", "", ""]
            if l >= 4:
                url_compts[3] = url[3]
            if l >= 5:
                url_compts[4] = url[4]
            url_str = ni_urlparse.urlunparse(url_compts)
            self.set_url(url_str)
        else:
            debug("NIname constructor: argument type %s not allowed" % str(type(url)))
            raise TypeError
        return
    @classmethod
    def construct_suite_index(cls):
        """
        @brief Construct suite index on first use - dicytionary of suites vs hashalg keys
        """
        if NIname.suite_index == None:
            NIname.suite_index = {}
            for key in NIname.hash_algs.keys():
                NIname.suite_index[NIname.hash_algs[key][NIname.SI]] = key
            debug(NIname.suite_index)
        return
    
    def set_url(self, url):
        """
        @brief update stored URL
        @param url string (in)
        @return (void)
        """
        self.url = url
        (self.scheme, self.netloc, self.path, self.params,
         self.query, self.fragment) = ni_urlparse.urlparse(url)
        (self.dir_part, sep, self.file_part) = self.path.rpartition("/")
        self.validated = False
        return

    def get_hash_alg_info(self):
        """
        @brief find the appropriate entry in hash_algs if there is one
        For the ni scheme the file_part of the URL must be the algorithm
        scheme textual name.
        For the nih scheme the file part can be either the textual scheme name
        or the index number of the suite.
        @return appropriate tuple from hash_algs or None if no match
        """
        if self.file_part in NIname.hash_algs.keys():
            self.alg_name = self.file_part
            return NIname.hash_algs[self.file_part]
        elif (self.scheme == "nih"):
            # See if the file_part is an integer and references one of the algorithms
            try:
                suite_no = int(self.file_part)
            except ValueError:
                debug("get_hash_alg_info: file_part %s is not an integer")
                return None
            if suite_no in NIname.suite_index.keys():
                self.alg_name = NIname.suite_index[suite_no]
                return NIname.hash_algs[NIname.suite_index[suite_no]]               
        return None

    def get_alg_name(self):
        """
        @brief retrieve the textual name of the algoritm embedded in the url
        This may have been derived from a suite index.
        @return algorithm name
        """
        return self.alg_name

    def get_scheme(self):
        """
        @brief retrieve the scheme component of the url
        @return scheme component
        """
        return self.scheme
        
    def get_netloc(self):
        """
        @brief retrieve the netloc component of the url
        @return netloc component
        """
        return self.netloc
        
    def validate_ni_url(self, has_params = True):
        """
        @brief Check URL is in the expected form - right scheme and valid alg name.
        @param has_params Indicates if expecting params in URL (templates have empty params)
        @return returns niSUCCESS, niBADSCHEME, niBADALG, niBADPARAMS, niNOFRAG or niBADURL.

        Check scheme is "ni" or "nih"

        Check that there is no authority if scheme is "nih"
        
        Check last (file) component of path (after last '/') is a valid algorithm name.

        Check that the rest of the path (the 'dir') is empty.

        If has_params is true check params are present and non-empty.

        If has_params is false check params is empty string.

        If has_params is true, check params are in right format for scheme and algorithm

        Check query is empty for nih scheme only.

        Check fragment is empty (neither ni or nih scheme really allows fragments
        """

        if not ((self.scheme == "ni") or (self.scheme == "nih")):
            debug("validate_ni_url: Scheme is not 'ni' or 'nih' in %s" % self.url)
            return ni_errs.niBADSCHEME
        if ((self.scheme == "nih") and (self.netloc != "")):
            debug("validate_ni_url: name has authority - not allowed for 'nih' %s" % self.url)
            return ni_errs.niNOAUTHORITY
        if (self.dir_part != ""):
            debug("validate_ni_url: Non-empty dir part of path in %s" % self.url)
            return ni_errs.niBADURL
        self.hash_alg_info = self.get_hash_alg_info()
        if (self.hash_alg_info == None):
            debug("validate_ni_url: Unknown hash digest function (file part of path) in %s" % self.url)
            return ni_errs.niBADALG
        if (has_params and (self.params == "")):
            debug("validate_ni_url: URL was expected to have non-empty params %s" % self.url)
            return ni_errs.niBADURL
        if ((not has_params) and (self.params != "")):
            debug("validate_ni_url: URL was expected to have empty params %s" % self.url)
            return ni_errs.niBADURL
        if ((self.scheme == "nih") and (self.query != "")):
            debug("validate_ni_url: name has query part - not allowed for 'nih' %s" % self.url)
            return ni_errs.niNOQUERY
        if (self.fragment != ""):
            return ni_errs.niNOFRAG
        if has_params:
            # Check params are correct length
            pl = len(self.params)
            if self.scheme == "ni":
                if pl != self.hash_alg_info[NIname.EL]:
                    debug("validate_ni_url: ni URL has wrong length params (%d != %d)" %
                          (pl, self.hash_alg_info[NIname.EL]))
                    return ni_errs.niBADPARAMS
                elif re.match("[-_0-9a-zA-Z]+$", self.params) == None:
                    debug("validate_ni_url: ni URL uses inappropriate characters in params (%s)" %
                          self.params)
                    return ni_errs.niBADPARAMS
            else:
                # nih scheme
                # Expected length is 2 characters for every character in
                # truncated digest and optionally 2 extra for the check digit
                # and semi-colon separator
                tl2 = 2 * self.hash_alg_info[NIname.TL]
                if not ((pl == (tl2 + 2)) or (pl == tl2)):
                    debug("validate_ni_url: nih URL has wrong length params (%d != %d or %d)" %
                          (pl, tl2, (tl2 + 2)))
                    return ni_errs.niBADPARAMS
                else:
                    m = re.match("[0-9a-f]+(;[0-9a-f])?$", self.params)
                    if not m:
                        debug("validate_ni_url: nih URL has an inappropriate format in params (%s)" %
                              self.params)
                        return ni_errs.niBADPARAMS
                    elif (m.group(1) == None) and (pl != tl2):
                        debug("validate_ni_url: nih URL without check digit is too long(%d != %d)" %
                              (pl, tl2))
                        return ni_errs.niBADPARAMS
                    
        self.validated = True
        return ni_errs.niSUCCESS    

    def url_validated(self):
        """
        @brief Return boolean indicating if ni: URL has been validated
        @return self.validated
        """
        return self.validated
    
    def regen_url(self):
        """
        @brief regenerate internal state of URL from components after update
        Clear validated flag after regenerating state.
        @return (void)
        """
        self.url = ni_urlparse.urlunparse((self.scheme, self.netloc, self.path,
                                           self.params, self.query, self.fragment))
        self.validated = False
        return
    
    def set_params(self, params):
        """
        @brief update params part of stored URL and regen URL
        Should call validate again afterwards.
        @param params new value for params
        @return (void)
        """
        self.params = params
        self.regen_url()
        return

    def get_url(self):
        """
        @brief return stored URL rebuilt from components
        @return reconstructed URL
        """
        return self.url
        
    def get_query_string(self):
        """
        @brief return stored query string
        @return query
        """
        return self.query
        
    def get_hash_function(self):
        """
        @brief return hash function for specified hash alg name (file_part)
        @return callable for selected hash function
        """
        if (not self.validated):
            debug("get_hash_function called for unvalidated URL %s" % self.url)
            return None
        return self.hash_alg_info[NIname.AF]

    def get_digest_length(self):
        """
        @brief return digest length for specified hash alg name/suite (file_part)
        @return binary digest length in octets
        """
        if (not self.validated):
            debug("get_digest_length called for unvalidated URL %s" % self.url)
            return None
        return self.hash_alg_info[NIname.HL]

    def get_truncated_length(self):
        """
        @brief return truncated digest length for specified hash alg name/suite (file_part)
        @return truncated binary digest length in octets
        """
        if (not self.validated):
            debug("get_truncated_length called for unvalidated URL %s" % self.url)
            return None
        return self.hash_alg_info[NIname.TL]

    def get_b64_encoded_length(self):
        """
        @brief return encoded digest length for specified hash alg name (file_part)
        @return url-safe base64 encoded digest length in octets
        """
        if (not self.validated):
            debug("get_b64_encoded_length called for unvalidated URL %s" % self.url)
            return None
        return self.hash_alg_info[NIname.EL]

    def get_digest(self):
        """
        @brief return params part of stored URL
        @return params
        """
        return self.params

    def get_wku_transform(self):
        """
        @brief Generate http .well-known transform of ni: URL
        @return HTTP URL with .well-known in it or None if not validatable or has empty params.

        Before generating check that URL has been validated and contains params (digest).
        """
        if (not self.validated):
            rv = self.validate_ni_url(has_params = True)
            if (rv != ni_errs.niSUCCESS):
                return None
        elif (self.params ==  ""):
            return None
        return ni_urlparse.urlunparse(("http", self.netloc,
                                       "/.well-known/ni/"+self.file_part+"/"+self.params,
                                       "", self.query, self.fragment))
    
    def __repr__(self):
        """
        @brief Presentation string for NIname
        @return URL string
        """ 
        return self.url

class NIdigester(ParamDigester):
    """
    @brief Class to wrap up a digest mechanism with the ni URI to be used while 
    @brief sending a file to an HTTP server.  Helper class for MultipartParam.

    Derived from ParamDigester in the encode module and the NIname class.
    
    The digest is generated on the fly while the octets are being sent to the
    server via the encode or iter_encode methods of MultipartParam.

    The NIdigester class then has five methods:
    - set_url - records the template url and sets up the 'context' appropriate 
                for generating the digest using the algorithm in the template.
    - update_digest - incorporates a chunk of data into the digest
    - finalize_digest - creates and store the digest according to the algorithm and
                data fed in. Regenerates the url with the digest
    - get_digest - returns the claculated digest
    - get_encoded _length - returns the (expected) length of the url-safe base64
                encoded length (works before digest has been calculated from
                algorithm name).
    - get_url - get the url in its current form (with digest once finalized)

    The intention is that the digest is created for a file object and the
    digest can be passed across as a part of all of a separate parameter
    in order to check that the file has not got corrupted
    """
    def __init__(self):
        """
        @brief Constructor - Initialises instance variables
        """
        self.algorithm = None
        self.hash_function = None
        self.digest = None
        self.ni_name = None
        self.initialized = False
        return

    def set_url(self, url):
        """
        @brief Records algorithm and sets up context for digestion.
        @param ni URI template containing algorithm specifier
        @return returns niSUCCESS, niBADSCHEME, niBADALG or niBADURL.
        """
        self.ni_name = NIname(url)
        rv = self.ni_name.validate_ni_url(has_params=False)
        if rv != ni_errs.niSUCCESS:
            return rv
        self.set_algorithm(self.ni_name.get_hash_function())
        self.initialized = True
        return rv

    def update_digest(self, buffer):
        """
        @brief Pass a buffer of input to digest algorithm
        @param buffer of data to be digested
        @return boolean  indicating success or otherwise
        Feeds buffer to selected algorithm
        """
        debug("digest update with length %d" % len(buffer))
        if not self.initialized:
            debug("NIdigester update called for unitialized instance")
            return False
        self.hash_function.update(buffer)
        return True

    def finalize_digest(self):
        """
        @brief Complete generation of digest based on data input through 'update'
        @return boolean  indicating success or otherwise

        Generates digest and saves the result
        """
        debug("NIdigester digest finalized")
        if not self.initialized:
            debug("NIdigester update called for unitialized instance")
            return False
        bin_dgst = self.hash_function.digest()
        if (len(bin_dgst) != self.ni_name.get_digest_length()):
            debug("Binary digest has unexpected length")
            return False
        # Build the right sort of encoded digest depending on the scheme
        if self.ni_name.get_scheme() == "ni":
            self.digest = NIproc.make_b64_urldigest(bin_dgst[:self.ni_name.get_truncated_length()])
        else:
            self.digest = NIproc.make_human_digest(bin_dgst[:self.ni_name.get_truncated_length()])
        if self.digest is None:
            return False
        self.ni_name.set_params(self.digest)
        if self.ni_name.validate_ni_url(has_params=True) != ni_errs.niSUCCESS:
            return False
        debug("Complete URL: %s" % self.ni_name.get_url())
        return True

    def get_digest(self):
        """
        @brief Access previously generated digest
        @return digest string
        """
        return self.digest

    def get_b64_encoded_length(self):
        """
        @brief return bas64url encoded digest length for specified hash alg name (file_part)
        @return url-safe base64 encoded digest length in octets
        """
        return self.ni_name.get_b64_encoded_length()
    
    def get_url(self):
        """
        @brief Access URL with incorporated digest (if made already)
        @return URL string
        """
        return self.ni_name.get_url()

    def __repr__(self):
        """
        @param Python standard string representation output
        @return suitable representation string
        """
        return "Digest algorithm: %s; Value: %s" % (str(self.algorithm),
                                                    str(self.digest))

class NI:
    """
    @brief NI operations class

    Note: This class does not contain any state.  The operations can all be safely
    called through the single globally accessible instance NIproc defined below.

    Provides:
    
    1. routines to convert 'template' ni: URLS with empty parameter strings
    into full ni: URLs containing a digest made using the algorithm specified in the
    file part of the URL:
    - makenif - adds the digest for a file to the template URL.
    - makenib - adds the digest for a memory buffer to the template URL.

    2. Routines to verify that a full ni: URL has a digest that matches the digest
    of an object made with the algorithm specified in the file part of the URL:
    - checknif - checks digest against the digest for a file.
    - checknib - checks digest against the digest for a memory buffer.
    """

    def __init__(self):
        """
        @brief Constructor - empty 
        """
        debug("Started nilib")
        return

    #######################################
    # Private routines
    #######################################
    def digest_file(self, ni_url, file_name):
        """
        @brief Apply the algorithm selected in ni_url to the whole contents of a file
        @param ni validated NIname object providing digest algorithm info (in)
        @param file_name of file to be hashed (in)
        @return tuple (binary digest as string or None if failed, result code) 
        Returns result code
        niBADALG if ni_url has not been validated
        niBADFILE if canot open/read file, 
        niHASHFAIL if the hash digest seems to be the wrong length or
        niSUCCESS if all goes well.
        Processes file in chunks to avoid needing enormous buffer.
        """

        # Digest output
        dgst = None

        ret = ni_errs.niSUCCESS
        
        # Check ni_url has been validated and if so get hash digest class
        if not ni_url.url_validated():
            return (dgst, ni_errs.niBADALG)
        h = ni_url.get_hash_function()()

        # Open the file
        try:
            f = open(file_name, "rb")
        except Exception, e :
            debug("Cannot open file: Error: %s" % str(e))
            return (dgst, ni_errs.niBADFILE)

        try:
            l = f.read(1024)
        except Exception, e :
            debug("Cannot read file: Error: %s" %str(e))
            return (dgst, ni_errs.niBADFILE)
        while (len(l) > 0):
            h.update(l)
            try:
                l = f.read(1024)
            except Exception, e :
                debug("Cannot read file: Error: %s" %str(e))
                return (dgst, ni_errs.niBADFILE)

        f.close()

        dgst = h.digest()
        
        if len(dgst) != ni_url.get_digest_length():
            debug("Hash algorithm returned unexpected length (Exp: %d; Actual: %d)" % (self.hash_algs[alg_name][HL], len(dgst)))
            return (dgst, ni_errs.niHASHFAIL)

        return (dgst[:ni_url.get_truncated_length()], ni_errs.niSUCCESS)

    #######################################
    # Public routines
    #######################################
    def make_b64_urldigest(self, bin_digest):
        """
        @brief Construct the base64, URL-encoded digest from binary digest
        Remove trailing pad characters ('=') if present (depends on length of digest)  
        @param bin_digest binary hash digest as a string (in)
        @return URL safe base64 encoded ASCII digest (out)
        """
        dgst = base64.urlsafe_b64encode(bin_digest)

        # The result of the previous function potentially contains one or two
        # trailing padding characters (=) depending on the remainder mod(3)
        # of the length of the binary hash.  Since the unpadded value
        # characterizes the hash completely and '=' is a significant
        # character in URLs they can (and should) be removed 
        # So, remove up to two trailing '='
        if (dgst[len(dgst) -  1] == '='):
            reduce = 1
            if (dgst[len(dgst) -  2] == '='):
                reduce = 2
            dgst = dgst[:len(dgst) - reduce]
        debug(dgst)
        debug(len(dgst))
        return dgst

    def make_human_digest(self, bin_digest):
        """
        @brief Construct the base16 (hex) encoding from the binary digest.
        Add check digit.
        @param bin_digest binary hash digest as a string (in)
        @return bas16 (hex) encoded ASCII digest with check digit(out)
        """
        dgst = base64.b16encode(bin_digest).lower()
        debug("base16 encoded digest: %s" % dgst)
        check_digit = luhn.calc_check_digit(dgst, NIname.get_nih_alphabet())
        debug("check digit: %s" % check_digit)
        dgst = dgst + ";" + check_digit        
        return dgst 

    def makenif(self, ni_url, file_name):
        """
        @brief make an ni or nih scheme URI for a named file
        Given an ni or nih name template, open a file, hash it and add the hash to
        the URI template as the 'params' field appended to path file component.

        @param ni_url is the URI - expects NIname object (in/out)
        @param file_name is a file name - string (in)
        @return result code from ni_errs enumeration:
        niBADSCHEME if the ni_url has ascheme other than ni or nih
        niBADPARAMS if the digest isn't the right format when generated
        niNOFRAG if the ni_url has fragment specifiers
        niBADURL if the initial URL already has parameters
        niBADALG if algorithm name is not known,
        niBADFILE if canot open/read file, 
        niHASHFAIL if the hash digest seems to be the wrong length or
        niSUCCESS if all goes well.
        """

        # Check that ni_name has been validated and then validate if not
        if not ni_url.url_validated():
            rv = ni_url.validate_ni_url(has_params=False)
            if (rv != ni_errs.niSUCCESS):
                return rv
                
        # Construct the binary digest of the file
        (bin_dgst, ret) = self.digest_file(ni_url, file_name)
        if bin_dgst == None:
            return ret

        debug(str(len(bin_dgst)))

        # Build the right sort of encoded digest depending on the scheme
        if ni_url.get_scheme() == "ni":
            # Construct the base64, URL-encoded digest
            dgst = self.make_b64_urldigest(bin_dgst)
        else:
            # Construct the bas16 plus checkd digit human readable digest
            dgst = self.make_human_digest(bin_dgst)

        # Reconstruct name
        ni_url.set_params(dgst)

        # Validation *should be* a formality
        return ni_url.validate_ni_url(has_params=True)
        
    def checknif(self, ni_url, file_name):
        """
        @brief check if an ni or nih scheme URI matches a file's content
        Extract the hash algorithm for the URI, use to hash the file
        contents and compare it with the digest in the URI params field.
 
        If the URI and file hashes match, return will be niSUCESS
        If the URI and file content do not match, return will be some
        other value indicating why the match could not be done or failed.
        An example error would be if a hash function is not supported,
        in that case the function returns an niBADALG error.

        @param ni_URL is the URI - expects NIname object with params(in)
        @param file_name is a file name - string (in)
        @return result code taken from ni_errs enumeration
        niBADSCHEME if scheme is not ni or nih
        niBADALG if algorithm name is not known,
        niBADPARAMS if the digest isn't the right format when generated
        niNOFRAG if the ni_url has fragment specifiers
        niBADURL if the initial URL already has parameters
        niBADFILE if canot open/read file, 
        niHASHFAIL if the hash digest seems to be the wrong length,
        niBADHASH if the digest in the name does not match digest of file
        niHASHTOOLONG if the digest in the name is too long,
        and
        niSUCCESS if all goes well.
        """
        # Check that ni_name has been validated and then validate if not
        if not ni_url.url_validated():
            rv = ni_url.validate_ni_url(has_params=True)
            if (rv != ni_errs.niSUCCESS):
                return rv
                
        # Construct the binary digest of the file
        (bin_dgst, ret) = self.digest_file(ni_url, file_name)
        if bin_dgst == None:
            return ret

        # Build the right sort of encoded digest depending on the scheme
        if ni_url.get_scheme() == "ni":
            # Construct the base64, URL-encoded digest
            dgst = self.make_b64_urldigest(bin_dgst)
        else:
            # Construct the bas16 plus checkd digit human readable digest
            dgst = self.make_human_digest(bin_dgst)

        # Check if this matches with digest in name
        supplied_digest = ni_url.get_digest()
        # Check that digest is right length
        if (len(supplied_digest) > len(dgst)):
            return ni_errs.niHASHTOOLONG
        # and matches calculated digest
        if dgst == supplied_digest:
            return ni_errs.niSUCCESS
        elif (ni_url.get_scheme() == "nih") and (dgst[:-2] == supplied_digest):
            # Matched without the optional check digit and separator
            return ni_errs.niSUCCESS            
                                            
        return ni_errs.niBADHASH

    def makenib(self, ni_url, buf):
        """
        @brief make an ni or nih scheme URI for a buffer
        Given an ni or nih name template, hash a buffer and add the hash to
        the URI template as the 'params' field appended to path file component.

        @param ni_url is the URI template - expects NIname object without params (in/out)
        @param buf is the buffer 
        @return result code taken from ni_errs enumeration:
        niBADSCHEME if the ni_url has ascheme other than ni or nih
        niBADPARAMS if the digest isn't the right format when generated
        niNOFRAG if the ni_url has fragment specifiers
        niBADURL if the initial URL already has parameters
        niBADALG if algorithm name is not known,
        niHASHFAIL if the hash digest seems to be the wrong length or
        niSUCCESS if all goes well.     
        """
        # Check that ni_name has been validated and then validate if not
        if not ni_url.url_validated():
            rv = ni_url.validate_ni_url(has_params=False)
            if (rv != ni_errs.niSUCCESS):
                return rv
                
        debug(ni_url.get_alg_name())

        debug("Hashing buffer of length %d" % len(buf))

        # Construct digest of buffer
        h = ni_url.get_hash_function()()
        h.update(buf)
        bin_dgst = h.digest()

        # Check length is as expected
        if len(bin_dgst) != ni_url.get_digest_length():
            debug("Hash algorithm returned unexpected length (Exp: %d; Actual: %d)" % (self.hash_algs[alg_name][HL], len(bin_dgst)))
            return ni_errs.niHASHFAIL

        # Build the right sort of encoded digest depending on the scheme
        if ni_url.get_scheme() == "ni":
            # Construct the base64, URL-encoded digest
            dgst = self.make_b64_urldigest(bin_dgst[:ni_url.get_truncated_length()])
        else:
            # Construct the bas16 plus checkd digit human readable digest
            dgst = self.make_human_digest(bin_dgst[:ni_url.get_truncated_length()])
     
        # Reconstruct name
        ni_url.set_params(dgst)
        
        # Validation *should be* a formality
        return ni_url.validate_ni_url(has_params=True)

    def checknib(self, ni_url, buf):
        """
        @brief check if an ni or nih scheme URI matches a buffer
        Given an ni or nih name and a buffer, hash the buffer and compare the hash to
        the URI 'params' field appended to path file component.
     
        If the URI and buffer hashes match, return will be niSUCESS
        If the URI and file content do not match, return will be some
        other value indicating why the match could not be done or failed.
        An example error would be if a hash function is not supported,
        in that case the function returns an niBADALG error.

        @param ni_url is the URI - expects NIname object with non-empty params (in)
        @param buf is the buffer 
        @param res is the result (out, zero if good)
        @return result code taken from ni_errs enumeration
        niBADSCHEME if scheme is not ni or nih
        niBADALG if algorithm name is not known,
        niBADPARAMS if the digest isn't the right format when generated
        niNOFRAG if the ni_url has fragment specifiers
        niBADURL if the initial URL already has parameters
        niHASHFAIL if the hash digest seems to be the wrong length,
        niBADHASH if the digest in the name does not match digest of file
        niHASHTOOLONG if the digest in the name is too long,
        and
        niSUCCESS if all goes well. 
        """
        # Check that ni_name has been validated and then validate if not
        if not ni_url.url_validated():
            rv = ni_url.validate_ni_url(has_params=True)
            if (rv != ni_errs.niSUCCESS):
                return rv
                
        debug(ni_url.get_alg_name())

        # Construct digest of buffer
        h = ni_url.get_hash_function()()
        h.update(buf)
        bin_dgst = h.digest()

        # Check length is as expected
        if len(bin_dgst) != ni_url.get_digest_length():
            debug("Hash algorithm returned unexpected length (Exp: %d; Actual: %d)" % (self.hash_algs[alg_name][HL], len(bin_dgst)))
            return ni_errs.niHASHFAIL

        # Build the right sort of encoded digest depending on the scheme
        if ni_url.get_scheme() == "ni":
            # Construct the base64, URL-encoded digest
            dgst = self.make_b64_urldigest(bin_dgst[:ni_url.get_truncated_length()])
        else:
            # Construct the base16 plus check digit human readable digest
            dgst = self.make_human_digest(bin_dgst[:ni_url.get_truncated_length()])
   
        # Check if this matches with digest in name
        supplied_digest = ni_url.get_digest()
        # Check that digest is right length
        if (len(supplied_digest) > len(dgst)):
            return ni_errs.niHASHTOOLONG
        # and matches calculated digest
        if dgst == supplied_digest:
            return ni_errs.niSUCCESS
        elif (ni_url.get_scheme() == "nih") and (dgst[:-2] == supplied_digest):
            # Matched without the optional check digit and separator
            return ni_errs.niSUCCESS            
                                            
        return ni_errs.niBADHASH

    def makebnf(self, suite_no, file_name):
        """
        @brief make a binary format hash for a file given the suite number for the encoding
        @param suite_no index of encoding suite (see NIname.suite_index) (in)
        @param file_name is the file (in)
        @return (tuple) result code taken from ni_errs enumeration, binary digest as bytearray(none if fails)
        niBADALG if algorithm name is not known,
        niHASHFAIL if the hash digest seems to be the wrong length or
        niSUCCESS if all goes well.
        niBADALG if algorithm name is not known,
        niBADPARAMS if the digest isn't the right format when generated
        niBADFILE if canot open/read file, 
        niHASHFAIL if the hash digest seems to be the wrong length,
        niHASHTOOLONG if the digest in the name is too long,
        and
        niSUCCESS if all goes well.      
        """

        # Simulate an nih type name using the suite
        url = "nih:%d" % suite_no
        ni_url = NIname(url)
        
        # Validate the suite_no
        rv = ni_url.validate_ni_url(has_params=False)
        if (rv != ni_errs.niSUCCESS):
            return (rv, None)
                
        # Construct the binary digest of the file
        (bin_dgst, ret) = self.digest_file(ni_url, file_name)
        if bin_dgst == None:
            return (ret, None)

        debug(str(len(bin_dgst)))

        dgst_ba = bytearray()
        dgst_ba.append(suite_no)
        dgst_ba.extend(bin_dgst)

        return (ni_errs.niSUCCESS, dgst_ba)
    
    def makebnb(self, suite_no, buf):
        """
        @brief make a binary format hash for a buffer given the suite number for the encoding
        @param suite_no index of encoding suite (see NIname.suite_index) (in)
        @param buf is the buffer (in)
        @return (tuple) result code taken from ni_errs enumeration, binary digest as bytearray (none if fails)
        niBADALG if algorithm name is not known,
        niHASHFAIL if the hash digest seems to be the wrong length or
        niSUCCESS if all goes well.
        niBADALG if algorithm name is not known,
        niBADPARAMS if the digest isn't the right format when generated
        niHASHFAIL if the hash digest seems to be the wrong length,
        niHASHTOOLONG if the digest in the name is too long,
        and
        niSUCCESS if all goes well.      
        """
        # Simulate an nih type name using the suite
        url = "nih:%d" % suite_no
        ni_url = NIname(url)
        
        # Validate the suite_no
        rv = ni_url.validate_ni_url(has_params=False)
        if (rv != ni_errs.niSUCCESS):
            return (rv, None)
                
        debug(ni_url.get_alg_name())

        debug("Hashing buffer of length %d" % len(buf))

        # Construct digest of buffer
        h = ni_url.get_hash_function()()
        h.update(buf)
        bin_dgst = h.digest()

        # Check length is as expected
        if len(bin_dgst) != ni_url.get_digest_length():
            debug("Hash algorithm returned unexpected length (Exp: %d; Actual: %d)" % (self.hash_algs[alg_name][HL], len(bin_dgst)))
            return (ni_errs.niHASHFAIL, None)

        dgst_ba = bytearray()
        dgst_ba.append(suite_no)
        dgst_ba.extend(bin_dgst[:ni_url.get_truncated_length()])

        return (ni_errs.niSUCCESS, dgst_ba)

## @brief NIproc - Global instance for NI operations class
NIproc = NI()

if __name__ == "__main__":
    import inspect

    def lineno():
        """
        @brief Returns the current line number in our program.
        """
        return inspect.currentframe().f_back.f_lineno

    # Sample file names
    foo_sample = "../samples/foo"
    bar_sample = "../samples/bar"

    # Construct 100 octet buffer, zero filled
    buf = "".zfill(100)

    # Construct buffer with random text
    randbuf = "@GCC: (Ubuntu/Linaro 4.5.2-8ubuntu4) 4.5.2GCC: (Ubuntu/Linaro 4.5.2-8ubuntu3) 4.5.2.symtab.strtab.shstrtab.interp.note.ABI-tag.note.gnu.build-id.gnu.hash.dynsym.dynstr.gnu.version.gnu.version_r.rela.dyn.rela.plt.init.text.fini.rodata.eh_frame_hdr.eh_frame.ctors.dtors.jcr.dynamic.got.got.plt.data.bss.comment"
    
    
    # Make file_name "foo"
    file_name = foo_sample

    print "Checking construction of NIname for scheme ni"
    print "============================================="
    
    print "\nNIname from string..."
    n = NIname("ni://tcd.ie/sha-256?a=b")
    print n
    print "\nNIname from 3 element tuple..."
    n = NIname(("ni", "tcd.ie", "sha-256"))
    print n
    print "\nNIname from 4 element tuple..."
    n = NIname(("ni", "tcd.ie", "sha-256", "def"))
    print n
    print "\nNIname from 5 element tuple (query element empty)..."
    n = NIname(("ni", "tcd.ie", "sha-256", "abd", ""))
    print n
    print "\nNIname from 5 element tuple (query element non-empty)..."
    n = NIname(("ni", "tcd.ie", "sha-256", "abd", "xyz"))
    print n
    
    print "\nChecking construction of NIname for scheme nih"
    print   "=============================================="
    
    print "\nNIname from string with no authority..."
    n = NIname("nih:sha-256?a=b")
    print n
    print "\nNIname from 3 element tuple..."
    n = NIname(("nih", "", "sha-256"))
    print n
    print "\nNIname from 4 element tuple..."
    n = NIname(("nih", "", "sha-256", "def"))
    print n
    print "\nNIname from 5 element tuple (query element empty)..."
    n = NIname(("nih", "", "sha-256", "abd", ""))
    print n
    print "\nNIname from 5 element tuple (query element non-empty)..."
    n = NIname(("nih", "", "sha-256", "abd", "xyz"))
    print n
    
    print "\nCheck validation of NIname for bad scheme"
    print   "========================================="

    n = NIname("zz://tcd.ie.bollix/sha-256;?c=moreshite")
    print "\nChecking validation of URL %s with wrong scheme name..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADSCHEME):
        print "Bad scheme correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Bad scheme accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    print "\nCheck validation of NIname for ni scheme"
    print   "========================================"

    n = NIname("ni://tcd.ie.bollix/sha-256;?c=moreshite#a_fragment")
    print "\nChecking validation of URL %s with non-empty fragment part..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niNOFRAG):
        print "Existence of fragment correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Existence of fragment accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/abde/sha-256;?c=moreshite")
    print "\nChecking validation of URL %s with non-empty dir part..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADURL):
        print "Bad path correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Bad path accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/barf-256;?c=moreshite")
    print "\nChecking validation of URL %s with unknown digest..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADALG):
        print "Unknown digest algorithm correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Unknown digest algorithm accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/sha-256;?c=moreshite")
    print "\nChecking validation of template URL %s when expecting params..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADURL):
        print "Lack of params correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Lack of params accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/sha-256;fghfasjhasdgjaaga?c=moreshite")
    print "\nChecking validation of full URL %s when not expecting params..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADURL):
        print "Inappropriate presence of params correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Inappropriate presence of params accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni:///sha-256")
    print "\nChecking validation of minimal template URL %s..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niSUCCESS):
        print "URL correctly accepted"
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/sha-256-32;afshgs?d=e")
    print "\nChecking validation of full URL %s with query..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niSUCCESS):
        print "URL correctly accepted"
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]

    n = NIname("ni://tcd.ie.bollix/sha-256-32;afshg?d=e")
    print "\nChecking validation of full URL %s with a short digest string..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Short digest correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Short digest accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/sha-256-32;afshgxy?d=e")
    print "\nChecking validation of full URL %s with an overlong digest string..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Overlong digest correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Overlong digest accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/sha-256-32;afsh*h?d=e")
    print "\nChecking validation of full URL %s with a inappropriate character in the digest string..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Inappropriate character correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Inappropriate character accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("ni://tcd.ie.bollix/sha-256-32;afshgs?d=e")
    print "\nGenerating HTTP transform of URL... %s" % n.get_url()
    print n.get_wku_transform()

    n = NIname("ni://tcd.ie.bollix/mumble-256;afshgsdd?d=e")
    print"\nChecking HTTP transform not generated for bad ni: URL %s ..." % n.get_url()
    http_url = n.get_wku_transform()
    if (http_url == None):
        print "HTTP transform correctly not generated for ni: URL with bad transform"
    else:
        print "Error: HTTP transform %s generated for ni: URL with bad transform" % http_url

    n = NIname("ni://tcd.ie.bollix/sha-256;?d=e")
    print"\nChecking HTTP transform not generated for ni: template URL %s ..." % n.get_url()
    http_url = n.get_wku_transform()
    if (http_url == None):
        print "HTTP transform correctly not generated for ni: template URL with no digest"
    else:
        print "Error: HTTP transform %s generated for ni: templatye URL with no digest" % http_url


    print "\nCheck validation of NIname for nih scheme"
    print   "========================================="

    n = NIname("nih://tcd.ie/sha-256;")
    print "\nChecking validation of URL %s with authority part..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niNOQUERY):
        print "Existence of authority correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Existence of authority accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256;?c=moreshite")
    print "\nChecking validation of URL %s with non-empty query part..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niNOQUERY):
        print "Existence of query correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Existence of query accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256;#a_fragment")
    print "\nChecking validation of URL %s with non-empty fragment part..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niNOFRAG):
        print "Existence of fragment correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Existence of fragment accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:abde/sha-256;")
    print "\nChecking validation of URL %s with non-empty dir part..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADURL):
        print "Bad path correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Bad path accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:barf-256;")
    print "\nChecking validation of URL %s with unknown digest..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADALG):
        print "Unknown digest algorithm correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Unknown digest algorithm accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256;")
    print "\nChecking validation of template URL %s when expecting params..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADURL):
        print "Lack of params correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Lack of params accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256;fghfasjhasdgjaagasda")
    print "\nChecking validation of full URL %s when not expecting params..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADURL):
        print "Inappropriate presence of params correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Inappropriate presence of params accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256")
    print "\nChecking validation of minimal template URL with name %s..." % n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niSUCCESS):
        print "URL correctly accepted"
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:2")
    print "\nChecking validation of minimal template URL with suite number %s..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niSUCCESS):
        print "URL correctly accepted: suite identifed - %s" % n.get_alg_name()
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:11;")
    print "\nChecking validation of URL %s with unknown suite number..." %n.get_url()
    rv = n.validate_ni_url(has_params=False)
    if (rv == ni_errs.niBADALG):
        print "Unknown suite number correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Unknown suite number accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256-32;01234aff")
    print "\nChecking validation of full URL without check digit %s..." % n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niSUCCESS):
        print "URL correctly accepted"
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]

    n = NIname("nih:sha-256-32;01234aff;5")
    print "\nChecking validation of full URL with check digit %s..." % n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niSUCCESS):
        print "URL correctly accepted"
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]

    n = NIname("nih:sha-256-32;0123456")
    print "\nChecking validation of full URL %s with a short digest string..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Short digest correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Short digest accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256-32;012345678")
    print "\nChecking validation of full URL %s with an overlong digest string..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Overlong digest correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Overlong digest accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256-32;0123456g")
    print "\nChecking validation of full URL %s with an inappropriate character in the digest string..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Inappropriate character correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Inappropriate presence of params accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]
    
    n = NIname("nih:sha-256-32;01234567ff")
    print "\nChecking validation of full URL %s with overlong digest string but same length as with check digit..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Overlong digest correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Overlong digest accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]

    n = NIname("nih:sha-256-32;01234567;h")
    print "\nChecking validation of full URL %s with bad check digit..." %n.get_url()
    rv = n.validate_ni_url(has_params=True)
    if (rv == ni_errs.niBADPARAMS):
        print "Bad check digit correctly detected."
    elif (rv == ni_errs.niSUCCESS):
        print "Bad check digit accepted incorrectly."
    else:
        print "Unexpected error detected: %s" % ni_errs_txt[rv]

    n = NIname("nih:sha-256-32;01234aff")
    print "\nGenerating HTTP transform of URL... %s" % n.get_url()
    print n.get_wku_transform()

    n = NIname("nih:mumble-256;afshgsdd")
    print"\nChecking HTTP transform not generated for bad ni: URL %s ..." % n.get_url()
    http_url = n.get_wku_transform()
    if (http_url == None):
        print "HTTP transform correctly not generated for ni: URL with bad transform"
    else:
        print "Error: HTTP transform %s generated for ni: URL with bad transform" % http_url

    n = NIname("nih:sha-256;")
    print"\nChecking HTTP transform not generated for ni: template URL %s ..." % n.get_url()
    http_url = n.get_wku_transform()
    if (http_url == None):
        print "HTTP transform correctly not generated for ni: template URL with no digest"
    else:
        print "Error: HTTP transform %s generated for ni: templatye URL with no digest" % http_url


    print "\nChecking operation of NIdigester"
    print "=================================="

    print "Setting up NIdigester with template ni://www.example.com/sha-256"
    z = NIdigester()
    rv = z.set_url("ni://www.example.com/sha-256")
    if rv != ni_errs.niSUCCESS:
        print "Unexpected error detected when validating template: %s" % ni_errs_txt[rv]
    else:
        print "Template accepted by NIdigester"
        rv = z.update_digest("The quick brown fox jumped over the lazy dog")
        if not rv:
            print "Nidigester update_digest returned False - unexpected"
        else:
            rv = z.finalize_digest()
            if not rv:
                print "NIdigester finalize_digest return False - unexpected"
            else:
                print "Generated URL : %s" % z.get_url()
                print "Representation of NIdigester instance: %s " % z
    
    print "Setting up NIdigester with duff template ni://www.example.com/shc-256"
    z = NIdigester()
    rv = z.set_url(("ni", "www.example.com", "shb-256"))
    if rv == ni_errs.niSUCCESS:
        print "Unexpected success detected when validating template"
    else:
        print "Error correctly detected when validating template: %s" % ni_errs_txt[rv]
        
    print "\nChecking makenif, makebnf and checknif"
    print   "======================================\n"
    
    print "File name %s in buffer 'buf' %d octets long" % ( str(file_name), len(file_name))
    
    n = NIname("ni://tcd.ie.bollix/sha-256;?c=moreshite")
    print "\nName: %s" % n.get_url() 
    NIproc.makenif(n, file_name)
    print "Name with digest: %s\n" % n.get_url()
    
    n = NIname("nih:sha-256-32;")
    print "\nName: %s" % n.get_url() 
    NIproc.makenif(n, file_name)
    full_name = n.get_url()
    print "Name with digest: %s" % n.get_url()
    print "Checking name with check digit..."
    ret = NIproc.checknif(n, file_name)
    if ret == ni_errs.niSUCCESS:
        print "Digest verified successfully"
    else:
        print "Error inappropriately detected when verifying name: %s" % ni_errs_txt[ret]
    n = NIname(full_name[:-2])
    print "Checking name without check digit...%s" % n.get_url()
    ret = NIproc.checknif(n, file_name)
    if ret == ni_errs.niSUCCESS:
        print "Digest verified successfully"
    else:
        print "Error inappropriately detected when verifying name: %s" % ni_errs_txt[ret]
    
    n = NIname("nih:6;")
    print "\nName: %s" % n.get_url() 
    NIproc.makenif(n, file_name)
    print "Name with digest: %s" % n.get_url()
    
    print "\nChecking makebnf with suite 6..."
    (ret, ba) = NIproc.makebnf(6, file_name)
    if ret == ni_errs.niSUCCESS:
        print "Binary digest: %s" % base64.b16encode(str(ba))
    else:
        print "Error inappropriately detected when generating binary digest: %s" % ni_errs_txt[ret]
    
    print "\nChecking makebnf with (bad) suite 11..."
    (ret, ba) = NIproc.makebnf(11, file_name)
    if ret == ni_errs.niSUCCESS:
        print "Making binary digest succeeded unexpectedly"
    else:
        print "Error correctly detected when generating binary digest: %s" % ni_errs_txt[ret]
    
    n = NIname("ni://tcd.ie.bollix/sha-256-32;?c=moreshite")
    print "\nName: %s" % n.get_url() 
    NIproc.makenif(n, file_name)
    print "Name with SHA256 truncated digest: %s\n" % n.get_url()
    
    n = NIname("ni://tcd.ie.bollix/sha-256;")    
    print "\nName: %s" % n.get_url() 
    NIproc.makenif(n, bar_sample)
    print "Name with digest: %s\n" % n.get_url()

    n = NIname("ni://tcd.ie/sha-256;?c=image%%2Fjson")
    print "\nName: %s" % n.get_url() 
    ret = NIproc.makenif(n, file_name)
    if ret != ni_errs.niSUCCESS:
        print "Error: %s at line %d" % (ni_errs_txt[ret], lineno())
    else:
        print "Name with digest: %s\n" % n.get_url()
        ret = NIproc.checknif(n, file_name)
        if ret != ni_errs.niSUCCESS:
            print "Error: %s at line %d" % (ni_errs_txt[ret], lineno())
        else:
            print "Hash check for name %s with content file %s successful." % (n.get_url(),
                                                                               file_name)
        print "Checking name same digest with wrong content file \'%s\'" % bar_sample
        ret = NIproc.checknif(n, bar_sample)
        if ret == ni_errs.niBADHASH:
            print "Correctly detected: %s" % ni_errs_txt[ret]
        elif ret == ni_errs.niSUCCESS:
            print "Hash check for name %s failed to detect hash incorrect for content." % n.get_url()
        else:
            print "Hash check for name %s detected unexpected error %s." % (n.get_url(), ni_errs_txt[ret])
                                                                               
        
        i = n.get_url().index("?")
        good_name =  n.get_url()                                                                     
        nn = NIname("Z".join([n.get_url()[:i], n.get_url()[i:]]))
        print "\nName with too long digest: %s\n" % nn.get_url()
        ret = NIproc.checknif(nn, file_name)
        if ret == ni_errs.niHASHTOOLONG:
            print "Correctly detected: %s" % ni_errs_txt[ret]
        elif ret == ni_errs.niSUCCESS:
            print "Hash check for name %s failed to detect HASHTOOLONG error." % nn.get_url()
        else:
            print "Hash check for name %s detected unexpected error %s." % (nn.get_url(), ni_errs_txt[ret])
                                                                               
        i = good_name.index(";") + 4
        c = good_name[i]
        if c != "_":
            bad_name = "_".join([good_name[:i],good_name[(i+1):]])
        else:
            bad_name = "Q".join([good_name[:i],good_name[(i+1):]])
        nn = NIname(bad_name)
        print "\nName with corrupted digest: %s\n" % nn.get_url()
        ret = NIproc.checknif(nn, file_name)
        if ret == ni_errs.niBADHASH:
            print "Correctly detected: %s" % ni_errs_txt[ret]
        elif ret == ni_errs.niSUCCESS:
            print "Hash check for name %s failed to detect HASHTOOLONG error." % nn.get_url()
        else:
            print "Hash check for name %s detected unexpected error %s." % (nn.get_url(), ni_errs_txt[ret])

    print "\nChecking makenib, makebnb and checknib"
    print   "======================================\n"

    print "Using buffer 'buf' %d octets long filled with zeroes (%s)." % ( len(buf), buf.decode())

    n = NIname("ni://folly.org.wl/sha-256;?abc=zzz")
    print "\nName: %s" % n.get_url()
    NIproc.makenib(n, randbuf)
    n = NIname("ni://folly.org.wl/sha-256;?abc=mmm")
    print "Name with digest of 'randbuf': %s\n" % n.get_url()
    ret = NIproc.makenib(n, buf)
    if ret != ni_errs.niSUCCESS:
        print "Error: %s at line %d" % (ni_errs_txt[ret], lineno())
    else:
        print "Name with digest of 'buf': %s\n" % n.get_url()
        ret = NIproc.checknib(n, buf)
        if ret != ni_errs.niSUCCESS:
            print "Error: %s at line %d" % (ni_errs_txt[ret], lineno())
        else:
            print "Hash check for name %s with content file %s successful." % (n.get_url(),
                                                                               file_name)
        print "Checking name same digest with wrong content buffer \'randbuf\'"
        ret = NIproc.checknib(n, randbuf)
        if ret == ni_errs.niBADHASH:
            print "Correctly detected: %s" % ni_errs_txt[ret]
        elif ret == ni_errs.niSUCCESS:
            print "Hash check for name %s failed to detect hash incorrect for content buffer." % n.get_url()
        else:
            print "Hash check for name %s detected unexpected error %s." % (n.get_url(), ni_errs_txt[ret])
                                                                               
        
        i = n.get_url().index("?")
        good_name =  n.get_url()                                                                     
        nn = NIname("Z".join([n.get_url()[:i], n.get_url()[i:]]))
        print "\nName with too long digest: %s\n" % nn.get_url()
        ret = NIproc.checknib(nn, buf)
        if ret == ni_errs.niBADPARAMS:
            print "Correctly detected: %s" % ni_errs_txt[ret]
        elif ret == ni_errs.niSUCCESS:
            print "Hash check for name %s failed to detect HASHTOOLONG error." % nn.get_url()
        else:
            print "Hash check for name %s detected unexpected error %s." % (nn.get_url(), ni_errs_txt[ret])
                                                                               
        i = good_name.index(";") + 4
        c = good_name[i]
        if c != "_":
            bad_name = "_".join([good_name[:i],good_name[(i+1):]])
        else:
            bad_name = "Q".join([good_name[:i],good_name[(i+1):]])
        nn = NIname(bad_name)
        print "\nName with corrupted digest: %s\n" % nn.get_url()
        ret = NIproc.checknib(nn, buf)
        if ret == ni_errs.niBADHASH:
            print "Correctly detected: %s" % ni_errs_txt[ret]
        elif ret == ni_errs.niSUCCESS:
            print "Hash check for name %s failed to detect HASHTOOLONG error." % nn.get_url()
        else:
            print "Hash check for name %s detected unexpected error %s." % (nn.get_url(), ni_errs_txt[ret])

    n = NIname("nih:sha-256-32;")
    print "\nName: %s" % n.get_url() 
    NIproc.makenib(n, randbuf)
    full_name = n.get_url()
    print "Name with digest: %s" % n.get_url()
    print "Checking name with check digit..."
    ret = NIproc.checknib(n, randbuf)
    if ret == ni_errs.niSUCCESS:
        print "Digest verified successfully"
    else:
        print "Error inappropriately detected when verifying name: %s" % ni_errs_txt[ret]
    n = NIname(full_name[:-2])
    print "Checking name without check digit...%s" % n.get_url()
    ret = NIproc.checknib(n, randbuf)
    if ret == ni_errs.niSUCCESS:
        print "Digest verified successfully"
    else:
        print "Error inappropriately detected when verifying name: %s" % ni_errs_txt[ret]
    
    n = NIname("nih:6;")
    print "\nName: %s" % n.get_url() 
    NIproc.makenib(n, randbuf)
    print "Name with digest: %s" % n.get_url()
    
    print "\nChecking makebnb with suite 6..."
    (ret, ba) = NIproc.makebnb(6, randbuf)
    if ret == ni_errs.niSUCCESS:
        print "Binary digest: %s" % base64.b16encode(str(ba))
    else:
        print "Error inappropriately detected when generating binary digest: %s" % ni_errs_txt[ret]
    
    print "\nChecking makebnb with (bad) suite 11..."
    (ret, ba) = NIproc.makebnb(11, randbuf)
    if ret == ni_errs.niSUCCESS:
        print "Making binary digest succeeded unexpectedly"
    else:
        print "Error correctly detected when generating binary digest: %s" % ni_errs_txt[ret]
    
    print "\nEnd of tests"
    print "============\n"

                                                                               





    
