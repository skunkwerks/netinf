#!/usr/bin/python
"""
@package nilib
@file wsgishim.py
@brief Request handler shim for  NI NetInf HTTP convergence layer (CL) server
@brief and NRS server.  Shim to link the mod_wsgi application with
@brief NIHTTPRequestHandler.
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
wsgishim.py overview

This module defines a version of the HTTPRequestShim class that links the
standard mod_wsgi with NIHTTPRequestHandler in nihandler.py so that requests
coming through Apache can be processed using the same module as used with
BaseHTTPServer/BaseHTTPRequestHandler.

The main functions of the shim are:
- to provide a common way of accessing the various instance variables listed
  independent of how the information is supplied by the server that invokes the
  handler,
- to extract values from the environ dictionary using appropriate keys
  corresponding to instance variables expected by NIHTTPRequestHandler (with
  several of the assignments defined by BaseHTTPRequestHandler and
  StreamRequestHandler),
- to provide the equivalent functionality to Handle and HandleOneRequest
  methods in BaseHTTPRequestHandler, 
- to set up uniform logging capabilities, and
- to provide a uniform interface to the generation of the response body for a
  request.

The handler expects to have the following instance variables set up:

1) As expected in any handler derived from BaseHTTPRequestHandler
   - server_port      the TCP port used by the HTTP server listener (default 8080)
   - server_name      the hostname part of the address of the HTTP server
   - authority        Combination of server_name and server_port as expected in
                      netloc portion of a URL.
   - command          the operation in the HTTP request
   - path             the path portion plus query and fragments of the request
   - rfile            file representing input request stream positioned after
                      any request headers have been read.
   - default_error_message
                   template for error response HTML sent by send_error.  
[Note: BaseHTTPRequestHandler provides some extra items that are not currently
 used by nihandler.py.  If these are pressed into use, they may have to be
 emulated in the WSGI shim case. These include: requestline, raw_requestline,
 request_version, client_address.
 **** See note below regarding wfile which should not be used.****]
                  
2) Specific items controlled by Apache/mod_wsgi configuration variables if
   using mod_wsgi or alternatively can be inserted into WSGI environ dictionary
   before invoking handler:
   - storage_root     the base directory where the content cache is stored
   - getputform       pathname for a file containing the HTML code uploaded to
                      show the NetInf GET/PUBLISH/SEARCH forms in a browser
   - nrsform          pathname for file containing the HTML code uploaded to show
                      the NetInf NRS configuration forms in a browser
   - favicon          pathname for favicon file sent to browsers for display.
   - provide_nrs      flag indicating if NRS operations should be supported by
                      this server
-    redis_nrs        REDIS server connection (None if provide_nrs is False) -
                      doesn't need a configuration variable - set up dynamically.
Corresponding Apache environment variables:
SetEnv NETINF_STORAGE_ROOT <directory path>
SetEnv NETINF_GETPUTFORM <file path name>
SetEnv NETINF_NRSFORM <file path name>
SetEnv NETINF_FAVICON <file path name>
SetEnv NETINF_PROVIDE_NRS <boolean> [yes/true/1|no/false/0]

3) Convenience functions to provide logging functions at various informational
   levels (each takes a string to be logged).  The resulting string is fed
   to the Apache logger by writing to environ["esgi.errors"]:
   - logdebug
   - logerror
   - logwarn
   - loginfo

4) The following routines are used to wrap the sending of strings and whole
   files as part of a response.  This is done so that self.wfile does not appear
   explicitly in the nihandler.py code so that the same interface can be used
   for the BaseHTTPRequestHandler shim.  The responses are acumulated for
   delivery via an iterable rather than being written directly to a 'file' as is
   the case with directHTTPRequestShim and BaseHTTPRequestHandler.
   - send_string
   - send_file

The handler expects the following standard methods in BaseHTTPRequestHandler to be available:
- date_time_string Date/time string when request processed
- send_error       Send an HTTP error code and message as response
- headers          Dictionary like accessor for request headers
- send_request     Send an HTTP (success) code and message as first part of response
- send_header      Send a single header as part of response
- end_headers      Send header terminator (blank) line as part of response
These routines build a list of headers to send and items to be fed to the
response iterator.

@code
Revision History
================
Version   Date       Author         Notes
1.0       24/11/2012 Elwyn Davies   Renamed HTTPRequestShim to
                                    wsgiHTTPRequestShim to satisfy Doxygen.
0.0       19/11/2012 Elwyn Davies   Split out from niserver.py and adapted to
                                    allow use with either WSGI or
                                    BaseHTTPRequestHandler.

@endcode
"""

#==============================================================================#
#=== Standard modules for Python 2.[567].x distributions ===
import sys
import logging
import types
import time
import random

##@var redis_loaded
# Flag indicating if it was possible to load the Redis module.
# The program can do without Redis if not providing NRS services.
try:
    import redis
    redis_loaded = True
except ImportError:
    redis_loaded = False

#=== Local package modules ===

from netinf_ver import NETINF_VER, NISERVER_VER

#==============================================================================#
# List of classes/global functions in file
__all__ = ['wsgiHTTPRequestShim', 'HeaderDict']

#==============================================================================#
# === GLOBAL CONSTANTS AND VARIABLES ===

##@var WSGI_HTTP_HEADER_MAP
# Map from environment variables representing request header values
# as passed from WSGI with values that are the correseponding W3C
# HTTP header names in lower case.  These are used to convert from
# the environ dictionary passed into the WSGI application back into
# a dictionary of header values that can be used for code written
# using the W3C names (as with the nihandler). 
WSGI_HTTP_HEADER_MAP = {
    "HTTP_ACCEPT": "accept",
    "HTTP_ACCEPT_CHARSET": "accept-charset",
    "HTTP_ACCEPT_ENCODING": "accept-encoding",
    "HTTP_ACCEPT_LANGUAGE": "accept-language",
    "HTTP_ACCEPT_DATETIME": "accept-datetime",
    "HTTP_AUTHORIZATION": "authorization",
    "HTTP_CACHE_CONTROL": "cache-control",
    "HTTP_CONNECTION": "connection",
    "HTTP_COOKIE": "cookie",
    "HTTP_CONTENT_MD5": "content-md5",
    "HTTP_DATE": "date",
    "HTTP_EXPECT": "expect",
    "HTTP_FROM": "from",
    "HTTP_HOST": "host",
    "HTTP_IF_MATCH": "if-match",
    "HTTP_IF_MODIFIED_SINCE": "if-modified-since",
    "HTTP_IF_NONE_MATCH": "if-none-match",
    "HTTP_IF_RANGE": "if-range",
    "HTTP_IF_UNMODIFIED_SINCE": "if-unmodified-since",
    "HTTP_KEEP_ALIVE": "keep-alive",
    "HTTP_MAX_FORWARDS": "max-forwards",
    "HTTP_PRAGMA": "pragma",
    "HTTP_PROXY_AUTHORIZATION": "proxy-authorization",
    "HTTP_RANGE": "range",
    "HTTP_REFERER": "referer",
    "HTTP_TE": "te",
    "HTTP_UPGRADE": "upgrade",
    "HTTP_USER_AGENT": "user-agent",
    "HTTP_VIA": "via",
    "HTTP_WARNING": "warning",
    "HTTP_X_REQUESTED_WITH</TD>": "x-requested-with</td>",
    "HTTP_DNT": "dnt",
    "HTTP_X_FORWARDED_FOR": "x-forwarded-for",
    "HTTP_X_FORWARDED_PROTO": "x-forwarded-proto",
    "HTTP_FRONT_END_HTTPS": "front-end-https",
    "HTTP_X_ATT_DEVICEID": "x-att-deviceid",
    "HTTP_X_WAP_PROFILE": "x-wap-profile",
    "HTTP_PROXY_CONNECTION": "proxy-connection",
    "CONTENT_LENGTH": "content-length",
    "CONTENT_TYPE": "content-type"
}

##@var WSGI_OTHER_ENV_MAP
# Various other WSGI environment variables that might be of interest
WSGI_OTHER_ENV_MAP = {
    "GATEWAY_INTERFACE": "gateway-interface",
    "PATH_INFO": "path-info",
    "QUERY_STRING": "query-string",
    "REMOTE_ADDR": "remote-addr",
    "REMOTE_HOST": "remote-host",
    "REQUEST_METHOD": "request-method",
    "SCRIPT_NAME": "script-name",
    "SERVER_NAME": "server-name",
    "SERVER_PORT": "server-port",
    "SERVER_PROTOCOL": "server-protocol",
    "SERVER_SOFTWARE": "server-software",
}
##@var HTTP_WSGI_HEADER_MAP
# Dynamically created inverse map to WSGI_HTTP_HEADER_MAP.
HTTP_WSGI_HEADER_MAP = {}
for k in WSGI_HTTP_HEADER_MAP:
    HTTP_WSGI_HEADER_MAP[WSGI_HTTP_HEADER_MAP[k]] = k

#==============================================================================#
class HeaderDict:
    """
    @brief Pseudo-dictionary used to map the WSGI environ into an HTTP
           headers dictionary.

    Tries to minimize the effort of scanning the whole environ dictionary.
    which is pretty large, to extract all the entries that correspond to
    W3C HTTP headers.  This is the keys that start with HTTP_ plus
    two special cases CONTENT_LNGTH and CONTENT_TYPE.

    The HTTP_ keys are generated by upper casing the W3C name and translating
    any puntuation to underscores (basically this only affects hyphens in the
    W3C header names.

    The optimization is intended to work by looking up the equivalent CGI
    name in environ.  This only applies to __getitem__ and get which is the
    main operation that is used in the nihandler. If any of the operations that
    look at the whole set of headers (e.g., len) a complete dictionary is
    constructed and used subsequently.

    Note that the headers would not necessarily be quite as in the original
    request because if there are multiple headers of the same name in the
    request CGI combines them into a single string.  In practice this is
    a non-issue because muliple headers are almost non-existent.
    """
    
    #--------------------------------------------------------------------------#
    # === INSTANCE VARIABLES ===

    ##@var environ
    # dictionary environ dictionary as supplied to constructor
    
    ##@var dict
    # dictionary indexed by W3C HTTP header names with values taken from environ.

    ##@var headers
    # array of strings resconstructed lines from request "key: value" 
    
    #--------------------------------------------------------------------------#
    def __init__(self, environ):
        """
        @brief Constructor - records supplied environ dictionary
        @param environ dictionary with all CGI key/values.
        """
        self.environ = environ
        self.dict = None
        self.headers = None

    #--------------------------------------------------------------------------#
    def __len__(self):
        """
        @brief Get the number of headers in a message.
        @return integer nuber of headers found

        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        return len(self.dict)

    #--------------------------------------------------------------------------#
    def __getitem__(self, name):
        """
        @brief Get a specific header, as from a dictionary.
        @param name string HTTP header name of which to get the value
        @return string value of header entry for name

        This routine tries to avoid creating the whoel dict dictionary.
        However if it has been produced then it will be used.

        Note that this will raise KeyError if the name is not in the dict.
        """
        n = name.lower()
        if self.dict is not None:
            return self.dict[n]
        h = HTTP_WSGI_HEADER_MAP[n]
        h = self.environ[h]
        return h

    #--------------------------------------------------------------------------#
    def get(self, name, default=None):
        """
        @brief Get a specific error but return default if name not in the dict.
        @param name string HTTP header name of which to get the value
        @param default string value to return if name not in dictionary
        @return string value of header entry for name or value of default
                if not in dictionary.

        This routine tries to avoid creating the whoel dict dictionary.
        However if it has been produced then it will be used.
        """
        try:
            return self[name]
        except KeyError:
            return default

    #--------------------------------------------------------------------------#
    def __setitem__(self, name, value):
        """
        @brief Set the value of a header.
        @param name string key whose walue is to be set
        @param value string value for key
        @return void

        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.

        Modifies both dict and headers.  Because the headers have been
        coalesced into a single string by CGI there is only one entry
        per header now.

        Note: This is not a perfect inversion of __getitem__, because any
        changed headers get stuck at the end of the raw-headers list rather
        than where the altered header was.
        """
        if self.dict is None:
            self._make_dict()
        del self[name] # Won't fail if it doesn't exist
        self.dict[name.lower()] = value
        self.headers.append(name + ": " + value + "\n")
        return

    #--------------------------------------------------------------------------#
    def __delitem__(self, name):
        """
        @brief Delete the occurrence of a specific header, if it is present.
        @param name string key of entry to be deleted

        Entries are deleted from both dict and headers.  Note that here there
        is only a single entry for each header after CGI has got at the request.

        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        name = name.lower()
        if not name in self.dict:
            return
        del self.dict[name]
        name = name + ':'
        n = len(name)
        lst = []
        hit = 0
        for i in range(len(self.headers)):
            line = self.headers[i]
            if line[:n].lower() == name:
                hit = 1
            elif not line[:1].isspace():
                hit = 0
            if hit:
                lst.append(i)
        for i in reversed(lst):
            del self.headers[i]
        return

    #--------------------------------------------------------------------------#
    def setdefault(self, name, default=""):
        """
        @brief Same as get but make an entry in the dict and headers
               with the default value if there was no entry before
        @param name string HTTP header name of which to get the value
        @param default string value to set and return if name not in dictionary
        @return string value of header entry for name or value of default
                if not in dictionary.
               
        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        lowername = name.lower()
        if lowername in self.dict:
            return self.dict[lowername]
        else:
            text = name + ": " + default
            for line in text.split("\n"):
                self.headers.append(line + "\n")
            self.dict[lowername] = default
            return default

    #--------------------------------------------------------------------------#
    def has_key(self, name):
        """
        @brief Determine whether a message contains the named header.
        @param name string key to check
        @return boolean indicating if key is in dict

        This is optimized so that we don't build dict if not already built.
        """
        n = name.lower()
        if self.dict is not None:
            return n in self.dict
        h = HTTP_WSGI_HEADER_MAP.get(n)
        if h is None:
            return False
        return h in self.environ
        
        return name.lower() in self.dict

    #--------------------------------------------------------------------------#
    def __contains__(self, name):
        """
        @brief Determine whether a message contains the named header.
        @param name string key to check
        @return boolean indicating if key is in dict

        This is optimized so that we don't build dict if not already built.
        """
        n = name.lower()
        if self.dict is not None:
            return n in self.dict
        h = HTTP_WSGI_HEADER_MAP.get(n)
        if h is None:
            return False
        return h in self.environ

    #--------------------------------------------------------------------------#
    def __iter__(self):
        """
        @brief Generate an iterator over the dictionary.
        @return iterator for dictionary

        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        return iter(self.dict)

    #--------------------------------------------------------------------------#
    def keys(self):
        """
        @brief Get all of a message's header field names.
        @return key set for dictionary
        
        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        return self.dict.keys()

    #--------------------------------------------------------------------------#
    def values(self):
        """
        @brief Get all of a message's header field values.
        @return value set for dictionary

        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        return self.dict.values()

    #--------------------------------------------------------------------------#
    def items(self):
        """
        @brief Get all of a message's headers.
        @return list of name, value tuples.
        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        return self.dict.items()

    #--------------------------------------------------------------------------#
    def __str__(self):
        """
        @brief Get string representation of total set of headers
        @return string join of headers
        For this we have to construct the dictionary of althe headers
        if it hadn't been done already.
        """
        if self.dict is None:
            self._make_dict()
        return ''.join(self.headers)

    #--------------------------------------------------------------------------#
    def _make_dict(self):
        """
        @brief Compile dictionary of all headers
        
        Scan the environ dictionary for all entries that are also in
        WSGI_HTTP_HEADER_MAP dictionary.

        Make the internal dict using the value of the entry in
        WSGI_HTTP_HEADER_MAP as key and the correseponding value from environ. 
        Make the headers list in parallele.
        """
        self.dict = {}
        self.headers = []
        for k in self.environ:
            if ((k.startswith("HTTP_")) and (k in WSGI_HTTP_HEADER_MAP)) :
                h = WSGI_HTTP_HEADER_MAP[k]
                v = self.environ[k]
                self.dict[h] = v
                self.headers.append("%s: %s\n" % (h, v))
            elif ((k == "CONTENT_LENGTH") or (k == "CONTENT_TYPE")):
                h = WSGI_HTTP_HEADER_MAP[k]
                v = self.environ[k]
                self.dict[h] = v
                self.headers.append("%s: %s\n" % (h, v))
        return
                                              
#==============================================================================#
class wsgiHTTPRequestShim:
    """
    @brief Interface shim to allow NIHTTPRequestHandler to be used from a WSGI
           application funtion

    Typically a WSGI application function using this class and a real hanfler
    would look like

    @code

    # Trivial handler
    class TrivialHandler(wsgiHTTPRequestShim):
        def do_GET(self):
            self.send_response(200, "OK")
            response_str = "Hello World!"
            self.send_header("Content-Length", str(len(response_str)))
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.send_string(response_str)
            return

        def do_POST(self):
            ...
            
    def application(environ, start_response):  # WSGI boilerplate

        # These entries have to be present for the NIHTTPRequestHandler
        # but aren't used in the example.  They can be set by
        # Apache SetEnv directives if used with mod_wsgi.
        environ["NETINF_STORAGE_ROOT"] = "/tmp/cache"
        environ["NETINF_GETPUTFORM"] = "/var/niserver/getputform.html"
        environ["NETINF_NRSFORM"] = "/var/niserver/nrsconfig.html"
        environ["NETINF_FAVICON"] = "/var/niserver/favicon.ico"
        environ["NETINF_PROVIDE_NRS"] = "no"
        # Optionally...
        environ["NETINF_LOG_LEVEL"] = "NETINF_LOG_INFO"

        # Handle the request
        handler = TrivialHandler(log_stream=environ["wsgi.error"]))
        return handler.handle_request(environ, start_response)
    @endcode

    The class constructor sets up a logger that writes to the logger stream
    provided by WSGI (environ["wsgi.error"]).  Note that care has to be taken
    to flush and close the logger before completing the request because
    the WSGI logger may not accept more input after the application function
    returns and the logger can operate asynchronously.

    The method 'handle_request' sets up the equivalent of the environment
    that is used by a class derived from BaseHTTPRequestHandler, which is what
    NIHTTPRequestHandler expects, using the 'environ' dictionary supplied by
    WSGI as a parameter to 'application'.  When used with mod_wsgi the NETINF
    specific values can be supplied by Apache SetEnv directives but must be in
    'environ' when 'handle_request' is called.

    In 'handle_request' the headers from the request are converted into a
    'pseudo-dictionary' using an instance of 'HeaderDict'.

    Then depending on the value of environ["REQUEST_METHOD"] (GET, POST, etc),
    the appropriate 'do_...' method is called in the handler subclass.

    The various 'send_...' methods called by the handler class method assemble
    the reponse line, the response headers and chunks of the response body into
    - response_status
    - respomse_headers
    - response_body

    Response_status and response_headers are passed to the WSGI start_response
    function when the handler finishes by calling the 'trigger_response'
    method which also flushes the log.

    The whole class is configured as an iterator (see 'next' method) and is
    passed back to WSGI as the return value of 'application'.  WSGI then
    grabs all the chunks of reponse body by iterating through the reponse
    body via the 'next' method.
    """
    #--------------------------------------------------------------------------#
    # CONSTANT VALUES USED BY CLASS

    ##@var DEFAULT_ERROR_MESSAGE
    # string template used by send_error for error returns
    DEFAULT_ERROR_MESSAGE = """\
    <head>
    <title>Error response</title>
    </head>
    <body>
    <h1>Error response</h1>
    <p>Error code %(code)d.
    <p>Message: %(message)s.
    <p>Error code explanation: %(code)s = %(explain)s.
    </body>
    """
    
    ##@var DEFAULT_ERROR_CONTENT_TYPE
    # The content-type corresponding to the DEFAULT_ERROR_MESSAGE.
    DEFAULT_ERROR_CONTENT_TYPE = "text/html"

    ##@var NETINF_LOG_MAP
    # Table mapping string values for NETINF_LOG_LEVEL environent values
    # to logging module level (integer) values.
    NETINF_LOG_MAP = {
        "NETINF_LOG_DEBUG": logging.DEBUG,
        "NETINF_LOG_INFO":  logging.INFO,
        "NETINF_LOG_WARN":  logging.WARN,
        "NETINF_LOG_ERROR": logging.ERROR
    }

    ##@var WEEKDAYNAME
    # Array of abbreviated weekday names for making date/time strings
    WEEKDAYNAME = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    ##@var MONTHNAME
    # Array of abbreviated month names for making date/time strings
    MONTHNAME = [None,
                 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    ##@var HTTP_RESPONSES
    # Table mapping response codes to messages; entries have the
    # form {code: (shortmessage, longmessage)}.
    # See RFC 2616.
    HTTP_RESPONSES = {
        100: ('Continue', 'Request received, please continue'),
        101: ('Switching Protocols',
              'Switching to new protocol; obey Upgrade header'),

        200: ('OK', 'Request fulfilled, document follows'),
        201: ('Created', 'Document created, URL follows'),
        202: ('Accepted',
              'Request accepted, processing continues off-line'),
        203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
        204: ('No Content', 'Request fulfilled, nothing follows'),
        205: ('Reset Content', 'Clear input form for further input.'),
        206: ('Partial Content', 'Partial content follows.'),

        300: ('Multiple Choices',
              'Object has several resources -- see URI list'),
        301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
        302: ('Found', 'Object moved temporarily -- see URI list'),
        303: ('See Other', 'Object moved -- see Method and URL list'),
        304: ('Not Modified',
              'Document has not changed since given time'),
        305: ('Use Proxy',
              'You must use proxy specified in Location to access this '
              'resource.'),
        307: ('Temporary Redirect',
              'Object moved temporarily -- see URI list'),

        400: ('Bad Request',
              'Bad request syntax or unsupported method'),
        401: ('Unauthorized',
              'No permission -- see authorization schemes'),
        402: ('Payment Required',
              'No payment -- see charging schemes'),
        403: ('Forbidden',
              'Request forbidden -- authorization will not help'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed',
              'Specified method is invalid for this resource.'),
        406: ('Not Acceptable', 'URI not available in preferred format.'),
        407: ('Proxy Authentication Required', 'You must authenticate with '
              'this proxy before proceeding.'),
        408: ('Request Timeout', 'Request timed out; try again later.'),
        409: ('Conflict', 'Request conflict.'),
        410: ('Gone',
              'URI no longer exists and has been permanently removed.'),
        411: ('Length Required', 'Client must specify Content-Length.'),
        412: ('Precondition Failed', 'Precondition in headers is false.'),
        413: ('Request Entity Too Large', 'Entity is too large.'),
        414: ('Request-URI Too Long', 'URI is too long.'),
        415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
        416: ('Requested Range Not Satisfiable',
              'Cannot satisfy request range.'),
        417: ('Expectation Failed',
              'Expect condition could not be satisfied.'),

        500: ('Internal Server Error', 'Server got itself in trouble'),
        501: ('Not Implemented',
              'Server does not support this operation'),
        502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
        503: ('Service Unavailable',
              'The server cannot process the request due to a high load'),
        504: ('Gateway Timeout',
              'The gateway server did not receive a timely response'),
        505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
        }

    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES
    

    # === Application Variables derived from configuration ===
    
    ##@var storage_root
    # string pathname for base directory of storage cache
    
    ##@var getputform
    # string pathname for file containing HTML form template for netinfproto
    
    ##@var nrsform
    # string pathname for file containing HTML form template for nrsconf
    
    ##@var favicon
    # string pathname for favicon for NetInf operations
    
    ##@var provide_nrs
    # boolean if True server supports NRS operations and needs Redis interface
    
    ##@var nrs_redis
    # object instance of Redis database interface (or None if provide_nrs False)

    # === CGI derived variables ===
    
    ##@var server_name
    # string FQDN of server hosting this program
    
    ##@var server_port
    # integer port number on which server is listening
    
    ##@var authority
    # string combination of server_name and server_port as used for netloc of URLs
    
    ##@var command
    # string the HTTP request type (expecting HEAD, GET or POST)
    
    ##@var path
    # combination of the path and query string components of the URL
    # i.e., everything after the netloc - shouldn't contain any fragment
    # specifier as this is supposed to be filtered out by browser, but might not be.
    
    ##@var rfile
    # object instance of file(-like) object on which any request body can be read.
    
    ##@var headers
    # dictionary(-like) object reprresenting request headers indexed by HTTP
    # header names.
    
    ##@var requestline
    # string original value of request command line in HTTP (e.g., HTTP/1.1 GET /)
    
    ##@var environ
    # dictionary of environment variable keys and values as suplied by WSGI
    
    ##@var server_version
    # string with one or more version information units, started with the
    # value of SERVER_SOFTWARE and adding information abut NetInf server
    
    ##@var sys_version
    # string the version of Python being run
    
    ##@var version_string
    # string concatenation of server_version and sys_version
    
    # === Logging convenience functions etc ===
    
    ##@var logger
    # object instance of Logger object routing to Apache log via stderr
    # redirection through mod_wsgi.
    
    ##@var log_handler
    # object instance of StreamHandler attached to logger.  Has to be kept
    # visible so that it can be flushed and closed before the mod_wsgi
    # wsgi.error object 'expires' when the 'application' function completes.
    # The StreamHandler (probably) runs asynchronously so that log messages
    # are queued up for output so they don't get flushed till the garbage
    # coilector cleans up the logger instance.
    
    ##@var log_level
    # integer normally one of logging.ERROR/WARN/INFO/DEBUG used to set
    # logging level in logger.
    
    ##@var loginfo
    # Convenience function for logging informational messages
    
    ##@var logdebug
    # Convenience function for logging debugging messages
    
    ##@var logwarn
    # Convenience function for logging warning messages
    
    ##@var logerror
    # Convenience function for logging error reporting messages
    
    ##@var error_message_format
    # string template for error document sent by send_error
    #        May be modified if a different format is wanted
    #        Remember to alter error_content_type if appropriate.
    error_message_format = DEFAULT_ERROR_MESSAGE
    
    ##@var error_content_type
    # string corresponding content type for error_message_format 
    error_content_type = DEFAULT_ERROR_CONTENT_TYPE

    # === Response gathering ===
    ##@var response_status
    # string HTTP response code and status message separated by a space
    
    ##@var response_headers
    # array of 2-tuples consisting of HTTP header name string and value string

    ##@var response_body
    # array of strings or readable file-like object instances.
    # Iterated over to form response body.
    
    ##@var response_headers_done
    # boolean set True when end_headers is called to signify the header set is
    # complete
    
    ##@var response_length
    # string overall length of response body cnverted to a string
    
    ##@var http_response_code
    # integer HTTP reesponse code to be returned from this request
    
    ##@var resp_curr_index
    # integer index into response_body array used when iterating over array
    
    ##@var ready_to_iterate
    # boolean True when the reponse is ready to pass back to WSGI
    
    ##@var error_sent
    # boolean True if send_error has been called while processing this request.
    # If send_error is called again an error message will be logged but the
    # original message won't be modified.
    
    ##@var unique_id 
    # integer random number used to uniquely identify files generated for this
    # request

    #--------------------------------------------------------------------------#
    def __init__(self, log_stream=None):
        """
        @brief Constructor - sets up logging
        @param log_stream file like object with write capability or None

        Uses the Python logging module
        Defaults to INFO level logging and stderr sttream output.
        Everything else has to be configured on a per request basis.
        """
        
        self.logger = logging.getLogger("NetInf")
        self.logger.setLevel(logging.INFO)
        ch = logging.StreamHandler(log_stream)
        fmt = logging.Formatter("mod_wsgi.netinf - %(asctime)s %(levelname)s %(message)s")
        ch.setFormatter(fmt)
        self.logger.addHandler(ch)
        self.log_handler = ch

        # Logging functions
        self.loginfo = self.logger.info
        self.logdebug = self.logger.debug
        self.logwarn = self.logger.warn
        self.logerror = self.logger.error

        # Used for creating unique temporary file names
        r = random.SystemRandom()
        self.unique_id = r.randint(0, 64000)

        return

    #--------------------------------------------------------------------------#
    def _quote_html(self, html):
        """
        @brief Used for quoting error mesages to avoid cross-site scripting
        @param html string the HTML to be quoted
        @return string the quoted HTML
        """
        return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    #--------------------------------------------------------------------------#
    def handle_request(self, environ, start_response):
        """
        @brief Process request fed to WSGI via 'spplication' function
        @param environ dictionary containing environment and request headers
        @param start_response callable to return response code etc as per WSGI
        @return iterable representing response content

        Load instance variables from environ dictionary.
        
        Generate instance variables from environ dictionary:
            Check there is a sensible request and path to process.
            The path has to be reconstructed from the CGI variables
            NOTE: The CGI process in Apache splits up the path
            component of the URI into pieces depending on aliasing
            of scripts in the server configuration.  An explanation
            of exactly what the split means can be found here
            http://wildlifedamage.unl.edu/manual/cgi_path.html
            (I cannot find this in the current official documentation!)
            Basically:
            SCRIPT_NAME  is the part 'the user has no control over' - if
                         there is an alias in place then this is the part
                         of the URL path that matches the alias.
            PATH_INFO    is the rest of the path except that if
                         mod_cgi is in use and AcceptPathInfo is set off
                         then you will never see the PATH_INFO and
                         Apache will give you a 404 error for non-empty
                         pieces after the SCRIPT_NAME.
            QUERY_STRING the part after the ? in the URL.  Note that
                         fragment specifiers should never make it to
                         here as browsers aren't supposed to put them on
                         the wire.  Less pernickety clients might send
                         them along.. but they shouldn't make it this far.
        Create headers dictionary from environ dictionary.
        Setup connection to Redis database server if required.
        Invoke function do_<command> to process request
        Check headers have been constructed and end_headers called.
        Set up response data iterable.
        Send data back to WSGI.
        """
        def set_from_env(env_name, ret_val, env_type):
            try:
                v = environ[env_name]
                return (v, ret_val)
            except KeyError:
                self.logerror("%s environment variable %s not set" %
                              (env_type, env_name))
                return (None, False)

        # Rememeber the environment dictionary
        self.environ = environ    

        # Set up to record information for response
        self.clear_response()
        self.error_sent = False

        # Alter logging level from default (INFO) if NetInf env var set
        self.log_level = self.NETINF_LOG_MAP[environ.get("NETINF_LOG_LEVEL",
                                                         "NETINF_LOG_INFO")]
        self.logger.setLevel(self.log_level)

        self.requestline = "(Not yet known)"
        self.server_version = " %s %s" % (NISERVER_VER, NETINF_VER)
        self.sys_version = "Python/" + sys.version.split()[0]
        self.version_string = self.server_version + " " + self.sys_version

        rv = True
        self.command, rv = set_from_env("REQUEST_METHOD", rv, "Mandatory CGI")
        self.path, rv = set_from_env("SCRIPT_NAME", rv, "Mandatory CGI")
        pi, rv = set_from_env("PATH_INFO", rv, "Mandatory CGI")
        if not rv:
            # Assume there is something seriously wrong here
            print >>sys.stderr, "Mandatory settings missing from mod_wsgi environment"
            # Try for a 500 error
            self.send_error(500, "Mandatory CGI environment not found")
            return self.trigger_response(start_response)
        self.path += pi
        try:
            qs = environ["QUERY_STRING"]
            if qs != "":
                self.path += "?" + qs
        except KeyError:
            # QUERY_STRING may not be set if the URL didn't have one
            pass

        # Basic CGI environment        
        self.server_name, rv     = set_from_env("SERVER_NAME", rv, "CGI")
        server_port, rv          = set_from_env("SERVER_PORT", rv, "CGI")
        self.client_address, rv  = set_from_env("REMOTE_ADDR", rv, "CGI")
        self.server_version, rv  = set_from_env("SERVER_SOFTWARE", rv, "CGI")
        self.request_version, rv = set_from_env("SERVER_PROTOCOL", rv, "CGI")

        if not rv:
            # Assume there is something seriously wrong here
            print >>sys.stderr, "Expected settings missing from mod_wsgi environment"
            # Try for a 500 error
            self.send_error(500, "Expected CGI environment not found")
            return self.trigger_response(start_response)

        self.server_port = int(server_port)
        
        self.authority = "%s:%d" % (self.server_name, self.server_port)

        self.requestline = "%s %s %s" % (self.request_version,
                                         self.command,
                                         self.path)

        # Add info to server_version string and create version_string
        self.server_version += " %s %s" % (NISERVER_VER, NETINF_VER)
        self.version_string = self.server_version + " " + self.sys_version

        # NetInf specific environment
        self.storage_root, rv    = set_from_env("NETINF_STORAGE_ROOT", rv, "NetInf")
        self.getputform, rv      = set_from_env("NETINF_GETPUTFORM", rv, "NetInf")
        self.nrsform, rv         = set_from_env("NETINF_NRSFORM", rv, "NetInf")
        provide_nrs, rv          = set_from_env("NETINF_PROVIDE_NRS", rv, "NetInf")
        self.favicon, rv         = set_from_env("NETINF_FAVICON", rv, "NetInf")

        if not rv:
            self.send_error(500, "NetInf environment not correctly configured")
            return self.trigger_response(start_response)

        # WSGI specific environment
        self.rfile, rv           = set_from_env("wsgi.input", rv, "WSGI module") 

        if not rv:
            self.send_error(500, "WSGI environment not functioning correctly")
            return self.trigger_response(start_response)

        # Create request headers pseudo-dictionary
        self.headers = HeaderDict(environ)

        # Convert string value of NETINF_PROVIDE_NRS to boolean
        provide_nrs = provide_nrs.lower()
        if provide_nrs in ["yes", "true", "1"]:
            self.provide_nrs = True
        elif provide_nrs in ["no", "false", "0"] :
            self.provide_nrs = False
        else:
            self.logerror("Cannot convert NETINF_PROVIDE_NRS to boolean: %s" %
                          provide_nrs)
            self.send_error(500, "Value of NETINF_PROVIDE_NRS must be one of yes/true/1/no/false/0.")
            return self.trigger_response(start_response)            

        # If an NRS server is wanted, create a Redis client instance
        # Assume it is the default local_host, port 6379 for the time being
        if self.provide_nrs:
            try:
                self.nrs_redis = redis.StrictRedis()
            except Exception, e:
                self.logerror("Unable to connect to Redis server: %s" % str(e))
                self.send_error(500, "Unable to connect to Redis server")
                return self.trigger_response(start_response)
        else:
            self.nrs_redis = None

        self.loginfo("New HTTP request connection from %s" % self.client_address[0])

        # Call appropriate command processor
        mname = 'do_' + self.command
        if not hasattr(self, mname):
            self.send_error(501, "Unsupported method (%s)" % self.command)
        else:
            method = getattr(self, mname)
            method()

        # Get the response going
        # Check that the method has flagged all the headers finished and
        # entered a status - override with an error if not so
        if not (self.response_status and self.response_headers_done):
            self.response_headers = []
            self.response_body = []
            self.send_error(500,
                            "Method either did not write status or mark end of headers")

        return self.trigger_response(start_response)

    #--------------------------------------------------------------------------#
    def trigger_response(self, start_response):
        """
        @brief Inform WSGI that response is ready.
        @return iterator which will return reponse body wehn asked
        """
        self.ready_to_iterate = True

        # To avoid log object having expired by the time log messages are output
        # have to flush and close the log_handler.  Otherwise mesaages queued
        # messages may cause later exceptions.
        self.log_handler.flush()
        self.log_handler.close()
        
        start_response(self.response_status, self.response_headers)
        return iter(self)

    #--------------------------------------------------------------------------#
    def __iter__(self):
        """
        @brief This class can be treated as an iterator.

        It has a 'next' method that will deliver the contents of the
        response_body in chunks when set up.
        """
        return self
    
    #--------------------------------------------------------------------------#
    def next(self):
        """
        @brief Generator function that iterates through parts of response body

        Items in response_body array are either strings (entered by send_string)
        or open readable files (entered by send_file). The string items
        are yielded as one unit.  The files are yielded as blocks of up to 16K
        octets.

        Note: It would be nice to actually write this as a generator function.
        Unfortunately generator methods do not work in the obvious way that
        stand-alone functions do.  There is a horribly complex recipe for
        applying a decorator to the method that turns it into a generator
        but for the simple case here it is in the end easier to provide the
        class with the iterator interface (define __iter__ and next methods).
        If you are interested in how to turn a class method into a generator
        see http://code.activestate.com/recipes/392154/.  There will be a quiz
        at the end of class...
        """
        while True:
            if ((not self.ready_to_iterate) or
                (self.resp_curr_index >= len(self.response_body))):
                raise StopIteration

            segment = self.response_body[self.resp_curr_index]
            if type(segment) == types.StringType:
                self.resp_curr_index += 1
                return segment
            elif hasattr(segment, "read"):
                blksize = 16384
                buf = segment.read(blksize)
                if not buf:
                    segment.close()
                    self.resp_curr_index += 1
                    continue
                return buf
            else:
                self.logerror("Item in response_body that is not a string or file")
                self.resp_curr_index += 1
                continue
        return None
                
    #--------------------------------------------------------------------------#
    def clear_response(self):
        """
        @brief Reset all the state associated with a response

        Used when starting to handle a new request or if an error has to be sent.
        """
        self.response_status = None
        self.response_headers = []
        self.response_headers_done = False
        # On initialisation response_body deosn't yet exist
        try:
            # Close any file descriptors in the response_body array
            for i in self.response_body:
                if hasattr(i, "close"):
                    i.close()
        except Exception, e:
            # print "No response_body: %s" % str(e)
            pass
        self.response_body = []
        self.response_length = "(Not known)"
        self.http_response_code = 0
        self.resp_curr_index = 0
        self.ready_to_iterate = False
        return
    
    #--------------------------------------------------------------------------#
    def send_error(self, code, message=None):
        """
        @brief Send and log an error reply.
        @param code integer HTTP error code
        @param message string optional error message (defaults supplied if missing)

        Arguments are the error code, and a detailed message.
        The detailed message defaults to the short entry matching the
        response code.

        This sends an error response (so it must be called before any
        output has been generated), logs the error, and finally sends
        a piece of HTML explaining the error to the user.

        It clears any previously generated headers and cached resppnse body.
        """

        # Don't overwrite earlier error
        if self.error_sent:
            self.logerror("Secondary error recorded: %s (%d)" % (message, code))
            return
        
        try:
            short, long = self.HTTP_RESPONSES[code]
        except KeyError:
            short, long = '???', '???'
        if message is None:
            message = short
        explain = long

        # using _quote_html to prevent Cross Site Scripting attacks (see bug #1100201)
        content = (self.error_message_format %
                   {'code': code,
                    'message': self._quote_html(message),
                    'explain': explain})
        self.clear_response()
        self.send_response(code, message)
        if self.command != 'HEAD' and code >= 200 and code not in (204, 304):
            self.send_string(content)
        self.send_header("Content-Type", self.error_content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.error_sent = True
        self.loginfo("code: %d, message: %s", code, message)
        return

    #--------------------------------------------------------------------------#
    def send_response(self, code, message=None):
        """
        @brief Record the response header and log the response code.

        Also send two standard headers with the server software
        version and the current date.

        """
        # Don't overwrite earlier error
        if self.error_sent:
            self.logerror("Response after error recorded: %s (%d)" % (message, code))
            return
        
        if message is None:
            if code in self.HTTP_RESPONSES:
                message = self.HTTP_RESPONSES[code][0]
            else:
                message = ''
        self.http_response_code = code
        self.response_status = "%d %s" % (code, message)
        self.send_header('Server', self.version_string)
        self.send_header('Date', self.date_time_string())
        return

    #--------------------------------------------------------------------------#
    def send_header(self, keyword, value):
        """
        @brief Record an HTTP header for leater sending.
        @param keyword string name f header in canonical HTTP form
        @param value string value of header to be sent

        The header (keyword, value) 2-tuple is added to the list for
        later sending by mod_wsgi.

        Record the response length if the Content-Length header is seen
        """
        if (keyword.lower() == "content-length"):
            if self.command == "HEAD":
                value = "0"
            self.response_length = value
        self.response_headers.append( (keyword, value) )
        return


    #--------------------------------------------------------------------------#
    def end_headers(self):
        """
        @brief Record all headers setup

        This is mainly a sanity check for thw WSGI case as the actual
        header sending is organized by mod_wsgi.
        It is also sensible to log the request here because this should
        be called last after send_request and any calls to send_header.

        In the WSGI case the order is not critical but for the alternative
        BaseHTTPRequestHandler usage of the handler, the *order is important*:
        Need to call send_request, then zero or more calls of send header
        completed by a call to end_headers because they actually push the
        output onto the wire.
        """
        self.log_request(self.http_response_code, self.response_length)
        self.response_headers_done = True
        return

    #--------------------------------------------------------------------------#
    def log_request(self, code='-', size='-'):
        """Log an accepted request.

        This is called by send_response().

        """

        self.loginfo('"%s" %s %s',
                         self.requestline, str(code), str(size))

    #--------------------------------------------------------------------------#
    def send_file(self, source):
        """
        @brief Record an open file descriptor ro be read and written as part
               of the response.

        @param source file-like object open for reading
                          (or anything with a read() method)
        @return void
        
        """
        # Don't overwrite earlier error
        if self.error_sent:
            self.logerror("Attempt to add file response after error sent")
            return
        
        # Verify this is really a file-like readable (StringIO possibly)
        if not hasattr(source, "read"):
            self.logerror("Arument to send_file is not a file: %s" % str(source))
            return
        
        self.response_body.append(source)
        return

    #--------------------------------------------------------------------------#
    def send_string(self, buf):
        """
        @brief Record a buf (string) to be copied as par of the response.

        @param buf string to be written

        @return void
        """
        # Don't overwrite earlier error
        if self.error_sent:
            self.logerror("Attempt to add string response after error sent")
            return

        # Verify this is really a string
        if (type(buf) != types.StringType):
            self.logerror("Arument to send_string is not a string: %s" % str(buf))
            return
        
        self.response_body.append(buf)
        return

    #--------------------------------------------------------------------------#
    def date_time_string(self, timestamp=None):
        """
        @brief Return the current date and time formatted for a message header.
        @param timestamp integer time value to be inserted into string
        @return strin containing date and time

        If the timestamp is None the current time is used
        """
        if timestamp is None:
            timestamp = time.time()
        year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
        s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
                self.WEEKDAYNAME[wd],
                day, self.MONTHNAME[month], year,
                hh, mm, ss)
        return s

    #--------------------------------------------------------------------------#
    def log_date_time_string(self):
        """
        @brief Return the current time formatted for logging.
        @return string with curent time formatted suitable for logging.
        """
        now = time.time()
        year, month, day, hh, mm, ss, x, y, z = time.localtime(now)
        s = "%02d/%3s/%04d %02d:%02d:%02d" % (
                day, self.MONTHNAME[month], year, hh, mm, ss)
        return s

#==============================================================================#

