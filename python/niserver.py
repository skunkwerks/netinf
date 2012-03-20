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

Creates a threaded HTTP server that responds to a limited set of URLs
- GET/HEAD on path /.well-known/ni/<digest algorithm id>/<digest>
- POST on paths /.well-known/netinfproto/get and
                /.well-known/netinfproto/publish
  (again SEARCH to follow)

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

Revision History
================
Version   Date       Author         Notes
0.0	  12/02/2012 Elwyn Davies   Created for SAIL codesprint.
"""

import os
import socket
import threading
import logging
import shutil
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

<form name="fetchni" action=".well-known/netinfproto/get" method="post">
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

<form name="fetchni" action=".well-known/netinfproto/publish" enctype="multipart/form-data" method="post">
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


</body>
</html>

"""


import ni

class NIHTTPHandler(BaseHTTPRequestHandler):

    # Fixed strings used in NI HTTP translations and requests
    WKN            = "/.well-known/"
    NI_HTTP        = WKN + "ni"
    NI_ACCESS_FORM = "/getputform.html"
    NI_SHOWCACHE   = "/showcache.html"
    ALG_QUERY      = "?alg="
    NETINF_GET     = WKN + "netinfproto/get"
    NETINF_PUBLISH = WKN + "netinfproto/publish"

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

        There are two special cases:
        - Returning the form code
        - Getting a listing of the cache

        """
        # Display the put/get form for this server.
        if (self.path.lower() == self.NI_ACCESS_FORM):
            f = StringIO()
            f.write(GET_PUT_FORM_HTML)
            file_len = f.tell()
            f.seek(0)
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(file_len))
            self.end_headers()
            return f

        if self.path.lower().startswith(self.NI_SHOWCACHE):
            return self.showcache(self.path.lower())

        rv, ni_name, path = self.translate_path(self.server.authority,
                                                self.server.storage_root,
                                                self.path)
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("Path format for %s inappropriate: %s" % (self.path,
                                                                   ni.ni_errs_txt[rv]))
            self.send_error(406, ni.ni_errs_txt[rv])
            return None

        return self.send_get_header(path)

    def send_get_header(self, path):           
        """
        @brief Send headers for the response to a get request.
        @param prospective path of file
        @return open file object for copying data to output stream.

        The path has been derived from an ni: scheme URI but not yet
        verifed as extant.
        
        The cache of Named Data Objects contains files that have the
        digest as file name.  This makes it impossible to determine
        what the content of the file is from the name.
        To get round this, when the files are published, the master file
        is created with a name that consists of the digest followed by
        a query string, thus ?c=x%2fy, representing a MIME type of x/y.
        Then the file with just the digest as name is made a soft link
        to this file.  If we weren't told what sort of file it was when
        the file was published it defaults to application/octet-stream.
        Thus we can find the type of the file by executing os.realpath()
        on the pure digest name and extracting the query string. Note that
        '/' has to be %-encoded in the query string to avoid upsetting
        path algorithm finders.

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
        # Check if the path corresponds to an actual file
        if not os.path.isfile(path):
            self.loginfo("File does not exists: %s" % path)
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

    def ni_name_to_file_name(self, storage_root, ni_name):
        """
        @brief make basic patname for ni_name in object cache
        @param root of directory tree for object cache
        @param ni: scheme URL encoded in a NIname object
        @return pathname for 'basic' file (no mimetype extension)

        Generate <storage root>/<hash alg identifier>/<digest>
        """
        return "%s/%s/%s" % (storage_root,
                             ni_name.get_alg_name(),
                             ni_name.get_digest())


    def translate_path(self, authority, storage_root, path):
        """
        @brief Translate a /-separated PATH to a ni_name and the local
        filename syntax.
        @param the FQDN of this node used to build ni name
        @param the root of the directory tree where ni Named Data Objects are cached
        @param the path from the HTTP request
        @return either (niSUCCESS. NIname instance, pathbame) or
                       (error code from ni_errs, None, None) if errors found.

        Strips off the expected '/.well-know/ni' prefix and builds
        an ni name corresponding to the http: form. Validates the
        form of the ni name and then builds it into a local file name.
        The path is expected to have the form:
        /.well-known/ni/<digest name>/<url encoded digest>[?<query][#<fragment>]

        If this is found, then it is turned into:
         - ni URI:   ni://<authority>/<digest name>;<url encoded digest>[?<query][#<fragment>]
         - filename: <storage_root>/<digest name>/<url encoded digest>
        Both are returned.
        
        """

        # Note: 'path' may contain param, query and fragment components
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
            return (rv, None, None)
        path = self.ni_name_to_file_name(storage_root, ni_name)
        self.logdebug("NI URL: %s, storage path: %s" % (url, path))

        return (ni.ni_errs.niSUCCESS, url, path)

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

        This function is invoked when the path is /showcache.html optionally
        qualified by a query string of the form ?alg=<hash algorithm name>.

        If there is no query string directory listings for all available
        hash algorithms are displayed.  Otherwise a listing for just one
        algorithm is displayed.  The set of available algorithms is defined by
        ni.NIname.get_all_algs() which returns a list of the textual names of
        the possible algorithms.

        There is a sub-directory below the (server.)storage_root for each of
        these algorithms.  These ae the directories that are listed.  At present
        there are two entries for each file:
        - The master entry which contains a 'query string' indicating the
          mimetype of the file in the form '?c=type%2fsubtype' tagged onto the
          digest of the file content in rlsafe bas64 encoding.
        - A soft link to this file which just has the digest as name.

        Because of the nature of the ni: digests, the second form of the name
        is a.s. unique, although there may be some issues with heavily
        truncated hashes where uniqueness is a smaller concept.

        This code dynamically builds some HTTP in a fixed width font to
        display the selected directory listing.
        """
        # Determine which directories to list -assume all by default
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
            dirpath = "%s/%s" % (self.server.storage_root, alg)
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
        http://<destination netloc>/.well-known/netinfproto/<msg type>
        where <msg_type> is 'get' or 'publish' ('search' to follow)

        This routine processes the form data ready to either retrieve a
        Named Data Object (NDO) from the local cache ('get' case) or
        insert a (new) NDO into the local cache ('publish' case).  The]
        actual details of the GET and PUBLISH operations are in
        subsidary routines netinf_get and netinf_publish.

        The cache is a directory tree rooted at the location specifed
        in self.server.storage_root.  The cache has a directory per
        hash digest algorithm used to generate using the names of the
        algorithms as directory names. (The main server program ensures
        that all relevant directories exist (or creates them) using the
        list of known algorithms retieved from ni.NIname.get_all_algs().

        The files in the cache are named using the url-safe base64 encoded
        digest used in ni: URIs. Each file has a canonical name that consists
        of the digest with a 'query string' appended that identifies the
        mimetype of the file in the form '?c=<type>%2f<subtype>' where the
        '/' that would normally be seen in a mimetype is %-encoded to avoid
        it being seen as a path separator.  There is then a soft link to
        this file from a name that just uses the digest (which is essentially
        guaranteed to be unique for the complete hash digests - there is a
        potential issue with truncated hashes.. TBD).
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

        # Turn the ni_name into a path and send the headers if all is well
        path = self.ni_name_to_file_name(self.server.storage_root, ni_name)
        # send_get_header returns open file pointer to file to be returned (or None)
        f = self.send_get_header(path)
        if f:
            self.copyfile(f, self.wfile)
            f.close()
        return

    def netinf_publish(self, form):
        """
        @brief Process the decoded form sent with a POST NetInf publish request
        @param Processed form data

        The form sent with a NetInf publish request to
        http://<netloc>/.well-known/netinfproto/publish
        must contain at least the following fields:
        URI:    the ni: name for the NDO to be published
        octets: the file to be published (with a filename attribute)
        msgid:  an identifier used by the source to correlate replies
        ext:    placeholder for extension fields (no values currently defined)
        loc1:   a location (FQDN) where the file might be found

        It may also contain
        loc2:   another location (FQDN) where the file might be found

        The routine
        - checks the relevant fields are present (and no more)
            - sends a 412 error if validation fails
        - turns the URI into a NIname instance and validates it
            - sends a 406 error if the validation fails
        - maps the ni: URI into a file name
            - sends a 304 response if the file already exists (with the mod time here
        - saves the file using the filetype and creating the 'naked' digest name link
            - sends a 401 error if the file cannot be written
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
        if form["octets"].filename is None:
            self.logdebug("Expected 'octets' form field to be a file but has no filename attribute")
            seld.send_error(412, "Form field 'octets' does contain an uplaoded file")
            return
        
        self.logdebug("NetInf publish for URI %s, octets %s, msgid %s, ext %s, loc1 %s" % (form["URI"].value,
                                                                                           form["octets"].filename,
                                                                                           form["msgid"].value,
                                                                                           form["ext"].value,
                                                                                           form["loc1"].value))
        
        # Generate NIname and validate it (it should have a Params field).
        ni_name = ni.NIname(form["URI"].value)
        rv = ni_name.validate_ni_url()
        if rv is not ni.ni_errs.niSUCCESS:
            self.loginfo("URI format of %s inappropriate: %s" % (self.path,
                                                                 ni.ni_errs_txt[rv]))
            self.send_error(406, "ni: scheme URI not in appropriate format: %s" % ni.ni_errs_txt[rv])
            return

        # Turn the ni_name into a path
        path = self.ni_name_to_file_name(self.server.storage_root, ni_name)
        # Check if the path corresponds to an actual file
        if os.path.isfile(path):
            self.loginfo("File already exists: %s" % path)
            fs = os.stat(path)
            f = StringIO()
            f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
            f.write("<html>\n<title>NetInf PUBLISH Report</title>\n")
            f.write("<h2>NetInf PUBLISH Report</h2>\n")
            f.write("\n<p>File %s is already in cache as '%s' (%d octets)</p>\n" % (form["octets"].filename,
                                                                                    ni_name.get_url(),
                                                                                    fs[6]))
            f.write("\n</body>\n</html>\n")
            length = f.tell()
            f.seek(0)
            self.send_response(200, "Object already in cache here")
            self.send_header("Content-Length", str(length))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            self.wfile.write(f.read())
            return

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

        # Get binary digest and convert to urlsafe base64 encoding
        bin_dgst = hash_function.digest()
        if (len(bin_dgst) != ni_name.get_digest_length()):
            os.remove(temp_name)
            self.logdebug("Binary digest has unexpected length")
            self.send_error(500, "Calculated binary digest has wrong length")
            return
        digest = ni.NIproc.make_urldigest(bin_dgst[:ni_name.get_truncated_length()])
        if digest is None:
            os.remove(temp_name)
            self.logdebug("Failed to create urlsafe bas64 encoded digest")
            self.send_error(500, "Failed to create urlsafe bas64 encoded digest")
            return

        # Check digest matches with digest in ni name in URI field
        if (digest != ni_name.get_digest()):
            os.remove(temp_name)
            self.loginfo("Digest calculated from incoming file does not match digest in ni; name")
            send_error(401, "Digest of incoming file does match specified ni;  URI")
            return

        # Create 'real path name' with mimetype in query string
        ctype = form["octets"].type
        self.logdebug("Content type is %s" % ctype)
        query_str = "?c="+"%2f".join(ctype.split("/"))
        rpath = path + query_str

        # To be sure, to be sure...
        # This should not happen
        if os.path.isfile(rpath):
            os.remove(temp_name)
            self.logerror("File already exists - should not be possible: %s" % rpath)
            self.send_error(500, "Alternative name exists in cache when it should not")
            return

        # Rename the temporary file to be the long name with query string
        try:
            os.rename(temp_name, rpath)
        except:
            os.remove(temp_name)
            self.logerror("Unable to rename tmp file %s to %s: %s" % (temp_name, rpath, str(e)))
            self.send_error(500, "Unable to rename temporary file")
            return

        # Create a soft link to the ful name from the digest name.
        try:
            os.symlink(rpath, path)
        except:
            os.remove(rpath)
            self.logerror("Unable to create symlink for %s from %s: %s" % (path, rpath, str(e)))
            self.send_error(500, "Unable to link full name to short name")
            return

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

def ni_http_server(storage_root, authority, logger):
    HOST, PORT = "localhost", 8080
    return NIHTTPServer((HOST, PORT), storage_root,
                         authority, logger)

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
