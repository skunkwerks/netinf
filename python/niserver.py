#!/usr/bin/python
"""
@package ni
@file niserver.py
@brief Lightweight dedicated NI HTTP server.
@brief Implements NetInf proto HTTP convergence layer and direct GETs via HTTP.
@version $Revision: 0.01 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
      This is an adjunct to the NI URI library developed as
      part of the SAIL project. (http://sail-project.eu)

      Specification(s) - note, versions may change
          http://tools.ietf.org/html/farrell-decade-ni-00
          http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
       http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

===========================================================================

Lightweight dedicated NI HTTP server.

Implements
- NetInf proto GET and PUBLISH with HTTP convergence layer (SEARCH to follow)
- Direct GETs of Named Data Objects via HTTP URL translations of ni: names.
- Various support functions including listing the cache, delivering a form
  to generate the POST functions and returning a favicon.ico 

Creates a threaded HTTP server that responds to a limited set of URLs
- GET/HEAD on path /.well-known/ni/<digest algorithm id>/<digest>,
                   /getputform.html
                   /favicon.ico, and
                   /netinfproto/list
- POST on paths /netinfproto/get,
                /netinfproto/publish, and
                /netinfproto/put,
                (with /netinf/search to follow)

A new thread is created for each incoming request.  Most of the work is done
by HTTP Server (effectively TCPServer) and BaseHTTPRequestHandler from the
standard Python module BaseHTTPServer.

The logging and thread management was inspired by the PyMail program from the
N4C project.

The basic GET and POST handlers are inspired by Doug Hellmann's writing on
on BaseHTTPServer in his Python Module of the Week series at
http://www.doughellmann.com/PyMOTW/BaseHTTPServer/index.html

Should be used with Python 2.x where x is 6 or greater (the TCP socket
server up to version 2.5 is badly flawed (euphemism).

The server uses a configuration file to specify various items (see
niserver_main.py) and set up logging.  The items that are significant
for the internal operations here are:
server_port     the TCP port used by the HTTP server listener (default 8080)
authority       the hostname part of the address of the HTTP server
storage_root    the base directory where the content cahe is stored
logger          a logger to be used by the server (uses Python logging module)

The server manages a local cache of published information.  In the storage_root
directory there are two parallel sub-directories: an ni_ndo and and an ni_meta
sub-directory where the content and metadata of the content are stored,
respectively.  In each sub-directory thre is a sub-directory for each digest
algorithm.  Each of these directories contains the file names are the digest of
the content (i.e., the digest in the ni: name).

Entries are inserted into the cache by the  NetInf 'publish' (or 'put') function
or can be generated externally and tied into the cache.

Revision History
================
Version   Date       Author         Notes
0.2	  01/09/2012 Elwyn Davies   Metadata handling added.
0.1       11/07/2012 Elwyn Davies   Added 307 redirect for get from .well_known.
0.0	  12/02/2012 Elwyn Davies   Created for SAIL codesprint.
"""

import os
import socket
import threading
import logging
import shutil
import json
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from BaseHTTPServer import BaseHTTPRequestHandler
from BaseHTTPServer import HTTPServer
from SocketServer import ThreadingMixIn
import cgi
import mimetypes
import urllib
import hashlib
import datetime

"""
@brief In browser form HTML source for doing NetInf GET and PUBLISH.

This form is displayed by accessing the document  getputform.html in the
document root of the mini server.  It is (currently) the only piece
of static HTML accessible through this server.  Everything else is about
getting showing and publishing Named Data Objects (NDOs) in the cache
managed by this server.

The code is essentially that from nilib/php/getputform.html.
"""
GET_PUT_FORM_HTML = """
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>SAIL "ni" name fetcher and putter</title>
</head>
<body>

<h1>NetInf GET</h1>

<form name="fetchni" action="/netinfproto/get" method="post">
<table border="1">
<tbody>
<tr> <td>NI name:</td> <td><input type="text" name="URI" /></td> </tr>
<tr> <td>msg-id</td> <td><input type="text" name="msgid" /></td> </tr>
<tr> <td>ext (optional)</td> <td><input type="text" name="ext" /></td> </tr>
<tr>
<td/>
<td><input type="submit" value="Submit"/> </td>
</tr>
</tbody>
</table>
</form>

<h1>NetInf PUBLISH</h1>

<form name="fetchni" action="/netinfproto/publish" enctype="multipart/form-data" method="post">
<table border="1">
<tbody>
<tr><td>NI name</td> <td><input type="text" name="URI"/> </tr>
<tr><td>msg-id</td> <td><input type="text" name="msgid" /></td> </tr>
<tr><td>ext (optional)</td> <td><input type="text" name="ext" /></td> </tr>
<tr><td>File (optional): </td><td><input type="file" name="octets" size="20"/></td></tr>
<tr><td>Locator1</td> <td><input type="text" name="loc1"/> </tr>
<tr><td>Locator2</td> <td><input type="text" name="loc2"/> </tr>
<tr><td>Full PUT?</td><td><input type="checkbox" name="fullPut"/></td></tr>
<tr><td><input type="submit" value="Submit"/> </tr>

</tbody>
</table>

</form>

<h1>NetInf SEARCH</h1>

<p>This will search Wikipedia (when it works!)</p>

<form name="searchni" action="/netinfproto/search" method="post">
<table border="1">
<tbody>
<input type="hidden" name="stage" value="zero"/>
<tr> <td>Keywords:</td> <td><input type="text" name="tokens" /></td> </tr>
<tr> <td>msg-id</td> <td><input type="text" name="msgid" /></td> </tr>
<tr> <td>ext (optional)</td> <td><input type="text" name="ext" /></td> </tr>
<tr>
<td/>
<td><input type="submit" value="Submit"/> </td>
</tr>
</tbody>
</table>
</form>

</body>
</html>

"""


import ni

class NetInfMetaData:
    def __init__(self, ni_uri="", timestamp=None, ctype=None, myloc=None, loc1=None, loc2=None, extrameta=None):
        self.json_obj = {}
        self.json_obj["NetInf"] = "v0.1a Elwyn"
        self.json_obj["ni"]     = ni_uri
        self.json_obj["detail"] = {}

        detail = self.json_obj["detail"]
        if timestamp is None:
            detail["ts"]            = ""
        else:
            detail["ts"]            = timestamp
        if ctype is None:
            detail["ct"]        = ""
        else:
            detail["ct"]        = ctype
        detail["loc"]           = []
        self.append_locs(myloc, loc1, loc2)
        if extrameta is None:
            detail["extrameta"] = {}
        else:
            detail["extrameta"] = extrameta
        detail["extrameta"]["publish"] = "python"

        return

    def __repr__(self):
        return json.dumps(self.json_obj, separators=(',',':'))
        
    def __str__(self):
        return json.dumps(self.json_obj, sort_keys = True, indent = 4)

    def json_val(self):
        return self.json_obj

    def append_locs(self, myloc=None, loc1=None, loc2=None):
        loclist = self.json_obj["detail"]["loc"]
        if myloc is not None and myloc is not "":
            if not myloc in loclist: 
                loclist.append(myloc)
        if loc1 is not None and loc1 is not "":
            if not loc1 in loclist: 
                loclist.append(loc1)
        if loc2 is not None and loc2 is not "":
            if not loc2 in loclist: 
                loclist.append(loc2)
        return
    def get_ni(self):
        return self.json_obj["ni"]
    
    def get_timestamp(self):
        return self.json_obj["detail"]["ts"]

    def get_ctype(self):
        return self.json_obj["detail"]["ct"]

    def get_loclist(self):
        return self.json_obj["detail"]["loclist"]
        
    def get_extrameta(self):
        return self.json_obj["detail"]["extrameta"]
        
        

class NIHTTPHandler(BaseHTTPRequestHandler):

    # Fixed strings used in NI HTTP translations and requests
    WKN            = "/.well-known/"
    WKDIR          = "/ni_wkd/"
    NI_HTTP        = WKN + "ni"
    NDO_DIR        = "/ndo_dir/"
    META_DIR       = "/meta_dir/"
    NI_ACCESS_FORM = "/getputform.html"
    ALG_QUERY      = "?alg="
    NETINF_GET     = "netinfproto/get"
    NETINF_PUBLISH = "netinfproto/publish" 
    NETINF_PUT     = "netinfproto/put"
    NETINF_SEARCH  = "netinfproto/search"
    NETINF_LIST    = "netinfproto/list"

    # Type introducer string in cached file names
    TI             = "?c="

    def end_run(self):
        self.request_close()

    def handle(self):
        self.request_thread = threading.currentThread()
        self.thread_num = self.server.next_server_num
        self.request_thread.setName("NI HTTP handler - %d" %
                                    self.thread_num)
        self.server.next_server_num += 1

        # Tell listener we are running
        self.server.add_thread(self)
        
        # Logging functions
        self.loginfo = self.server.logger.info
        self.logdebug = self.server.logger.debug
        #self.logwarn = self.server.logger.warn
        #self.logerror = self.server.logger.error

        self.loginfo("New HTTP request connection from %s" % self.client_address[0])

        # Delegate to super class handler
        BaseHTTPRequestHandler.handle(self)
        
        self.loginfo("NI HTTP handler finishing")
        return

    def log_message(self, format, *args):
        """
        Log an arbitrary message.
        Overridden from base class to use logger functions

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client host and current date/time are prefixed to
        every message.

        """

        self.loginfo("%s - - [%s] %s\n" %
                      (self.address_string(),
                       self.log_date_time_string(),
                       format % args))
        return

    def mime_boundary(self):
        """
        @brief Create a MIME boundary string by hashing today's date
        @return ASCII string suitable for use as mime boundary
        """
        return "--" + hashlib.sha256(str(datetime.date.today())).hexdigest()

    def do_GET(self):
        """
        @brief Serve a GET request.
        """
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()
        return

    def do_HEAD(self):
        """
        @brief Serve a HEAD request.
        """
        f = self.send_head()
        if f:
            f.close()
        return

    def send_head(self):
        """
        @brief Common code for GET and HEAD commands.
        @return open file object ready for transfering data to HTTP output stream

        This sends the response code and MIME headers.

        @return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        There are three special cases:
        - Returning the form code
        - Getting a listing of the cache
        - Returning the NETINF favicon

        Otherwise, we expect either
        - a path that starts with the WKDIR prefix
          which is a direct acces for one of the cached files, or
        - a path that starts /.well-known/ni/

        """
        self.logdebug("GET or HEAD with path %s" % self.path)
        # Display the put/get form for this server.
        if (self.path.lower() == self.NI_ACCESS_FORM):
            f = StringIO()
            f.write(GET_PUT_FORM_HTML)
            file_len = f.tell()
            f.seek(0, os.SEEK_SET)
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(file_len))
            self.end_headers()
            return f

        if self.path.lower().startswith(self.NI_LIST):
            return self.showcache(self.path.lower())

        if (self.path.lower() == "/favicon.ico") :
            self.logdebug("Getting favicon")
            f = open("favicon.ico", 'rb')
            f.seek(0, os.SEEK_END)
            file_len = f.tell()
            f.seek(0, os.SEEK_SET)
            self.send_response(200)
            self.send_header("Content-type", "image/x-icon")
            self.send_header("Content-Length", str(file_len))
            self.end_headers()
            return f

        if (self.path.lower().startswith(self.WKDIR)):
            return self.send_get_header( \
                                         self.redirect_name_to_file_name( \
                                                self.server.storage_root,
                                                self.path))
            

        rv, ni_name, ndo_path, meta_path = self.translate_path(self.server.authority,
                                                               self.server.storage_root,
                                                               self.path)
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("Path format for %s inappropriate: %s" % (self.ndo_path,
                                                                   ni.ni_errs_txt[rv]))
            self.send_error(406, ni.ni_errs_txt[rv])
            return None

        return self.send_get_redirect(ni_name, path)

    def send_get_header(self, path):           
        """
        @brief Send headers for the response to a get request.
        @param prospective path of file
        @return open file object for copying data to output stream.

        The path has been derived from an ni: scheme URI but not yet
        verifed as extant.
        
        The cache of Named Data Objects contains files that have the
        digest as file name.  This makes it impossible to determine
        what the content type of the file is from the name.
        The content type of the file is stored in the metadata for the
        NDO in the parallel directory. If we weren't told what sort of
        file it was when the file was published or we can't deduce it
        from the contents then it defaults to application/octet-stream.

        For this routine:
        - Check the path corresponds to a real file
            - send 404 error if not
        - Get the canonical file name if it exists and extract minetype
            - Use application/octet-stream if can't be deduced this way
        - open the file and find out how large it is
            - send 404 error if opening for reading fails
        - send 200 OK and appropriate headers
        """
        f = None
        self.logdebug("send_get_header for path %s" % path)
        # Check if the path corresponds to an actual file
        if not os.path.isfile(path):
            self.loginfo("File does not exist: %s" % path)
            self.send_error(404)
            return None

        rpath = os.path.realpath(path)
        type_offset = rpath.find(self.TI)
        if (type_offset != -1):
            ctype = urllib.unquote(rpath[type_offset+len(self.TI):])
        else:
            ctype = self.server.default_mime_type
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not readable")
            return None
        self.send_response(200)
        self.send_header("Content-type", ctype)
        fs = os.fstat(f.fileno())
        self.send_header("Content-Length", str(fs[6]))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def send_get_redirect(self, ni_name, path):
        f = None
        # Check if the path corresponds to an actual file
        if not os.path.isfile(path):
            self.loginfo("File does not exist: %s" % path)
            self.send_error(404)
            return None

        rpath = os.path.realpath(path)
        type_offset = rpath.find(self.TI)
        if (type_offset != -1):
            ctype = urllib.unquote(rpath[type_offset+len(self.TI):])
        else:
            ctype = self.server.default_mime_type
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not readable")
            return None
        f.close()
        self.send_response(307)
        self.send_header("Location", "http://%s%s%s/%s" % (self.authority,
                                                            self.WKDIR,
                                                            ni_name.get_alg_name(),
                                                            ni_name.get_digest()))
        self.end_headers()
        
        return None

    def ni_name_to_file_name(self, storage_root, ni_name):
        """
        @brief make basic patname for ni_name in object cache
        @param root of directory tree for object cache
        @param ni: scheme URL encoded in a NIname object
        @return pathnames for NDO (content) and metadata files 

        Generate <storage root>/<hash alg identifier>/<digest>
        """
        ndo_name =  "%s%s%s/%s" % (storage_root,
                                   NDO_DIR,
                                   ni_name.get_alg_name(),
                                   ni_name.get_digest())
        meta_name =  "%s%s%s/%s" % (storage_root,
                                   META_DIR,
                                   ni_name.get_alg_name(),
                                   ni_name.get_digest())
        return (ndo_name, meta_name)


    def redirect_name_to_file_name(self, storage_root, redirect_name):
        """
        @brief make basic patname for redirect_name in object cache
        @param root of directory tree for object cache
        @param pathname as supplied to redirect for ni: .well-known name
        @return pathname for 'basic' file (no mimetype extension)

        Generate <storage root>/ndo_dir/<redirect_name less WKDIR prefix>
        """
        return "%s%s%s" % (storage_root, NDO_DIR,
                          redirect_name[len(self.WKDIR):])



    def translate_path(self, authority, storage_root, path):
        """
        @brief Translate a /-separated PATH to a ni_name and the local
        filename syntax.
        @param the FQDN of this node used to build ni name
        @param the root of the directory tree where ni Named Data Objects are cached
        @param the path from the HTTP request
        @return either (niSUCCESS. NIname instance, NDO path, metadata path) or
                       (error code from ni_errs, None, None, None) if errors found.

        Strips off the expected '/.well-know/ni' prefix and builds
        an ni name corresponding to the http: form. Validates the
        form of the ni name and then builds it into a local file name.
        The path is expected to have the form:
        /.well-known/ni/<digest name>/<url encoded digest>[?<query]

        If this is found, then it is turned into:
         - ni URI:        ni://<authority>/<digest name>;<url encoded digest>[?<query]
         - NDO filename:  <storage_root>/ndo_dir/<digest name>/<url encoded digest>
         - META filename:<storage_root>/meta_dir/<digest name>/<url encoded digest>
        Both are returned.
        
        """

        # Note: 'path' may contain param and query (nut not fragment) components
        if not path.startswith(self.NI_HTTP):
            return (ni.ni_errs.niBADURL, None, None)
        path = path[len(self.NI_HTTP):]
        if (len(path) == 0) or not path.startswith("/"):
            return (ni.ni_errs.niBADURL, None, None)
        dgstrt = path.find("/", 1)
        if dgstrt == -1:
            return (ni.ni_errs.niBADURL, None, None)
            
        url = "ni://%s%s;%s" % (authority, path[:dgstrt], path[dgstrt+1:])
        self.logdebug("path %s converted to url %s" % (path, url))
        ni_name = ni.NIname(url)
        rv = ni_name.validate_ni_url()
        if (rv != ni.ni_errs.niSUCCESS):
            return (rv, None, None, None)
        (ndo_path, meta_path) = self.ni_name_to_file_name(storage_root, ni_name)
        self.logdebug("NI URL: %s, NDO storage path: %s" % (url, ndo_path))

        return (ni.ni_errs.niSUCCESS, ni_name, ndo_path, meta_path)

    def copyfile(self, source, outputfile):
        """
        @brief Copy all data between two file objects.

        @param source is a file object open for reading
        (or anything with a read() method)
        @param outputfile is a file object open for writing
        (or anything with a write() method).
        @return void
        
        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        -- note however that this the default server uses this
        to copy binary data as well.
        """
        shutil.copyfileobj(source, outputfile)
        return

    def showcache(self, path):
        """
        @brief Code to generate a cache listing for some or all of the NDO cache.
        @param Path from original HTTP request (forced to lower case)
        @return Pseudo-file object containing the HTML to display listing

        This function is invoked for GET requests when the path is
        /netinfproto/list optionally qualified by a query string of the
        form ?alg=<hash algorithm name>.

        If there is no query string directory listings for all available
        hash algorithms are displayed.  Otherwise a listing for just one
        algorithm is displayed.  The set of available algorithms is defined by
        ni.NIname.get_all_algs() which returns a list of the textual names of
        the possible algorithms.

        There is a sub-directory below the (server.)storage_root for each of
        these algorithms.  These are the directories that are listed.  At present
        there are one or two entries for each file in ni_ndo and/or ni_meta
        sub-directories for each algorithm, each named by the digest of the
        content for the relevant algorithm:
        - The content file in the ni_ndo sub-directory if the content is available
        - The metadata file in the ni_meta sub-directory which contains information
          about the content as a JSON encoded string

        Because of the nature of the ni: digests, the second form of the name
        is a.s. unique, although there may be some issues with heavily
        truncated hashes where uniqueness is a smaller concept.

        This code dynamically builds some HTTP in a fixed width font to
        display the selected directory listing.
        """
        # Determine which directories to list - assume all by default
        algs_list = ni.NIname.get_all_algs()
        qo = len(self.NI_SHOWCACHE)
        if (len(path) > qo):
            # Check if there is a query string
            if not path[qo:].startswith(self.ALG_QUERY):
                # Not a valid query string
                if (path[qo] == '?'):
                    self.send_error(406, "Unrecognized query string in request")
                else:
                    self.send_error(400, "Unimplemented request")
                return None
            if path[(qo + len(self.ALG_QUERY)):] not in algs_list:
                self.send_error(404, "Cache for unknown algorithm requested")
                return
            algs_list = [ path[(qo + len(self.ALG_QUERY)):]]

        # Set up a StringIO buffer to gather the HTML
        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Named Data Object Cache Listing for server %s</title>\n" % self.server.server_name)
        f.write("<body>\n<h2>Named Data Object Cache Listing for server %s</h2>\n" % self.server.server_name)
        f.write("<hr>\n<ul>\n")

        # Server access netloc
        if (self.server.server_port == 80):
            # Can omit the defulat HTTP port
            netloc = self.server.server_name
        else:
            netloc = "%s:%d" % (self.server.server_name, self.server.server_port)

        # List all the algorithms selected as HTTP style URLs
        for alg in algs_list:
            dirpath = "%s%s%s" % (self.server.storage_root, NDO_DIR, alg)
            try:
                list = os.listdir(dirpath)
            except os.error:
                self.send_error(404, "No permission to list directory for algorithm %s" % alg)
                return None
            f.write("<h3>Cache Listing for Algorithm %s</h3>\n" % alg)
            list.sort(key=lambda a: a.lower())
            http_prefix = "%s/%s/" % (self.NI_HTTP, alg)
            for name in list:
                f.write('<li><a href="%s">%s</a>\n'
                        % ((http_prefix + name), cgi.escape(name)))
            f.write("\n")
        f.write("</ul>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f              

    def do_POST(self):
        """
        @breif Process NetInf POST requests.
        @return void
        
        NetInf uses a set of forms POSTed to URLs to transmit NetInf
        messages on the HTTP convergence layer.
        The URLS are of the form
        http://<destination netloc>/netinfproto/<msg type>
        where <msg_type> is 'get', 'publish' (alias 'put') ('search' to follow)

        This routine processes the form data ready to either retrieve a
        Named Data Object (NDO) from the local cache ('get' case) or
        insert a (new) NDO into the local cache ('publish' case).  The]
        actual details of the GET and PUBLISH operations are in
        subsidary routines netinf_get and netinf_publish.

        The cache is a directory tree rooted at the location specifed
        in self.server.storage_root with two parallel trees for NDO content
        and corresponding metadata.  Each tree in the cache has a directory per
        hash digest algorithm used to generate names using the names of the
        algorithms as directory names. (The main server program ensures
        that all relevant directories exist (or creates them) using the
        list of known algorithms retrieved from ni.NIname.get_all_algs().

        The corresponding content and metadata files share a name. The files in
        the cache are named using the url-safe base64 encoded
        digest used in ni: URIs. (NOTE: There is a small probability of
        clashing names for truncated hashes.)
        """
        
        # The NetInf proto uses a very limited set of requests..
        if not ((self.path == self.NETINF_GET) or (self.path == self.NETINF_PUBLISH)):
            self.logdebug("Unrecognized POST request: %s" % self.path)
            self.send_error(404, "POST %s is not used by NetInf" % self.path)
            return
        
        # Parse the form data posted
        self.loginfo("Headers: %s" % str(self.headers))
        form = cgi.FieldStorage(
            fp=self.rfile, 
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })

        # Call subsidiary routines to do the work
        if (self.path == self.NETINF_GET):
            self.netinf_get(form)
        elif (self.path == self.NETINF_PUBLISH):
            self.netinf_publish(form)
        else:
            raise ValueError()

        return

    def netinf_get(self, form):
        """
        @brief Process the decoded form sent with a POST NetInf get request
        @param Processed form data

        The form sent with a NetInf get request to
        http://<netloc>/.well-known/netinfproto/get
        must contain exactly the following fields:
        URI:    the ni: name for the NDO to be retrieved
        msgid:  an identifier used by the source to correlate replies
        ext:    placeholder for extension fields (no values currently defined)

        The routine
        - checks the relevant fields are present (and no more)
            - sends a 412 error if validation fails
        - turns the URI into a NIname instance and validates it
            - sends a 406 error if the validation fails
        - maps the ni: URI into a file name
            - sends a 404  error if the file does not exist
        - constructs headers and sends back the data (see do_GET).
        """
        # Validate form data
        # Check only expected keys and no more
        mandatory_get_fields = ["URI", "msgid"]
        optional_get_fields = ["ext"]
        for field in mandatory_get_fields:
            if field not in form.keys():
                self.logdebug("Missing mandatory field %s in get form")
                self.send_error(412, "Missing mandatory field %s in form." % field)
                return
        ofc = 0
        for field in optional_get_fields:
            if field in form.keys():
                ofc += 1
                
        if (len(form.keys()) > (len(mandatory_get_fields) + ofc)):
            self.logdebug("NetInf get form has too many fields: %s" % str(form.keys()))
            self.send_error(412, "Form has unxepected extra fields beyond %s" % (str(mandatory_get_fields)+
                                                                                 str(optional_get_fields)))
        self.logdebug("NetInf get for URI %s, nsgid %s, ext %s" % (form["URI"].value,
                                                                   form["msgid"].value,
                                                                   form["ext"].value))
        
        # Generate NIname and validate it (it should have a Params field).
        ni_name = ni.NIname(form["URI"].value)
        rv = ni_name.validate_ni_url()
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni.ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni.ni_errs_txt[rv])
            return

        # Turn the ni_name into paths for NDO and metadata.
        # Then send the headers if all is well
        (ndo_path, meta_path) = self.ni_name_to_file_name(self.server.storage_root, ni_name)
        # send_get_header returns open file pointer to file to be returned (or None)
        f = self.send_get_header(ndo_path, meta_path)
        if f:
            self.copyfile(f, self.wfile)
            f.close()
        return

    def netinf_publish(self, form):
        """
        @brief Process the decoded form sent with a POST NetInf publish request
        @param Processed form data

        The form sent with a NetInf publish request to
        http://<netloc>/netinfproto/publish (or .../put)
        must contain at least the following fields:
        URI:    the ni: name for the NDO to be published
        msgid:  an identifier used by the source to correlate replies

        It may also contain
        fullPut:boolean value indicating if octets should be expected
        octets: the file to be published (with a filename attribute)
        ext:    placeholder for extension fields (no values currently defined)
        loc1:   a location (FQDN) where the file might be found
        loc2:   another location (FQDN) where the file might be found

        A request must contain either fullPut and the octets or, loc1 and/or
        loc2.  It may contain both types of information.

        There may also be a content type for the file in the query string
        part of the URI (path) in the form ?ct="<mimetype>".  Should be
        accessible from ni name structure. 

        The routine
        - checks the relevant fields are present (and no more)
            - sends a 412 error if validation fails
        - turns the URI into a NIname instance and validates it
            - sends a 406 error if the validation fails
        - maps the ni: URI into file names (for content and metadata)
            - if the content file already exists updates the metadata
            - if the metatdats update succeeds send a 304 response(with the mod time here)
            - if the metedata update fails send a 401 error 
        - if fullPut is set saves the file using the filetype and creating the file
          with the digest name; updates/cretes the metadata file
            - sends a 401 error if either of the files cannot be written
        - returns 200 OK if caching succeeded
        """
        # Validate form data
        # Check only expected keys and no more
        mandatory_publish_fields = ["URI",  "msgid"]
        optional_publish_fields = ["ext", "loc2", "fullPut", "octets", "loc1"]
        for field in mandatory_publish_fields:
            if field not in form.keys():
                self.logdebug("Missing mandatory field %s in get form")
                self.send_error(412, "Missing mandatory field %s in form." % field)
                return
        ofc = 0
        for field in optional_publish_fields:
            if field in form.keys():
                ofc += 1
                
        if (len(form.keys()) > (len(mandatory_publish_fields) + ofc)):
            self.logdebug("NetInf publish form has too many fields: %s" % str(form.keys()))
            self.send_error(412, "Form has unxepected extra fields beyond %s" % (str(mandatory_publish_fields)+
                                                                                 str(optional_publish_fields)))
            return

        # Either fullPut must be set or loc1 or loc2 must be present
        if not ( "fullPut" in form.keys() or "loc1" in form.keys() or "loc2" in form.keys()):
            self.logdebug("NetInf publish form must contain at least one of fullPut, loc1 and loc2.")
            self.send_error(412, "Form must have at least one of fields 'fullPut', 'loc1' and 'loc2'.")
            return
            
        # If fullPut is supplied then there must be octets which is a file
        file_uploaded = False
        timestamp = None
        if "fullPut" in form.keys() and form.getvalue("fullPut"):
            if not "octets" in form.keys():
                self.logdebug("Expected 'octets' form field to be present with 'fullPut' set")
                seld.send_error(412, "Form field 'octets' not present when 'fullPut' set.")
                return
            if form["octets"].filename is None:
                self.logdebug("Expected 'octets' form field to be a file but has no filename attribute")
                seld.send_error(412, "Form field 'octets' does not contain an uploaded file")
                return
            # Record that there is a file ready
            file_uploaded = True
            timestamp = self.date_time_string()

        
        self.logdebug("NetInf publish for "
                      "URI %s, fullPut %s octets %s, msgid %s, ext %s,"
                      "loc1 %s, loc2 %s at %s" % (form["URI"].value,
                                                  form["fullPut"].value,
                                                  form["octets"].filename,
                                                  form["msgid"].value,
                                                  form["ext"].value,
                                                  form["loc1"].value,
                                                  form["loc2"].value,
                                                  timestamp))
        
        # Generate NIname and validate it (it should have a Params field).
        ni_name = ni.NIname(form["URI"].value)
        rv = ni_name.validate_ni_url()
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni.ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni.ni_errs_txt[rv])
            return

        # Turn the ni_name into NDO and metadate file paths
        (ndo_path, meta_path) = self.ni_name_to_file_name(self.server.storage_root, ni_name)

        # We don't know what the content type is yet
        ctype = None

        # If the form data contains an uploaded file...
        if file_uploaded:
            # Copy the file from the network to a temporary name in the right
            # subdirectory of the storage_root.  This makes it trivial to rename it
            # once the digest has been verified.
            # This file name is unique to this thread and because it has # in it
            # should never conflict with a digested file name which doesn't use #.
            temp_name = "%s/%s/publish#temp#%d" % (self.server.storage_root,
                                                   ni_name.get_alg_name(),
                                                   self.thread_num)
            self.logdebug("Copying and digesting to temporary file %s" % temp_name)

            # Prepare hashing mechanisms
            hash_function = ni_name.get_hash_function()()

            # Copy file from incoming stream and generate digest
            try:
                f = open(temp_name, "wb");
            except Exception, e:
                self.loginfo("Failed to open temp file %s for writing: %s)" % (temp_name, str(e)))
                self.send_error(500, "Cannot open temporary file")
                return
            file_len = 0
            g = form["octets"].file
            while 1:
                buf = g.read(16 * 1024)
                if not buf:
                    break
                f.write(buf)
                hash_function.update(buf)
                file_len += len(buf)
            f.close()
            self.logdebug("Finished copying")

            # Check the file was completely sent (not interrupted or cancelled by user
            if form["octets"].done == -1:
                self.logdebug("File referenced by 'octets' form field incompletely uploaded")
                seld.send_error(412, "Upload of file referenced by 'octets' form field cancelled or interrupted by user")
                return
         
            # Get binary digest and convert to urlsafe base64 encoding
            bin_dgst = hash_function.digest()
            if (len(bin_dgst) != ni_name.get_digest_length()):
                self.logdebug("Binary digest has unexpected length")
                self.send_error(500, "Calculated binary digest has wrong length")
                os.remove(temp_name)
                return
            digest = ni.NIproc.make_urldigest(bin_dgst[:ni_name.get_truncated_length()])
            if digest is None:
                self.logdebug("Failed to create urlsafe bas64 encoded digest")
                self.send_error(500, "Failed to create urlsafe bas64 encoded digest")
                os.remove(temp_name)
                return

            # Check digest matches with digest in ni name in URI field
            if (digest != ni_name.get_digest()):
                self.loginfo("Digest calculated from incoming file does not match digest in ni; name")
                send_error(401, "Digest of incoming file does match specified ni;  URI")
                os.remove(temp_name)
                return

            # Work out content type for received file
            ctype = form["octets"].type
            self.logdebug("Supplied content type from form is %s" % ctype)

            if ctype is None:
                (ctype, encoding) = mimetypes.guess_type(temp_name, strict=False)
            
        # If ct= query string supplied in URL field..
        #   Override type got via received file if there was one but log warning if different
        qs = ni_name.get_query_string()
        if not (qs == ""):
            ct = re.search(r'ct\w*=\w*("[^"]+")', qs)
            if not (ct is  None or ct.group(1) == ""):
                if not (ctype is None or ctype == ct.group(1)):
                    self.logwarn("Inconsistent content types detected: %s and %s" % \
                                 (ctype, ct.group(1)))
                ctype = ct.group(1)

        # Set the default content type if we haven't been able to set it so far but have got a file
        # If we haven't got a file then we just leave it unassigned
        if ctype is None and file_uploaded:
            # Default..
            ctype = self.default_mime_type

        # Check if the metadata file exists - i.e., if this is an update
        if os.path.isfile(meta_path):
            # It does - had previous publish so update metadata
            md = update_metadata(meta_path, form, timestamp, ctype)
            if md is None:
                self.logerror("Unable to update metadata file %s" % meta_path)
                self.send_error(500, "Unable to upddate metadata file for %s" % \
                                ni_name.get_url())

            # Check the ni is the same - only affects query string
            # Assume for the time being that we expect exactly the same string
            # This is not really right as the query string need not be present
            # and there could be variations in white space
            if form["URI"].value != md.get_ni():
                self.logerror("Update uses different URI - old: %s; new: %s" % \
                              (md.get_ni(), form["URI"].value))
                self.send_error(412, "Publish update uses different ni - previous was %s" % \
                                md.get_ni())
                return

            # Check if ctype in existing metadata is consistent with new ctype
            if not((ctype is None) or (md.get_ctype() == ctype)):
                self.logerror("Update uses different content type - old: %s; new: %s" % \
                              (md.get_ctype(), ctype))
                self.send_error(412, "Publish update uses different ni - previous was %s" % \
                                md.get_ctype())
                return
                
        else:
            md = store_metadata(meta_path, form, timestamp, ctype)

        # Check if the path corresponds to an actual content file
        if os.path.isfile(ndo_path):
            self.loginfo("Content file already exists: %s" % ndo_path)
            # Discarding uploaded copy if received
            if file_uploaded:
                try:
                    os.remove(temp_name)
                except Exception, e:
                    self.loginfo("Failed to unlink temp file %s: %s)" % (temp_name, str(e)))
                    self.send_error(500, "Cannot unlink temporary file")
                    return
                    
            md = update_metadata(meta_path, form, ctype)
            if md is None:
                self.logerror("Unable to update metadata file %s" % meta_path)
                self.send_error(500, "Unable to upddate metadata file for %s" % \
                                ni_name.get_url())
            ts = md.get_timestamp()
            fs = os.stat(ndo_path)

            mb = self.mime_boundary()

            f = StringIO()
            f.write(mb + "\r\n")
            f.write("Content-Type: text/html\r\n")
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n')
            f.write("<html>\n<title>NetInf PUBLISH Report</title>\n")
            f.write("<h2>NetInf PUBLISH Report</h2>\n")
            f.write("\n<p>File %s is already in cache as '%s' (%d octets)</p>\n" % (form["octets"].filename,
                                                                                    ni_name.get_url(),
                                                                                    fs[6]))
            f.write("\n</body>\n</html>\r\n\r\n")
            f.write(mb + "\r\n")
            f.write("Content-Type: application/json\r\n")
            json.dump({ "status": "updated", "msgid" : form["msgid"].value,
                        "loclist" : md.get_loclist() }, f)
            f.write("\r\n\r\n" + mb + "-\r\n")
                    
            length = f.tell()
            f.seek(0)
            self.send_response(200, "Object already in cache here")
            self.send_header("MIME-Version", "1.0")
            self.send_header("Content-Type", "multipart/mixed; boundary=%s" % mb)
            self.send_header("Content-Disposition", "inline")
            self.send_header("Content-Length", str(length))
            # Ensure response not cached
            self.send_header("Expires", "Thu, 01-Jan-70 00:00:01 GMT")
            self.send_header("Last-Modified", ts)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            # IE extensions - extra header
            self.send_header("Cache-Control", "post-check=0, pre-check=0")
            # This seems irrelevant to a response
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(f.read())

            return

        # Rename the temporary file to be the long name with query string
        try:
            os.rename(temp_name, ndo_path)
        except:
            os.remove(temp_name)
            self.logerror("Unable to rename tmp file %s to %s: %s" % (temp_name, ndo_path, str(e)))
            self.send_error(500, "Unable to rename temporary file")
            return

        # Set up the metadata
        md = 
                    

        # Generate a nice response
        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>NetInf PUBLISH Report</title>\n")
        f.write("<h2>NetInf PUBLISH Report</h2>\n")
        f.write("\n<p>Uploaded %s as '%s' (%d octets)</p>\n" % (form["octets"].filename,
                                                                    ni_name.get_url(),
                                                                    file_len))
        f.write("\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.wfile.write(f.read())
        return

    def store_metadata(self, meta_path, form, timestamp, ctype):
        """
        @brief Create new metadata file for a cached NDO from form data etc
        @param File name for metadata file
        @param processed form data
        @param content type (maybe None if no uploaded file)
        @return NetInfMetaData instance that was written to file or None if a problem

        The file contains JSON encoded metadata created by writing
        a JSON encoded NetInfMetaData class instance to the file.

        Contract: The meta_path file does not exist on entry
        """

        try:
            f = open(meta_path, "w")
        except Exception, e:
            logerror("Unable to create metadata file %s: %s", % (meta_path, str(e)))
            return None

        md = NetInfMetaData
    
    
class NIHTTPServer(ThreadingMixIn, HTTPServer):
    def __init__(self, addr, storage_root, authority, logger):
        # These are used  by individual requests
        # accessed via self.server in the handle function
        self.storage_root = storage_root
        self.authority = authority
        self.logger = logger
        
        self.running_threads = set()
        self.next_server_num = 1

        # Default mimetype to use when we don't know.
        self.default_mime_type = 'application/octet-stream'

        # JSON encoder and decoder for use with metadata
        # Use all defaults for JSON processing (i.e. ascii output)
        self.json_enc = json.JSONEncoder()
        self.json_dec = json.JSONDecoder()


        # Setup to produce a daemon thread for each incoming request
        # and be able to reuse address
        HTTPServer.__init__(self, addr, NIHTTPHandler,
                            bind_and_activate=False)
        self.allow_reuse_address = True
        self.server_bind()
        self.server_activate()
                         
        self.daemon_threads = True

    def add_thread(self, thread):
        self.logger.debug("New thread added")
        self.running_threads.add(thread)

    def remove_thread(self, thread):
        if thread in self.running_threads:
            self.running_threads.remove(thread)

    def end_run(self):
        for thread in self.running_threads:
            if thread.request_thread.isAlive():
                thread.request.close()
        del self.running_threads
        self.shutdown()

def ni_http_server(storage_root, authority, server_port, logger):
    #HOST, PORT = "mightyatom.folly.org.uk", 8080
    print authority, server_port
    return NIHTTPServer((authority, server_port), storage_root,
                         "%s:%d" % (authority, server_port), logger)

#=========================================================================

if __name__ == "__main__":
    import time
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(levelname)s %(threadName)s %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Port 0 means to select an arbitrary unused port
    HOST, PORT = "localhost", 0

    def client(ip, port, message):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((HOST, PORT))
        sock.connect((ip, port))
        sock.send(message)
        time.sleep(1)
        m = sock.recv(4096)
        sock.close()
        return m

    # Create a dummy file to get
    sd = "/tmp"
    shutil.rmtree(sd+"/sha-256", ignore_errors=True)
    os.mkdir(sd+"/sha-256")
    fn = "/sha-256/abcdef-12f"
    full_fn = sd+fn+"?c=image%2fjpeg"
    f = open(full_fn, "w")
    f.write("The quick yellow fox burrowed under the twisting worm.\n")
    f.close()
    os.symlink(full_fn, sd+fn)

    fd="""--dbb76dd438094382bb923100624d68da
Content-Disposition: form-data; name="URI"
Content-Type: text/plain; charset=utf-8

ni://folly.org.uk/sha-256;WMeBb88-F_766WdGo9fPyBZ3ZOh6GXbzXIL1LG9X23g
--dbb76dd438094382bb923100624d68da
Content-Disposition: form-data; name="msgid"
Content-Type: text/plain; charset=utf-8

19319
--dbb76dd438094382bb923100624d68da
Content-Disposition: form-data; name="ext"
Content-Type: text/plain; charset=utf-8

ignored
--dbb76dd438094382bb923100624d68da

"""
    
    server = NIHTTPServer((HOST, PORT), "/tmp", "example.com", logger)
    ip, port = server.server_address

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=server.serve_forever,
                                     name="Niserver Listener")
    # Exit the server thread when the main thread terminates
    server_thread.setDaemon(True)
    server_thread.start()
    logger.info("Server loop running in thread:%s" % server_thread.getName())

    # Note server will hang if sent message with just one \r\n on the end
    # Needs to be thought about (timeouts!)
    logger.info(client(ip, port, "GET /some/path HTTP/1.0\r\n\r\n"))
    logger.info(client(ip, port, "GET /other/path;digest?q=d#dfgg HTTP/1.0\r\n\r\n"))
    logger.info(client(ip, port, "BURP /other/path HTTP/1.0\r\n\r\n"))
    logger.info(client(ip, port, "GET %s HTTP/1.0\r\n\r\n" % ("/.well-known/ni"+fn)))
    logger.info(client(ip, port, "POST %s HTTP/1.0\r\n%s" % ("/.well-known/netinfproto/get", fd)))
    server.end_run()
    logger.info("Server shutdown")
