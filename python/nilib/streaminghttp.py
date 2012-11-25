"""
@package nilib
@file streaminghttp.py
@brief Streaming HTTP uploads module.
@version $Revision: 0.9 $ $Author: Chris Atlee and Elwyn Davies $

Copyright (c) 2011 Chris AtLee

Copyright (c) 2012 Trinity College Dublin/Folly Consulting Ltd

    This version of this module is incorporated in the NI URI library
    developed as part of the SAIL project. (http://sail-project.eu)

    Specification(s) - note, versions may change
          - http://tools.ietf.org/html/draft-farrell-decade-ni-10
          - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03
          - http://tools.ietf.org/html/draft-kutscher-icnrg-netinf-proto-00

Ths module is a slightly modified version of part of the 'poster' software 
written by Chris Atlee.  The changes are in the documentation rather than the
code. The original code is available at
            http://atlee.ca/software/poster/index.html

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

This module extends the standard httplib and urllib2 objects so that
iterable objects can be used in the body of HTTP requests.

In most cases all one should have to do is call :func:`register_openers()`
to register the new streaming http handlers which will take priority over
the default handlers, and then you can use iterable objects in the body
of HTTP requests.

**N.B.** You must specify a Content-Length header if using an iterable object
since there is no way to determine in advance the total size that will be
yielded, and there is no way to reset an iterator.

Example usage:
@code

>>> from StringIO import StringIO
>>> import urllib2, poster.streaminghttp

>>> opener = poster.streaminghttp.register_openers()

>>> s = "Test file data"
>>> f = StringIO(s)

>>> req = urllib2.Request("http://localhost:5000", f,
...                       {'Content-Length': str(len(s))})
@endcode
"""

#==============================================================================#
import httplib, urllib2, socket
from httplib import NotConnected

#==============================================================================#
__all__ = ['StreamingHTTPConnection', 'StreamingHTTPRedirectHandler',
        'StreamingHTTPHandler', 'register_openers']

if hasattr(httplib, 'HTTPS'):
    __all__.extend(['StreamingHTTPSHandler', 'StreamingHTTPSConnection'])

#==============================================================================#
class _StreamingHTTPMixin:
    """
    @brief Mixin class for HTTP and HTTPS connections that implements a
           streaming send method.
    """
    #--------------------------------------------------------------------------#
    def send(self, value):
        """
        @brief Send ``value`` to the server.
        @param value string object, a file-like object that supports
                     a .read() method, or an iterable object that
                     supports a .next() method.
        @return void
        """
        # Based on python 2.6's httplib.HTTPConnection.send()
        if self.sock is None:
            if self.auto_open:
                self.connect()
            else:
                raise NotConnected()

        # send the data to the server. if we get a broken pipe, then close
        # the socket. we want to reconnect when somebody tries to send again.
        #
        # NOTE: we DO propagate the error, though, because we cannot simply
        #       ignore the error... the caller will know if they can retry.
        if self.debuglevel > 0:
            print "send:", repr(value)
        try:
            blocksize = 8192
            if hasattr(value, 'read') :
                if hasattr(value, 'seek'):
                    value.seek(0)
                if self.debuglevel > 0:
                    print "sendIng a read()able"
                data = value.read(blocksize)
                while data:
                    self.sock.sendall(data)
                    data = value.read(blocksize)
            elif hasattr(value, 'next'):
                if hasattr(value, 'reset'):
                    value.reset()
                if self.debuglevel > 0:
                    print "sendIng an iterable"
                for data in value:
                    self.sock.sendall(data)
            else:
                self.sock.sendall(value)
        except socket.error, v:
            if v[0] == 32:      # Broken pipe
                self.close()
            raise

#==============================================================================#
class StreamingHTTPConnection(_StreamingHTTPMixin, httplib.HTTPConnection):
    """
    @brief Subclass of `httplib.HTTPConnection` that overrides the `send()`
    method to support iterable body objects"""

#==============================================================================#
class StreamingHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
    """
    @brief Subclass of `urllib2.HTTPRedirectHandler` that overrides the
          `redirect_request` method to properly handle redirected POST
           requests

    This class is required because python 2.5's HTTPRedirectHandler does
    not remove the Content-Type or Content-Length headers when requesting
    the new resource, but the body of the original request is not preserved.
    """

    #--------------------------------------------------------------------------#
    handler_order = urllib2.HTTPRedirectHandler.handler_order - 1

    #--------------------------------------------------------------------------#
    # From python2.6 urllib2's HTTPRedirectHandler
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """
        @brief Handle a redirected request
        @param req object request
        @param fp file-like object from which response body might be read
        @param code HTTP status code indicating kind of redirect
        @param msg message that arrived with code
        @param headers
        @param newurl string target of redirection
        @return a Request or None in response to the redirect.

        This is called by the http_error_30x methods when a
        redirection response is received.  If a redirection should
        take place, return a new Request to allow http_error_30x to
        perform the redirect.  Otherwise, raise HTTPError if no-one
        else should try to handle this url.  Return None if you can't
        but another Handler might.
        """
        m = req.get_method()
        if (code in (301, 302, 303, 307) and m in ("GET", "HEAD")
            or code in (301, 302, 303) and m == "POST"):
            # Strictly (according to RFC 2616), 301 or 302 in response
            # to a POST MUST NOT cause a redirection without confirmation
            # from the user (of urllib2, in this case).  In practice,
            # essentially all clients do redirect in this case, so we
            # do the same.
            # be conciliant with URIs containing a space
            newurl = newurl.replace(' ', '%20')
            newheaders = dict((k, v) for k, v in req.headers.items()
                              if k.lower() not in (
                                  "content-length", "content-type")
                             )
            return urllib2.Request(newurl,
                           headers=newheaders,
                           origin_req_host=req.get_origin_req_host(),
                           unverifiable=True)
        else:
            raise urllib2.HTTPError(req.get_full_url(), code, msg, headers, fp)

#==============================================================================#
class StreamingHTTPHandler(urllib2.HTTPHandler):
    """
    @brief Subclass of `urllib2.HTTPHandler` that uses
           StreamingHTTPConnection as its http connection class.
    """

    handler_order = urllib2.HTTPHandler.handler_order - 1

    #--------------------------------------------------------------------------#
    def http_open(self, req):
        """
        @brief Open a StreamingHTTPConnection for the given request
        @param req object request to be sent
        @return connection for request to be sent
        """
        return self.do_open(StreamingHTTPConnection, req)

    #--------------------------------------------------------------------------#
    def http_request(self, req):
        """
        @brief Canonicalize a HTTP request by checking headers are correct etc.
        @param req object request to be sent
        @return canonicalized request
        
        Make sure that Content-Length is specified
        if we're using an interable value

        Call superclass to process the request
        """
        # Make sure that if we're using an iterable object as the request
        # body, that we've also specified Content-Length
        if req.has_data():
            data = req.get_data()
            if hasattr(data, 'read') or hasattr(data, 'next'):
                if not req.has_header('Content-length'):
                    raise ValueError(
                            "No Content-Length specified for iterable body")
        return urllib2.HTTPHandler.do_request_(self, req)

#==============================================================================#
if hasattr(httplib, 'HTTPS'):
    #==========================================================================#
    class StreamingHTTPSConnection(_StreamingHTTPMixin,
            httplib.HTTPSConnection):
        """
        @brief Subclass of `httplib.HTTSConnection` that overrides the `send()`
               method to support iterable body objects
        """

    #==========================================================================#
    class StreamingHTTPSHandler(urllib2.HTTPSHandler):
        """
        @brief Subclass of `urllib2.HTTPSHandler` that uses
               StreamingHTTPSConnection as its http connection class.
        """

        handler_order = urllib2.HTTPSHandler.handler_order - 1

        #----------------------------------------------------------------------#
        def https_open(self, req):
            """
            @brief Open a streaming connection for an HTTPS request
            @param req object to be sent
            @return connection object
            """
            return self.do_open(StreamingHTTPSConnection, req)

        #----------------------------------------------------------------------#
        def https_request(self, req):
            """
            @brief Handle an HTTPS request
            @param req object to be sent
            @return response object
            
            Make sure that if we're using an iterable object as the request
            body, that we've also specified Content-Length
            """
            if req.has_data():
                data = req.get_data()
                if hasattr(data, 'read') or hasattr(data, 'next'):
                    if not req.has_header('Content-length'):
                        raise ValueError(
                                "No Content-Length specified for iterable body")
            return urllib2.HTTPSHandler.do_request_(self, req)

#==============================================================================#
def get_handlers():
    """
    @brief Return the list of handlers declated by this module
    @return list of handlers
    """
    handlers = [StreamingHTTPHandler, StreamingHTTPRedirectHandler]
    if hasattr(httplib, "HTTPS"):
        handlers.append(StreamingHTTPSHandler)
    return handlers
    
#------------------------------------------------------------------------------#
def register_openers():
    """
    @brief Register the streaming http handlers in the global urllib2 default
           opener object.

    @return the created OpenerDirector object.
    """
    opener = urllib2.build_opener(*get_handlers())

    urllib2.install_opener(opener)

    return opener
#==============================================================================#
