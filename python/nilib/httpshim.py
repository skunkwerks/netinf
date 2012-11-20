#!/usr/bin/python
"""
@package nilib
@file httpshim.py
@brief Request handler shim for  NI NetInf HTTP convergence layer (CL) server
@brief and NRS server.  Shim to adapt BaseHTTPHandler for NIHTTPHandler.
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
httpshim.py overview

This module defines a version of the HTTPRequestShim class that adapts the
standard BaseHTTPHandler class for use with NIHTTPHandler in nihandler.py.

NIHTTPHandler was initially written as a derivative of BaseHTTPHandler so
this shim class is fairly minimal.  The reason for having this shim and the
alternative in wsgishim.py is to allow the same handler code to be used either
in a lightweight standalone HTTP server specifically for NetInf functionality
or to be invoked through the mod_wsgi interface from an Apache HTTP server.

The main functions of the shim are:
- to provide a common way of accessing the various instance variables listed
  independent of how the information is supplied by the server that invokes the
  handler,
- to conceal the details of how the server invokes the handler such as threading,
- to set up uniform logging capabilities, and
- to provide a uniform interface to the generation of the response body for a
  request.

The handler expects to have the following instance variables set up:

1) As expected in any handler derived from BaseHTTPHandler
- server_port      the TCP port used by the HTTP server listener (default 8080)
- server_name      the hostname part of the address of the HTTP server
- authority        Combination of server_name and server_port as expected in
                   netloc portion of a URL.
- command          the operation in the HTTP request
- path             the path portion plus query and fragments of the request
- rfile            file representing input request stream positioned after
                   any request headers have been read.
- DEFAULT_ERROR_MESSAGE
                   template for error response HTML sent by send_error.  
[Note: BaseHTTPHandler provides some extra items that are not currently used
 by nihandler.py.  If these are pressed into use, they may have to be emulated
 in the WSGI shim case. These include: requestline, raw_requestline,
 protocol_version, request_version, client_address.  See note below regarding
 wfile which should not be used.]
                  
2) Specific items passed from the HTTPServer instance managing the handler:
- storage_root     the base directory where the content cache is stored
- provide_nrs      flag indicating if NRS operations should be supported by
                   this server
- redis_nrs        REDIS server connection (None if provide_nrs is False)
- getputform       pathname for a file containing the HTML code uploaded to show
                   the NetInf GET/PUBLISH/SEARCH forms in a browser
- nrsform          pathname for file containing the HTML code uploaded to show
                   the NetInf NRS configuration forms in a browser
- favicon          pathname for favicon file sent to browsers for display.

3) Convenience functions to provide logging functions at various informational
   levels (each takes a string to be logged):
- logdebug
- logerror
- logwarn
- loginfo

4) The following routines are used to wrap the sending of strings and whole files
   as part of a response.  This is done so that self.wfile does not appear
   explicitly in the nihandler.py code so that the same interface can be used for
   the WSGI shim.  [In that case the responses are acumulated as an iterable
   rather than being written directly to a file.]
- send_string
- send_file

The handler expects the following standard methods in BaseHTTPHandler to be available:
- date_time_string Date/time string when request processed
- send_error       Send an HTTP error code and message as response
- headers          Dictionary like accessor for request headers
- send_request     Send an HTTP (success) code and message as first part of response
- send_header      Send a single header as part of response
- end_headers      Send header terminator (blank) line as part of response


@code
Revision History
================
Version   Date       Author         Notes
0.0       17/11/2012 Elwyn Davies   Split out from niserver.py and adapted to
                                    allow use with either WSGI or BaseHTTPHandler.

@endcode
"""
import threading
import shutil
from BaseHTTPServer import BaseHTTPRequestHandler

#==============================================================================#
class HTTPRequestShim(BaseHTTPRequestHandler):
    
    #--------------------------------------------------------------------------#
    # INSTANCE VARIABLES

    # === Thread information ===
    ##@var request_thread
    # The thread identifier retrieved from threading.CurrentThread()
    ##@var thread_num
    # Sequence number for threads controlled by next_handler_num in
    # the NIHTTPServers.  Incorporated in thread name to identify thread.

    # === Logging convenience functions ===
    ##@var loginfo
    # Convenience function for logging informational messages
    ##@var logdebug
    # Convenience function for logging debugging messages
    ##@var logwarn
    # Convenience function for logging warning messages
    ##@var logerror
    # Convenience function for logging error reporting messages
    
    #--------------------------------------------------------------------------#
    def handle(self):
        """
        @brief Wrapper round superclass handle() function setting up context.
        @return (none)

        Obtain unique sequence number for handler thread and make name
        for thread using it when connection is opened.

        Inform HTTPServer listener that thread is running.

        Generate convenience function variables for various levels of logging.

        Call superclass handle() function to manage requests -  farms out
        requests to 'do_GET', 'do_HEAD' or 'do_POST' according to request
        type.  There may be several requests on a single connection if
        requests specify 'Connect: keep-alive'.

        After all requests have been processed, inform HTTPServer listener that
        thread is no longer running.
        """
        
        # Record thread identifier in instance and set up thread name.
        self.request_thread = threading.currentThread()
        # Serialize access to next_handler_num
        with self.server.thread_running_lock:
            self.thread_num = self.server.next_handler_num
            self.server.next_handler_num += 1
        self.request_thread.setName("NI HTTP handler - %d" %
                                    self.thread_num)

        # Tell listener we are running
        self.server.add_thread(self)
        
        # Logging functions
        self.loginfo = self.server.logger.info
        self.logdebug = self.server.logger.debug
        self.logwarn = self.server.logger.warn
        self.logerror = self.server.logger.error

        # Copy items referenced via self.server to instance varisbles
        # Allows alternative use of WSGI environ by actual handler routiens.
        self.storage_root = self.server.storage_root
        self.getputform = self.server.getputform
        self.nrsform = self.server.nrsform
        self.provide_nrs = self.server.provide_nrs
        self.favicon = self.server.favicon
        self.authority = self.server.authority
        self.server_name = self.server.server_name
        self.server_port = self.server.server_port
        self.nrs_redis = self.server.nrs_redis

        self.loginfo("New HTTP request connection from %s" % self.client_address[0])

        # Delegate to super class handler
        BaseHTTPRequestHandler.handle(self)

        # Tell listener thread has finished
        self.server.remove_thread(self)
        self.loginfo("NI HTTP handler finishing")
        return

    #--------------------------------------------------------------------------#
    """
    Unclear that this is needed (or works.. where is request_close?)
    end_run is defined in the NIHTTPServer class and shuts down the threads.
    def end_run(self):
        self.request_close()
    """
    #--------------------------------------------------------------------------#
    def log_message(self, format, *args):
        """
        @brief Log an arbitrary message.
        @param format string Format template string with %-encoded substitutions
        @param args any Variables to substitute into format template
        @return (none)
        
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

    #--------------------------------------------------------------------------#
    def send_file(self, source):
        """
        @brief Copy all data from source to response body stream (self.wfile).
               Close source on completion.

        @param source file object open for reading
                          (or anything with a read() method)
        @return void
        
        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        """
        shutil.copyfileobj(source, self.wfile)
        source.close()
        return

    #--------------------------------------------------------------------------#
    def send_string(self, buf):
        """
        @brief Copy all data from buf (string) to response body stream (self.wfile).

        @param buf string to be written

        @return void
        """
        self.wfile.write(buf)
        return

