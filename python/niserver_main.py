#!/usr/bin/python
"""
@package ni
@file niserver_main.py
@brief Main program for NI lightweight HTTP server.
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

Main program for NI lightweight HTTP server

Sets up logging, creates NI HTTP listener thread and control socker
Waits for shutdown comands or signals; shutsdown server on request.

Revision History
================
Version   Date       Author         Notes
0.1	  16/02/2012 Elwyn Davies   Fixed usage string.
0.0	  12/02/2012 Elwyn Davies   Created for SAIL codesprint.
"""

import os
import sys
import time
import threading
import socket
import select
import logging
import logging.handlers
import logging.config
import ConfigParser
from optparse import OptionParser

from niserver import ni_http_server, NDO_DIR, META_DIR
from ni import NIname

# UDP port number used to send a shutdown control request.
CTRL_PORT = 2114

# Default port number for HTTP server to listen om
SERVER_PORT = 8080

def main(default_config_file):
    """
    @brief main program for lightweight NI HTTP server
    @param Default to use for configuration file if not on command line.

    Functions:
    - Parse options and negotiate with configuration file
    - Setup logging
    - check object cache directories exist and create if not present
    - check authority for server
    - create thread for main NI server listener (for incoming requests)
    - start thread
    - create control socket for shutdown instructions
    - go to sleep waiting for shutdown command or signal
    - on shutdown request or signal close down server and exit
    """

    # Options parsing and verification stuff
    # Config file
    # Command line parameters overrule config file
    usage = "%prog [-f <config file>] [-p <server port>] [-l <log config file>]\n" + \
            "                [-n <logger name>] [-s <storage root>] [-a <authority>]\n" + \
            "                [-b <logging base directory>] [-c <control port>]"

    parser = OptionParser(usage=usage, prog="niserver")
    
    parser.add_option("-f", "--config-file", dest="config_file",
                      type="string", default = default_config_file,
                      help="Pathname for niserver configuration file.")
    parser.add_option("-l", "--log-config-file", dest="log_config",
                      type="string",
                      help="Pathname for logger configuation file.")
    parser.add_option("-n", "--logger-name", dest="logger",
                      type="string",
                      help="Name of logger to use from log configuration.")
    parser.add_option("-s", "--storage-root", dest="storage_root",
                      type="string",
                      help="Pathname for root of cache directory tree.")
    parser.add_option("-a", "--authority", dest="authority",
                      type="string",
                      help="FQDN to be placed in authority component of NI names published.")
    parser.add_option("-b", "--log-base", dest="log_base",
                      type="string",
                      help="Directory path name used to hold log file.")
    # CTRL_PORT is used as a fallback if neither command line nor config file specify
    parser.add_option("-c", "--control-port", dest="ctrl_port",
                      type="int", default=None,
                      help="Control port for sending server stop instruction.")
    # SERVER_PORT is used as a fallback if neither command line nor config file specify
    parser.add_option("-p", "--server-port", dest="server_port",
                      type="int", default=None,
                      help="Control port for sending server stop instruction.")

    (options, args) = parser.parse_args()

    # Check options - there must be no leftover arguments
    if len(args) != 0:
        parser.error("Unrecognized arguments %s supplied." % str(args))
        sys.exit(-1)

    config_file = options.config_file
    log_config_file = options.log_config
    logger = options.logger
    storage_root = options.storage_root
    log_base = options.log_base
    ctrl_port = options.ctrl_port
    server_port =options.server_port
    authority = options.authority

    # Can do without config file if -l, -n and -s are specified
    if not ((log_config_file is not None) and
            (logger is not None) and
            (storage_root is not None)):
        if (config_file is None):
            parser.error("Must specify a configuration file if not specifying -l, -n and -s.")
            sys.exit(-1)

    # Get the configuration file if there is one
    if (config_file is not None):
        if not os.access(config_file, os.R_OK):
            parser.error("Master configuration file %s is not readable" % config_file)
            os._exit(2)
            
        # Setup the configuration file parser and parse config file
        config = ConfigParser.ConfigParser()
        try:
            configs_read = config.read(config_file)
            if not config_file in configs_read:
                parser.error("Unable to parse configuration file %s" % (config_file))
                os._exit(1)
        except Exception, inst:
            parser.error("Unable to parse configuration file %s: %s" %
                  (options.config_file, str(inst)))
            os._exit(1)

        # Get entries from config file
        # Check base entries exist (avoids excptions later)
        conf_section = "DEFAULT"
        conf_option = "conf_base"
        if not config.has_option(conf_section, conf_option):
            parser.error("No option for %s in section %s in configuration file %s" %
                  (conf_option, conf_section, config_file))
            os._exit(1)
        conf_option = "storage_base"
        if not config.has_option(conf_section, conf_option):
            parser.error("No option for %s in section %s in configuration file %s" %
                  (conf_option, conf_section, config_file))
            os._exit(1)
                
        # Retrieve logger configuration from master config file if needed
        # Gets: The name of the logger config file, the name of the logger
        #       and the directory (that needs to exist) where logs are stored
        conf_section = "logger"
        if ((log_config_file is None) or (logger is None)) and (not config.has_section(conf_section)):
            parser.error("No section named %s in configuration file %s" %
                  (conf_section, config_file))
            os._exit(1)
        else:
            if (log_config_file is None):
                conf_option = "log_config_file"
                if config.has_option(conf_section, conf_option):
                    log_config_file = config.get(conf_section, conf_option)
                else:
                    parser.error("No option for %s in section %s in configuration file %s" %
                          (conf_option, conf_section, config_file))
                    os._exit(1)
            if (logger is None):
                conf_option = "niserver_logger_name"
                if config.has_option(conf_section, conf_option):
                    logger = config.get(conf_section, conf_option)
                else:
                    parser.error("No option for %s in section %s in configuration file %s" %
                          (conf_option, conf_section, config_file))
                    os._exit(1)

        conf_section = "locations"
        if ((log_base is None) or (storage_root is None)) and (not config.has_section(conf_section)):
            parser.error("No section named %s in configuration file %s" %
                  (conf_section, config_file))
        else:
            if (log_base is None):
                conf_option = "log_base"
                if config.has_option(conf_section, conf_option):
                    log_base = config.get(conf_section, conf_option)
            if (storage_root is None):
                conf_option = "storage_root"
                if config.has_option(conf_section, conf_option):
                    storage_root = config.get(conf_section, conf_option)
                else:
                    parser.error("No option for %s in section %s in configuration file %s" %
                          (conf_option, conf_section, config_file))
                    os._exit(1)

        conf_section = "ports"
        if ((ctrl_port is None) or (server_port is None)) and (not config.has_section(conf_section)):
            parser.error("No section named %s in configuration file %s" %
                  (conf_section, config_file))
        else:
            if (ctrl_port is None):
                conf_option = "ctrl_port"
                if config.has_option(conf_section, conf_option):
                    ctrl_port = int(config.get(conf_section, conf_option))
            if (server_port is None):
                conf_option = "server_port"
                if config.has_option(conf_section, conf_option):
                    server_port = int(config.get(conf_section, conf_option))
                
        conf_section = "authority"
        if (authority is None) and (not config.has_section(conf_section)):
            parser.error("No section named %s in configuration file %s" %
                  (conf_section, config_file))
        else:
            if (authority is None):
                conf_option = "auth_fqdn"
                if config.has_option(conf_section, conf_option):
                    authority = config.get(conf_section, conf_option)

    # Check we have all the configuration we need and apply fallback
    # defaults for others
    if ((log_config_file is None) or
        (logger is None) or
        (storage_root is None)):
        parser.error("Must set values for log configuration file, logger and storage root.")
        os._exit(1)

    # Set authority to local FQDN if not specified
    if authority is None:
        authority = socket.gethostbyaddr(socket.gethostname())[0]

    # Set log_base to /tmp if not specified
    if log_base is None:
        log_base = "/tmp"

    if not (os.path.isdir(log_base) and os.access(config_file, os.W_OK)):
        parser.error("Log_base %s is not a directory and/or not writeable" % log_base)
        os._exit(2)
        
    # Set fallbacks for ctrl_port and server_port if needed
    if ctrl_port is None:
        ctrl_port = CTRL_PORT
    if server_port is None:
        server_port = SERVER_PORT

    # Check log configuration file exists and is readable (the error messages
    # from logging.config.fileConfig() are confusing if the file does not exist).
    if not os.access(log_config_file, os.R_OK):
        parser.error("Logging configuration file '%s' is not readable" % log_config_file)
        return False

    try:
        logging.config.fileConfig(log_config_file,
                                  defaults={"log_base": log_base})
    except Exception, inst:
        parser.error("Unable to configure logging: %s" % (str(inst)))
        return False
    try:
        niserver_logger = logging.getLogger(logger)
    except Exception, inst:
        parser.error("Unable to find logger '%s' in configuration file '%s'" %
              (logger, log_config_file))
        parser.error("Exception from logging.getlogging() was %s" % (str(inst)))
        return False
        
    loginfo = niserver_logger.info
    logdebug = niserver_logger.debug
    logerror = niserver_logger.error
    loginfo("%s: Main started" % parser.get_prog_name())
    
    loginfo("Serving for authority %s on port %s" % (authority, server_port))
    #print log_config_file, storage_root, log_base, logger, ctrl_port, server_port

    #====================================================================#
    # Check object cache directories exist and create them if necessary
    if not os.path.isdir(storage_root):
        logerror("Storage root directory %s does not exist." % storage_root)
        sys.exit(-1)
    for tree_name in (NDO_DIR, META_DIR):
        tree_root = "%s%s" % (storage_root, tree_name)
        if not os.path.isdir(tree_root):
            loginfo("Creating object cache tree directory: %s" % tree_root)
            try:
                os.mkdir(tree_root, 0755)
            except Exception, e:
                logerror("Unable to create tree directory %s : %s." % \
                         (tree_root, str(e)))
                sys.exit(-1)
        for auth_name in NIname.get_all_algs():
            dir_name = "%s%s" % (tree_root, auth_name)
            if not os.path.isdir(dir_name):
                loginfo("Creating object cache directory: %s" % dir_name)
                try:
                    os.mkdir(dir_name, 0755)
                except Exception, e:
                    logerror("Unable to create cache directory %s : %s." % \
                             (dir_name, str(e)))
                    sys.exit(-1)
                    
    #====================================================================#
    # Create server to handle HTTP requests
    ni_server = ni_http_server(storage_root, authority, server_port, niserver_logger)

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    ni_server_listener = threading.Thread(target=ni_server.serve_forever,
                                        name="niserver")
    # Exit the server thread when the main thread terminates
    ni_server_listener.setDaemon(True)
    ni_server_listener.start()
    
    # Let everything have a chance to get going (old trick)
    time.sleep(0.1)
    loginfo("NI serverlistener running in thread: %s" %
            ni_server_listener.getName())

    # The main thread now goes to sleep until either an interrupt or incoming data
    # (any incoming data) on CTRL_PORT (typically one more than the mail input port)
    # Shutdown control is restricted to local machine.
    HOST = "mightyatom.folly.org.uk"
    ctrl_skt = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,0)
    ctrl_skt.bind((HOST, CTRL_PORT))
    read_fds = [ctrl_skt]
    write_fds = []
    exc_fds = []
    
    try:
        # Wait indefinitely (no timeout specified) for input on ctrl_skt or signal.
        sel_fds = select.select(read_fds, write_fds, exc_fds)
        if not (ctrl_skt in sel_fds[0]):
            loginfo("Main thread terminated due to signal")
        else:
            loginfo("Main thread terminated through control interface")
    except:
        loginfo("Main thread received keyboard interrupt: %s" % sys.exc_info()[0])
    
    # Shutdown
    ctrl_skt.close()
    
    # Shutdown the HTTP server listener
    ni_server.end_run()

    # Give them a few seconds to die...
    time.sleep(6)

    loginfo("%s: shutting down" % parser.get_prog_name())
    return True
    
#============================================================================
if __name__ == "__main__":
    if not main("/var/niserver/niserver.conf"):
        os._exit(1)


