"""
@package nilib
@file encode.py
@brief Multipart/form-data encoding module.
@version $Revision: 0.9 $ $Author: Chris Atlee and Elwyn Davies $

Copyright (c) 2011 Chris AtLee
Copyright (c) 2012 Elwyn Davies, Folly Consulting and Trinity College Dublin

.
    This version of this module is incorporated in the NI URI library
    developed as part of the SAIL project. (http://sail-project.eu)

    Specification(s) - note, versions may change
          - http://tools.ietf.org/html/draft-farrell-decade-ni-10
          - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03

Ths module is a modified version of part of the 'poster' software written
by Chris Atlee.  The original code is available at
            - http://atlee.ca/software/poster/index.html

Licensed under the MIT license:

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

=============================================================================

This module provides functions that faciliate encoding name/value pairs
as multipart/form-data suitable for a HTTP POST or PUT request.

multipart/form-data is the standard way to upload files over HTTP

This version has been modified in two ways from version 0.8.1 on the web site:
- to allow a digest for a file to be uploaded to be generated 'on the fly'
  as it is sent out to the network for transmission over HTTP.
- to provide values for form parameters to be generated at the time the
  parameter is written to the network rather than when the form is constructed.
  This allows values to be dependent on things (such as digests) that are
  calculated as the form is uploaded.
"""

#==============================================================================#
# List of classes/global functions in file
__all__ = ['gen_boundary', 'encode_and_quote', 'ParamDigester', 'MultipartParam',
        'encode_string', 'encode_file_header', 'get_body_size', 'get_headers',
        'multipart_yielder', 'multipart_encode']

#==============================================================================#
try:
    import uuid
    def gen_boundary():
        """
        @brief Generates a random string to use as the boundary for a message
        @return random boundary string
        """
        return uuid.uuid4().hex
except ImportError:
    import random, sha
    def gen_boundary():
        """
        @brief Generates a random string to use as the boundary for a message
        @return random boundary string
        """
        bits = random.getrandbits(160)
        return sha.new(str(bits)).hexdigest()

import hashlib
import urllib, re, os, mimetypes
try:
    from email.header import Header
except ImportError:
    # Python 2.4
    from email.Header import Header

#==============================================================================#
def encode_and_quote(data):
    """
    @brief Depending on whether data is unicode or otherwise, encode and quote appropriately.
    @param data unicode or plain string - the data to be encoded
    @return If data is unicode: return urllib.quote_plus(data.encode("utf-8"))
    @return Otherwise:          return urllib.quote_plus(data)
    """
    if data is None:
        return None

    if isinstance(data, unicode):
        data = data.encode("utf-8")
    return urllib.quote_plus(data)

#------------------------------------------------------------------------------#
def _strify(s):
    """
    @brief Encode plain or unicode string.
    @return If s is a unicode string, encode it to UTF-8 and return the results,
    @return Otherwise, return str(s), or None if s is None
    """
    if s is None:
        return None
    if isinstance(s, unicode):
        return s.encode("utf-8")
    return str(s)

#==============================================================================#
class ParamDigester:
    """
    @brief Base class to wrap up a digest mechanism to be used while sending a
    @brief file to an HTTP server.  Helper class for MultipartParam.

    The digest is generated on the fly while the octets are being sent to the
    server via the encode or iter_encode methods of MultipartParam.

    The class then has four methods:
    - set_algorithm - records the required algoritm and sets up the 'context'
                    appropriate for generating the digest using the algorithm.
                    The parameter to this function should be a digest function
                    from the hashlib module.
    - update_digest - incorporates a chunk of data into the digest
    - finalize_digest - creates and store the digest according to the algorithm
                    and data fed in
    - get_digest - returns the claculated digest

    The intention is that the digest is created for a file object and the
    digest can be passed across as a part of all of a separate parameter
    in order to check that the file has not geot corrupted
    """

    #--------------------------------------------------------------------------#
    def __init__(self):
        """
        @brief Constructor - Initialises instance variables
        """
        self.algorithm = None
        self.digest = None
        self.hash_function = None
        return

    #--------------------------------------------------------------------------#
    def set_algorithm(self, alg_name= "", digester=None):
        """
        @brief Initializes digester and sets up context for digestion.
        @param alg_name - str Textual name of algorithm
        @param digester callable digest function from hashlib
        """
        self.algorithm = alg_name
        self.hash_function = digester()
        return

    #--------------------------------------------------------------------------#
    def update_digest(self, buffer):
        """
        @brief Pass a buffer of input to digest algorithm
        @param buffer of data to be digested
        @return boolean  indicating success or otherwise
        Feeds buffer to selected algorithm
        """
        #print "digest update with length %d" % len(buffer)
        if self.algorithm is None:
            return False
        self.hash_function.update(buffer)
        return True

    #--------------------------------------------------------------------------#
    def finalize_digest(self):
        """
        @brief Complete generation of digest based on data input through 'update'
        @return boolean  indicating success or otherwise

        Generates digest and saves the result
        """
        #print "digest finalized"
        if self.algorithm is None:
            return False
        self.digest = self.hash_function.digest()
        return True

    #--------------------------------------------------------------------------#
    def get_digest(self):
        """
        @brief Access previously generated digest
        @return digest string
        """
        return self.digest

    #--------------------------------------------------------------------------#
    def __repr__(self):
        """
        @brief Python standard string representation output
        @return suitable representation string
        """
        return "Digest algorithm: %s; Value: %s" % (str(self.algorithm),
                                                    str(self.digest))
        
#==============================================================================#
class MultipartParam(object):
    """
    @brief Represents a single parameter in a multipart/form-data request

    Such parameters can be
    - simple string values,
    - values defined via a dictionary that supplies a generator and a size, or
    - file-like objects.
    
    This class is designed so that the parameters and chunks of large ones
    such as files can be read off to feed the request stream by an iterator.

    In the list of instance variables below the following conditions aoply:
    - Both ``value`` and ``fileobj`` must not be set, doing so will
      raise a ValueError assertion.

    - If ``fileobj`` is set, and ``filesize`` is not specified, then
      the file's size will be determined first by stat'ing ``fileobj``'s
      file descriptor, and if that fails, by seeking to the end of the file,
      recording the current position as the size, and then by seeking back to
      the beginning of the file.
    """
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var name
    # string the name of this parameter.

    ##@var value
    # string, unicode or dictionary If ``value`` is set, it must be either
    # - string or unicode object to use as the data for this parameter, or
    # - a dictionary that contains a ``generator`` key.
    # In the dictionary case the value of the generator key must be a callable
    # which generates a string or unicode object value that can be used as data.
    # When the value for a dictionary is to be encoded, the ``generator``
    # callable is called with the dictionary as a parameter.  Because the
    # serialization process precalculates the length of the set of parameters,
    # the dictionary must also contain a (fixed value) length field that will
    # be the length of the value.

    ##@var filename
    # string If ``filename`` is set, it is what to say that this parameter's
    # filenam is in the form item.  Note that this does not have to be the
    # actual filename of any local file.

    ##@var filetype
    # string If ``filetype`` is set, it is used as the Content-Type for this
    # parameter. If unset it defaults to "text/plain; charset=utf8"

    ##@var filesize
    # integer If ``filesize`` is set, it specifies the length of the file
    # ``fileobj``

    ##@var fileobj
    # file-like object If ``fileobj`` is set, it must be a file-like object
    # that supports .read().

    ##@var cb
    # callable cb`` which will be called from iter_encode with three
    # arguments(self, current, total), representing the current parameter,
    # current amount transferred, and the total size.  This is done after
    # each chunk of the paramter is yielded in the iterator.  the callable
    # does not return a value.

    ##@var digester
    # instance of a class derived from ParamDigester.
    # If not None, it will be used in conjunction with a fileobj to generate
    # a digest for the file that may be sent across the wire as (part of)
    # another form parameter.
    
    #--------------------------------------------------------------------------#
    def __init__(self, name, value=None, filename=None, filetype=None,
                        filesize=None, fileobj=None, cb=None, digester=None):
        """
        @brief Constructor: saves values and checks rules for allowed
               combinations.  For details on parameters see corresponding
               instance variables.
        @param name string name of parameter
        @param value string, unicode or dictionary deleievers value if not a file
        @param filename string filename to be passed to remote server
        @param filetype string the Content-Type of the parameter if a file 
        @param filesize integer size of a fileobj
        @param fileobj object with file-like attributes (read, seek, tell, etc)
        @param cb callable called after each value chunk is yielded by iterator
        @param digester object instance of class derieved from ParamDigester
        """
        self.name = Header(name).encode()
        if value is None:
            self.value = None
        elif type(value) == dict:
            if "generator" not in value:
                raise AttributeError("Value dictionary must have 'generator' key")
            if not callable(value["generator"]):
                raise AttributeError("Value dictionary 'generator' entry must be callable.")
            if "length" not in value:
                raise AttributeError("Value dictionary must have 'length' key")
            self.value = value
        else:
            self.value = _strify(value)
        if filename is None:
            self.filename = None
        else:
            if isinstance(filename, unicode):
                # Encode with XML entities
                self.filename = filename.encode("ascii", "xmlcharrefreplace")
            else:
                self.filename = str(filename)
            self.filename = self.filename.encode("string_escape").\
                    replace('"', '\\"')
        self.filetype = _strify(filetype)

        self.filesize = filesize
        self.fileobj = fileobj
        self.cb = cb
        self.digester = digester

        if self.value is not None and self.fileobj is not None:
            raise ValueError("Only one of value or fileobj may be specified")

        if fileobj is not None and filesize is None:
            # Try and determine the file size
            try:
                self.filesize = os.fstat(fileobj.fileno()).st_size
            except (OSError, AttributeError):
                try:
                    fileobj.seek(0, 2)
                    self.filesize = fileobj.tell()
                    fileobj.seek(0)
                except:
                    raise ValueError("Could not determine filesize")

    #--------------------------------------------------------------------------#
    def __cmp__(self, other):
        """
        @brief Compare this parameter with another one
        @param other instance of MultipartParame to compare against
        @return boolean if all attributes are equal

        Compares all instance variables in attrs list.
        """
        attrs = ['name', 'value', 'filename', 'filetype', 'filesize', 'fileobj', 'digester']
        myattrs = [getattr(self, a) for a in attrs]
        oattrs = [getattr(other, a) for a in attrs]
        return cmp(myattrs, oattrs)

    #--------------------------------------------------------------------------#
    def reset(self):
        """
        @brief Rewind file parameters
        """
        if self.fileobj is not None:
            self.fileobj.seek(0)
        elif self.value is None:
            # Probably ought to be able to reset dictionar values as well
            raise ValueError("Don't know how to reset this parameter")

    #--------------------------------------------------------------------------#
    @classmethod
    def from_file(cls, paramname, filename):
        """
        @brief Returns new MultipartParam object constructed from a local file
        @param cls classname  MultipartParam
        @param paramname string name for this parameter (not the filename!)
        @param filename string pathname for local file
        @return instance of MultipartParam

        The constructor parameters are set as follows:
        - ``filesize`` is determined by os.path.getsize(``filename``)
        - ``filetype`` is determined by mimetypes.guess_type(``filename``)[0]
        - ``filename`` is set to os.path.basename(``filename``)
        """

        return cls(paramname, filename=os.path.basename(filename),
                filetype=mimetypes.guess_type(filename)[0],
                filesize=os.path.getsize(filename),
                fileobj=open(filename, "rb"))

    #--------------------------------------------------------------------------#
    @classmethod
    def from_params(cls, params):
        """
        @brief Constructs a list of MultipartParam objects
        @param cls classname  MultipartParam
        @param params either:
               - sequence of any combination of
                  - name, value pairs, or
                  - MultipartParam instances;
                or:
               - a mapping of names to values (e.g. dictionary)
        @return constructed list of MultipartParam objects

        The values may be strings, dictionaries or file objects, or
        MultipartParam objects.  MultipartParam object names must match
        the given names in the name,value pairs or mapping, if applicable.
        """
        if hasattr(params, 'items'):
            params = params.items()

        retval = []
        for item in params:
            if isinstance(item, cls):
                retval.append(item)
                continue
            name, value = item
            if isinstance(value, cls):
                assert value.name == name
                retval.append(value)
                continue
            if hasattr(value, 'read'):
                # Looks like a file object
                filename = getattr(value, 'name', None)
                if filename is not None:
                    filetype = mimetypes.guess_type(filename)[0]
                else:
                    filetype = None

                retval.append(cls(name=name, filename=filename,
                    filetype=filetype, fileobj=value))
            else:
                retval.append(cls(name, value))
        return retval

    #--------------------------------------------------------------------------#
    def encode_hdr(self, boundary):
        """
        @brief Returns the header of the encoding of this parameter
        @param boundary string MIME boundary string to be used
        @return string header strings preceded by MIME boundary
                separated by CRLF and terminated by CRLFCRLF
        """
        boundary = encode_and_quote(boundary)

        headers = ["--%s" % boundary]

        if self.filename:
            disposition = 'form-data; name="%s"; filename="%s"' % (self.name,
                    self.filename)
        else:
            disposition = 'form-data; name="%s"' % self.name

        headers.append("Content-Disposition: %s" % disposition)

        if self.filetype:
            filetype = self.filetype
        else:
            filetype = "text/plain; charset=utf-8"

        headers.append("Content-Type: %s" % filetype)

        headers.append("")
        headers.append("")

        return "\r\n".join(headers)

    #--------------------------------------------------------------------------#
    def encode(self, boundary):
        """
        @brief Returns the string encoding of this parameter
        @param boundary string needed to ensure it is not embedded in parameter
               and to trail the value.
        @return string representing parameter value or fileobj as appropriate

        If the parameter is a fileobj and has a digester, the digest is
        generated.  For this case the digest is generated in one go since the
        file is not chunked.  This will genrally only happen for small files.
        """
        if self.value is None:
            value = self.fileobj.read()
            if self.digester is not None:
                self.digester.update_digest(value)
                self.digester.finalize_digest()
        elif type(self.value) == dict:
            if len(self.value) == 2:
                # Just the "generator" and "length" entries - send no parameter
                value = self.value["generator"]()
            else:
                # Send the dictionary as a parameter
                value = self.value["generator"](self.value)
        else:
            value = self.value

        if re.search("^--%s$" % re.escape(boundary), value, re.M):
            raise ValueError("boundary found in encoded string")

        return "%s%s\r\n" % (self.encode_hdr(boundary), value)

    #--------------------------------------------------------------------------#
    def iter_encode(self, boundary, blocksize=4096):
        """
        @brief Yields the encoding of this parameter
        @param boundary string MIME boundary to use
        @param blocksize integer size of chunks of files to yield
        @return generator of strings
        
        If self.fileobj is set, then blocks of ``blocksize`` bytes are read and
        yielded.

        The callable cb is called on restarting after each yield if present.

        If there is a digester defined, it is fed each block of the
        corresponding fileobj as it is read.

        Plain value parameters are handed off to the encode method

        Fileobj chunks are checked to ensure they don't contain the encoded
        boundary string.  There has to be some clever jiggery pokery to
        ensure that a match with the encoded boundary isn't missed because
        it spans the break between two chunks. This is done by keeping the
        the last part of the previous block (to the length of the encoded
        boundary) and adding to the fron of the new block before  checking
        for a match.
        """
        total = self.get_size(boundary)
        current = 0
        if self.value is not None:
            block = self.encode(boundary)
            current += len(block)
            yield block
            if self.cb:
                self.cb(self, current, total)
        else:
            block = self.encode_hdr(boundary)
            current += len(block)
            yield block
            if self.cb:
                self.cb(self, current, total)
            last_block = ""
            encoded_boundary = "--%s" % encode_and_quote(boundary)
            boundary_exp = re.compile("^%s$" % re.escape(encoded_boundary),
                                      re.M)
            while True:
                block = self.fileobj.read(blocksize)
                if not block:
                    current += 2
                    if self.digester is not None:
                        self.digester.finalize_digest()
                    yield "\r\n"
                    if self.cb:
                        self.cb(self, current, total)
                    break
                last_block += block
                if boundary_exp.search(last_block):
                    raise ValueError("boundary found in file data")
                if self.digester is not None:
                    self.digester.update_digest(block)
                last_block = last_block[-len(encoded_boundary)-2:]
                current += len(block)
                yield block
                if self.cb:
                    self.cb(self, current, total)

    #--------------------------------------------------------------------------#
    def get_size(self, boundary):
        """
        @brief Returns the size in bytes that this param will be when encoded
               with the given boundary.
        @param boundary string boundary to be used
        @return integer length of encoded parameter.
        """
        if self.filesize is not None:
            valuesize = self.filesize
        elif type(self.value) == dict:
            valuesize = self.value["length"]
        else:
            valuesize = len(self.value)

        return len(self.encode_hdr(boundary)) + 2 + valuesize

    #--------------------------------------------------------------------------#
    def get_digest(self):
        """
        @brief Accessor for generated digest if there is one
        @return previously generated digest or None
        """
        if self.digester is None:
            return None
        else:
            return self.digester.get_digest()

    #--------------------------------------------------------------------------#
    def get_url(self):
        """
        @brief Accessor for url if there is one
        @return previously generated url or None
        """
        if self.digester is None:
            return None
        else:
            return self.digester.get_url()

#==============================================================================#
#==== Global Functions ====
        
def encode_string(boundary, name, value):
    """
    @brief Returns encoded multipart/form-data for name and value with boundary
    @param boundary string MIME boundary string to use
    @param name string name of parameter to be encoded
    @param value any of possible types for MultipartParam
    @return string with encoded value
    """

    return MultipartParam(name, value).encode(boundary)

#------------------------------------------------------------------------------#
def encode_file_header(boundary, paramname, filesize, filename=None,
                       filetype=None):
    """
    @brief Returns the leading data for a multipart/form-data field that
           contains file data.
    @param boundary string MIME boundary used throughout a single request to
                           separate variables.
    @param paramname string name of the variable in this request.
    @param filesize integer is the size of the file data.
    @param filename string if specified is the filename to give to this field.  This
                        This field is only useful to the server for determining
                        the original filename.
    @param filetype string if specified is the MIME type of this file.

    The actual file data should be sent after this header has been sent.
    """

    return MultipartParam(paramname, filesize=filesize, filename=filename,
            filetype=filetype).encode_hdr(boundary)

#------------------------------------------------------------------------------#
def get_body_size(params, boundary):
    """
    @brief Returns the length in octets that the multipart/form-data encoding
           of ``params`` will be.
    @param params iterable suitable for feeding to MultipartParams.from_params
    @param boundary string MIME boundary to use
    @return integer length of encoded parameter set
    """
    
    size = sum(p.get_size(boundary) for p in MultipartParam.from_params(params))
    # Allow for trailing '--CRLFCRLF'
    return size + len(boundary) + 6

#------------------------------------------------------------------------------#
def get_headers(params, boundary):
    """
    @brief Returns a dictionary with Content-Type and Content-Length headers
           for the multipart/form-data encoding of ``params``.
    @param params iterable suitable for feeding to MultipartParams.from_params
    @param boundary string MIME boundary to use
    @return dictionary with headers
    """
    headers = {}
    boundary = urllib.quote_plus(boundary)
    headers['Content-Type'] = "multipart/form-data; boundary=%s" % boundary
    headers['Content-Length'] = str(get_body_size(params, boundary))
    return headers

#==============================================================================#
class multipart_yielder:
    """
    @brief Class that acts as an iterator to deliver the encoded parameters
           of a set of form parameters that can be encoded as MultipartParams.
    """
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    ##@var params
    # list of instances of MultipartParam

    ##@var boundary
    # string MIME boundary to use

    ##@var cb
    # callable which will be called from next with three
    # arguments(self, current, total), representing the current parameter,
    # current amount transferred, and the total size.  This is done before
    # each chunk of the paramter is yielded in the iterator.  The callable
    # does not return a value. (Note minor difference with cb in
    # MultipartParam.)

    ##@var i
    # integer index of item in params currently being encoded

    ##@var p
    # instance of MultipartParam at position i in params

    ##@var param_iter
    # iterator for current instance of MultipartParam (in p)

    ##@var current
    # integer current position in file object being encoded

    ##@var total
    # integer size of body of complete set of encoded params
    
    def __init__(self, params, boundary, cb):
        """
        @brief Constructor - record parameters and initialise total as body size.
        @param params list of instances of MultipartParam
        @param boundary string MIME boundary to use
        @param cb callable which will be called defore each block is yielded

        Record parameters.
        Initialize  iteration variables and get expected total size of body.
        """
        self.params = params
        self.boundary = boundary
        self.cb = cb

        self.i = 0
        self.p = None
        self.param_iter = None
        self.current = 0
        self.total = get_body_size(params, boundary)

    #--------------------------------------------------------------------------#
    def __iter__(self):
        """
        @brief The class instance is itself an iterator (has next method)
        @return self
        """
        return self

    #--------------------------------------------------------------------------#
    def next(self):
        """
        @brief generator function to yield multipart/form-data representation
               of parameters
        @return chunks of current paramer, iterating through all of params

        Calls cb is not None just before returning next chunk
        """
        if self.param_iter is not None:
            try:
                block = self.param_iter.next()
                self.current += len(block)
                if self.cb:
                    self.cb(self.p, self.current, self.total)
                return block
            except StopIteration:
                self.p = None
                self.param_iter = None

        if self.i is None:
            raise StopIteration
        elif self.i >= len(self.params):
            self.param_iter = None
            self.p = None
            self.i = None
            block = "--%s--\r\n" % self.boundary
            self.current += len(block)
            if self.cb:
                self.cb(self.p, self.current, self.total)
            return block

        self.p = self.params[self.i]
        self.param_iter = self.p.iter_encode(self.boundary)
        self.i += 1
        return self.next()

    #--------------------------------------------------------------------------#
    def reset(self):
        """
        @brief reset the current parameter iterator
        """
        self.i = 0
        self.current = 0
        for param in self.params:
            param.reset()

#==============================================================================#
def multipart_encode(params, boundary=None, cb=None):
    """
    @brief Encode ``params`` as multipart/form-data.

    @param params - either a sequence of
                     - (name, value) pairs, or
                     - MultipartParam objects,
                  - or a mapping of names to values.
                  Values are either strings parameter values, dictionaries, or
                  file-like objects to use as the parameter value.  The
                  file-like objects must support .read() and either
                  .fileno() or both .seek() and .tell().

    @param boundary string If set, used as the MIME boundary.
                           Otherwise a randomly generated boundary will be used.
                           In either case, if the boundary string appears in the
                           parameter values a ValueError will be raised.

    @param cb callable  If set, it is a callback which will get called as blocks
                        of data are encoded.  It will be called with
                        (param, current, total), indicating the current
                        parameter being encoded, the current amount encoded,
                        and the total amount to encode.

    @return a tuple of `datagen`, `headers`, where `datagen` is a
            generator that will yield blocks of data that make up the encoded
            parameters, and `headers` is a dictionary with the assoicated
            Content-Type and Content-Length headers.

    Examples:

    @code
    >>> datagen, headers = multipart_encode( [("key", "value1"), ("key", "value2")] )
    >>> s = "".join(datagen)
    >>> assert "value2" in s and "value1" in s

    >>> p = MultipartParam("key", "value2")
    >>> datagen, headers = multipart_encode( [("key", "value1"), p] )
    >>> s = "".join(datagen)
    >>> assert "value2" in s and "value1" in s

    >>> datagen, headers = multipart_encode( {"key": "value1"} )
    >>> s = "".join(datagen)
    >>> assert "value2" not in s and "value1" in s
    @endcode
    """
    if boundary is None:
        boundary = gen_boundary()
    else:
        boundary = urllib.quote_plus(boundary)

    headers = get_headers(params, boundary)
    params = MultipartParam.from_params(params)

    return multipart_yielder(params, boundary, cb), headers

#==============================================================================#
# ==== Test Code ====
if __name__ == "__main__":
    from StringIO import StringIO
    import base64
    datagen, headers = multipart_encode( [("key", "value1"), ("key", "value2")] )
    s = "".join(datagen)
    print s
    assert "value2" in s and "value1" in s

    p = MultipartParam("key", "value2")
    datagen, headers = multipart_encode( [("key", "value1"), p] )
    s = "".join(datagen)
    print s
    assert "value2" in s and "value1" in s

    datagen, headers = multipart_encode( {"key": "value1"} )
    s = "".join(datagen)
    print s
    assert "value2" not in s and "value1" in s

    def test_dict(d):
        return "Key a - %s - Key b - %s" % (d["a"], d["b"])

    td = { "generator": test_dict, "length": 27, "a": "alpha", "b": "beta"}
    datagen, headers = multipart_encode( [("test_dict", td)])
    s = "".join(datagen)
    print s
    assert "Key a - alpha - Key b - beta" in s

    def test_digest(d):
        return base64.urlsafe_b64encode(d["execute"]())

    s = "Test file data"
    f = StringIO(s)

    dg = ParamDigester()
    dg.set_algorithm("sha-256", hashlib.sha256)
    digest_parm = MultipartParam("digest", fileobj=f, filename="str", digester=dg)

    te = { "generator": test_digest, "length": 43, "execute": digest_parm.get_digest }
    tf = { "generator": digest_parm.get_digest, "length": 43 }
    datagen, headers = multipart_encode( [digest_parm,
                                          ("test_dict1 - ascii digest", te),
                                          ("test_dict2 - binary", tf)])
    s = "".join(datagen)
    print s
    assert "-PZJemkhZSYuYuDZgZJHKd5cTCbVE0xWDyMvAC0mfu0=" in s


