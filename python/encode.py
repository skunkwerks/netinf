"""
@package ni
@file encode.py
@brief Multipart/form-data encoding module.
@version $Revision: 0.8.2 $ $Author: Chris Atlee $

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

__all__ = ['gen_boundary', 'encode_and_quote', 'ParamDigester', 'MultipartParam',
        'encode_string', 'encode_file_header', 'get_body_size', 'get_headers',
        'multipart_yielder', 'multipart_encode']

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

def encode_and_quote(data):
    """
    @brief Depending on whether data is unicode or otherwise, encode and quote appropriately.
    @return If data is unicode: return urllib.quote_plus(data.encode("utf-8"))
    @return Otherwise:          return urllib.quote_plus(data)
    """
    if data is None:
        return None

    if isinstance(data, unicode):
        data = data.encode("utf-8")
    return urllib.quote_plus(data)

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

class ParamDigester:
    """
    @briefBase class to wrap up a digest mechanism to be used while sending a file
    @brief to an HTTP server.  Helper class for MultipartParam.

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
    def __init__(self):
        """
        @brief Constructor - Initialises instance variables
        """
        self.algorithm = None
        self.digest = None
        self.hash_function = None
        return

    def set_algorithm(self, alg_name= "", digester=None):
        """
        @brief Initializes digester and sets up context for digestion.
        @param alg_name - str Textual name of algorithm
        @param digester callable digest function from hashlib
        """
        self.algorithm = alg_name
        self.hash_function = digester()
        return

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

    def get_digest(self):
        """
        @brief Access previously generated digest
        @return digest string
        """
        return self.digest

    def __repr__(self):
        """
        @param Python standard string representation output
        @return suitable representation string
        """
        return "Digest algorithm: %s; Value: %s" % (str(self.algorithm),
                                                    str(self.digest))
        
class MultipartParam(object):
    """
    @brief Represents a single parameter in a multipart/form-data request

    ``name`` is the name of this parameter.

    If ``value`` is set, it must be either a string or unicode object to use as the
    data for this parameter or a dictionary that contains a ``generator`` key.
    In the dictionary case the value of the generator key must be a callable
    which generates a string or unicode object value that can be used as data.
    When the value for a dictionary is to be encoded, the ``generator`` callable
    is called with the dictionary as a parameter. Because the serialization process
    precalculates the length of the set of parameters, the dictionary must
    also contain a (fixed value)length field that will be the length of the value.

    If ``filename`` is set, it is what to say that this parameter's filename
    is.  Note that this does not have to be the actual filename of any local file.

    If ``filetype`` is set, it is used as the Content-Type for this parameter.
    If unset it defaults to "text/plain; charset=utf8"

    If ``filesize`` is set, it specifies the length of the file ``fileobj``

    If ``fileobj`` is set, it must be a file-like object that supports
    .read().

    Both ``value`` and ``fileobj`` must not be set, doing so will
    raise a ValueError assertion.

    If ``fileobj`` is set, and ``filesize`` is not specified, then
    the file's size will be determined first by stat'ing ``fileobj``'s
    file descriptor, and if that fails, by seeking to the end of the file,
    recording the current position as the size, and then by seeking back to the
    beginning of the file.

    ``cb`` is a callable which will be called from iter_encode with (self,
    current, total), representing the current parameter, current amount
    transferred, and the total size.

    ``digester`` is an instance of a class derived from ParamDigester.
    If not None, it will be used in conjunction with a fileobj to generate
    a digest for the file that may be sent across the wire as (part of)
    another form parameter.
    
    """
    def __init__(self, name, value=None, filename=None, filetype=None,
                        filesize=None, fileobj=None, cb=None, digester=None):
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

    def __cmp__(self, other):
        attrs = ['name', 'value', 'filename', 'filetype', 'filesize', 'fileobj', 'digester']
        myattrs = [getattr(self, a) for a in attrs]
        oattrs = [getattr(other, a) for a in attrs]
        return cmp(myattrs, oattrs)

    def reset(self):
        if self.fileobj is not None:
            self.fileobj.seek(0)
        elif self.value is None:
            raise ValueError("Don't know how to reset this parameter")

    @classmethod
    def from_file(cls, paramname, filename):
        """Returns a new MultipartParam object constructed from the local
        file at ``filename``.

        ``filesize`` is determined by os.path.getsize(``filename``)

        ``filetype`` is determined by mimetypes.guess_type(``filename``)[0]

        ``filename`` is set to os.path.basename(``filename``)
        """

        return cls(paramname, filename=os.path.basename(filename),
                filetype=mimetypes.guess_type(filename)[0],
                filesize=os.path.getsize(filename),
                fileobj=open(filename, "rb"))

    @classmethod
    def from_params(cls, params):
        """Returns a list of MultipartParam objects from a sequence of
        name, value pairs, MultipartParam instances,
        or from a mapping of names to values

        The values may be strings or file objects, or MultipartParam objects.
        MultipartParam object names must match the given names in the
        name,value pairs or mapping, if applicable."""
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

    def encode_hdr(self, boundary):
        """Returns the header of the encoding of this parameter"""
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

    def encode(self, boundary):
        """Returns the string encoding of this parameter"""
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

    def iter_encode(self, boundary, blocksize=4096):
        """Yields the encoding of this parameter
        If self.fileobj is set, then blocks of ``blocksize`` bytes are read and
        yielded."""
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

    def get_size(self, boundary):
        """Returns the size in bytes that this param will be when encoded
        with the given boundary."""
        if self.filesize is not None:
            valuesize = self.filesize
        elif type(self.value) == dict:
            valuesize = self.value["length"]
        else:
            valuesize = len(self.value)

        return len(self.encode_hdr(boundary)) + 2 + valuesize

    def get_digest(self):
        """
        @brief Accessor for generated digest if there is one
        @return previously generated digest or None
        """
        if self.digester is None:
            return None
        else:
            return self.digester.get_digest()

    def get_url(self):
        """
        @brief Accessor for url if there is one
        @return previously generated url or None
        """
        if self.digester is None:
            return None
        else:
            return self.digester.get_url()

def encode_string(boundary, name, value):
    """Returns ``name`` and ``value`` encoded as a multipart/form-data
    variable.  ``boundary`` is the boundary string used throughout
    a single request to separate variables."""

    return MultipartParam(name, value).encode(boundary)

def encode_file_header(boundary, paramname, filesize, filename=None,
        filetype=None):
    """Returns the leading data for a multipart/form-data field that contains
    file data.

    ``boundary`` is the boundary string used throughout a single request to
    separate variables.

    ``paramname`` is the name of the variable in this request.

    ``filesize`` is the size of the file data.

    ``filename`` if specified is the filename to give to this field.  This
    field is only useful to the server for determining the original filename.

    ``filetype`` if specified is the MIME type of this file.

    The actual file data should be sent after this header has been sent.
    """

    return MultipartParam(paramname, filesize=filesize, filename=filename,
            filetype=filetype).encode_hdr(boundary)

def get_body_size(params, boundary):
    """Returns the number of bytes that the multipart/form-data encoding
    of ``params`` will be."""
    size = sum(p.get_size(boundary) for p in MultipartParam.from_params(params))
    return size + len(boundary) + 6

def get_headers(params, boundary):
    """Returns a dictionary with Content-Type and Content-Length headers
    for the multipart/form-data encoding of ``params``."""
    headers = {}
    boundary = urllib.quote_plus(boundary)
    headers['Content-Type'] = "multipart/form-data; boundary=%s" % boundary
    headers['Content-Length'] = str(get_body_size(params, boundary))
    return headers

class multipart_yielder:
    def __init__(self, params, boundary, cb):
        self.params = params
        self.boundary = boundary
        self.cb = cb

        self.i = 0
        self.p = None
        self.param_iter = None
        self.current = 0
        self.total = get_body_size(params, boundary)

    def __iter__(self):
        return self

    def next(self):
        """generator function to yield multipart/form-data representation
        of parameters"""
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

    def reset(self):
        self.i = 0
        self.current = 0
        for param in self.params:
            param.reset()

def multipart_encode(params, boundary=None, cb=None):
    """Encode ``params`` as multipart/form-data.

    ``params`` should be a sequence of (name, value) pairs or MultipartParam
    objects, or a mapping of names to values.
    Values are either strings parameter values, or file-like objects to use as
    the parameter value.  The file-like objects must support .read() and either
    .fileno() or both .seek() and .tell().

    If ``boundary`` is set, then it as used as the MIME boundary.  Otherwise
    a randomly generated boundary will be used.  In either case, if the
    boundary string appears in the parameter values a ValueError will be
    raised.

    If ``cb`` is set, it should be a callback which will get called as blocks
    of data are encoded.  It will be called with (param, current, total),
    indicating the current parameter being encoded, the current amount encoded,
    and the total amount to encode.

    Returns a tuple of `datagen`, `headers`, where `datagen` is a
    generator that will yield blocks of data that make up the encoded
    parameters, and `headers` is a dictionary with the assoicated
    Content-Type and Content-Length headers.

    Examples:

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

    """
    if boundary is None:
        boundary = gen_boundary()
    else:
        boundary = urllib.quote_plus(boundary)

    headers = get_headers(params, boundary)
    params = MultipartParam.from_params(params)

    return multipart_yielder(params, boundary, cb), headers
###########################
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


