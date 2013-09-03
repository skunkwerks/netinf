#!/usr/bin/python
"""
@package nilib
@file niserver_main.py
@version $Revision: 0.04 $ $Author: elwynd $
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

===========================================================================

@brief Main program for NI lightweight HTTP server

@details
Sets up logging, creates NI HTTP listener thread and control socker
Waits for shutdown comands or signals; shutsdown server on request.
@code
Revision History
================
Version   Date       Author         Notes
1.3       26/01/2013 Elwyn Davies   Add DTN->HTTP gateway functionality.
1.2       25/01/2013 Elwyn Davies   Add option to specify Redis DB number.
1.1       10/12/2012 Elwyn Davies   Add options for Redis cache storage.
1.0       04/12/2012 Elwyn Davies   Move check_cache_dirs into cache module.
                                    Now called in niserver.py.
0.4       11/10/2012 Elwyn Davies   Minor commenting improvements.
0.3	  07/10/2012 Elwyn Davies   Added favicon option. Improved doxygen stuff.
0.2	  06/10/2012 Elwyn Davies   Added getputform and nrsform options, and
                                    tests that the files referred to are
                                    readable.
0.1	  16/02/2012 Elwyn Davies   Fixed usage string.
0.0	  12/02/2012 Elwyn Davies   Created for SAIL codesprint.
@endcode
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

# Will also import niserver when we have decided which cache to use.

#==============================================================================#
# GLOBAL VARIABLES

#=== Configuration Defaults ===

##@var CTRL_PORT
# UDP port number used to send a shutdown control request.
CTRL_PORT = 2114

##@var SERVER_PORT
# Default port number for HTTP server to listen on
SERVER_PORT = 8080

##@var FAVICON_FILE
# Default name for favicon file requested by browsers
FAVICON_FILE = "/favicon.ico"

##@var REDIS_DB_NUM
# Default Redis DB number
REDIS_DB_NUM = 0

#==============================================================================#
def py_niserver_start(default_config_file):
    """
    @brief main program for lightweight NI HTTP server
    @param default_config_file string Pathname of default to use for
    configuration file if not on command line.
    @return Exits to system with various return codes depending on reason.

    Functions:
    - Parse options and negotiate with configuration file
    - Setup logging
    - Check stoage root directory exists (cache structure is checked later)
    - Check form and favicon files exist and are readable
    - If NRS server to be provided, check Redis module can be loaded
    - Check authority for server
    - Create thread for main NI server listener (for incoming requests)
    - Start thread
    - Create control socket for shutdown instructions
    - Go to sleep waiting for shutdown command or signal
    - On shutdown request or signal close down server and exit

    To check the command line parameters use@n
    niserver_main.py -h

    The default for the configuration file locations is /var/niserver
    which is where the form and favicon.ico files will be placed
    by default.

    See the default configuration file (niserver.conf) for details of
    all configuration file settings.
    """

    # Options parsing and verification stuff
    # Config file
    # Command line parameters overrule config file
    usage = "%prog [-f <config file>] [-p <server port>] [-l <log config file>]\n" + \
            "                [-n <logger name>] [-s <storage root>] [-a <authority>]\n" + \
            "                [-b <logging base directory>] [-c <control port>] [-i <favicon file>]\n" + \
            "                [-g <GET/PUT/SEARCH form code file>] [-r <NRS config from code file]\n" + \
            "                [-c [file|redis]] [-d <Redis db number>] [-G]"

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
    parser.add_option("-b", "--log_base", dest="log_base",
                      type="string",
                      help="Directory path name used to hold log file.")
    parser.add_option("-g", "--getputform", dest="getputform",
                      type="string",
                      help="Name of file containing HTML code for web GET/PUT/SEARCH form.")
    parser.add_option("-r", "--nrsform", dest="nrsform",
                      type="string",
                      help="Name of file containing HTML code for web NRS configuration form.")
    # CTRL_PORT is used as a fallback if neither command line nor config file specify
    parser.add_option("-c", "--control-port", dest="ctrl_port",
                      type="int", default=None,
                      help="Control port for sending server stop instruction.")
    # SERVER_PORT is used as a fallback if neither command line nor config file specify
    parser.add_option("-p", "--server-port", dest="server_port",
                      type="int", default=None,
                      help="Server port on which to listen for HTTP requests.")
    parser.add_option("-u", "--nrs-server", dest="provide_nrs",
                      default=0, action="count",
                      help="If present, offer NRS services from server.")
    parser.add_option("-i", "--icon", dest="favicon",
                      type="string",
                      help="File containing favicon for browser display.")
    parser.add_option("-m", "--cache-mode", dest="cache",
                      type="string",
                      help="Select cache mechanism ('file' - default - or 'redis').")
    # REDIS_DB_NUM is used as a fallback if neither command line nor config file specify
    parser.add_option("-d", "--db-number", dest="redis_db",
                      type="int", default=None,
                      help="Redis database number to use (if mode is redis).")
    parser.add_option("-G", "--gateway", dest="run_gateway",
                      default=0, action="count",
                      help="If present, offer DTN<->HTTP gateway services.")

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
    getputform = options.getputform
    nrsform = options.nrsform
    provide_nrs = None if (options.provide_nrs == 0) else True
    favicon = options.favicon
    cache_mode = options.cache
    redis_db = options.redis_db
    run_gateway = None if (options.run_gateway == 0) else True

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    # Can do without config file if -l, -n, -s, -g and -r are specified
    if not ((log_config_file is not None) and
            (logger is not None) and
            (storage_root is not None) and
            (getputform is not None) and
            (nrsform is not None)):
        if (config_file is None):
            parser.error("Must specify a configuration file if not specifying -l, -n, -s, -g and -r.")
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
        if ((log_base is None) or (storage_root is None) or
            (getputform is None) or (nrsform is None)) and (not config.has_section(conf_section)):
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
            if (getputform is None):
                conf_option = "getputform_code"
                if config.has_option(conf_section, conf_option):
                    getputform = config.get(conf_section, conf_option)
                else:
                    parser.error("No option for %s in section %s in configuration file %s" %
                                (conf_option, conf_section, config_file))
                    os._exit(1)
            if (nrsform is None):
                conf_option = "nrs_config_code"
                if config.has_option(conf_section, conf_option):
                    nrsform = config.get(conf_section, conf_option)
                else:
                    parser.error("No option for %s in section %s in configuration file %s" %
                                 (conf_option, conf_section, config_file))
                    os._exit(1)
            if (favicon is None):
                conf_option = "favicon"
                if config.has_option(conf_section, conf_option):
                    favicon = config.get(conf_section, conf_option)

            if (cache_mode is None):
                conf_option = "cache"
                if config.has_option(conf_section, conf_option):
                    cache_mode = config.get(conf_section, conf_option)

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

        conf_section = "nrs"
        if (provide_nrs is None) and (not config.has_section(conf_section)):
            parser.error("No section named %s in configuration file %s" %
                         (conf_section, config_file))
        else:
            if (provide_nrs is None):
                conf_option = "provide_nrs"
                if config.has_option(conf_section, conf_option):
                    try:
                        provide_nrs = config.getboolean(conf_section,
                                                        conf_option)
                    except ValueError:
                        parser.error("Value supplied for %s is not an "
                                     "acceptable boolean representation" %
                                     conf_option)

        conf_section = "redis"
        if config.has_section(conf_section):
            if (redis_db is None):
                conf_option = "redis_db"
                if config.has_option(conf_section, conf_option):
                    try:
                        redis_db = int(config.get(conf_section,
                                                  conf_option))
                    except ValueError:
                        parser.error("Value supplied for %s is not an "
                                     "acceptable integer representation" %
                                     conf_option)

        conf_section = "gateway"
        if config.has_section(conf_section):
            if (run_gateway is None):
                conf_option = "run_gateway"
                if config.has_option(conf_section, conf_option):
                    try:
                        run_gateway = config.getboolean(conf_section,
                                                        conf_option)
                    except ValueError:
                        parser.error("Value supplied for %s is not an "
                                     "acceptable boolean representation" %
                                     conf_option)

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
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

    if not (os.path.isdir(log_base) and os.access(log_base, os.W_OK)):
        parser.error("Log_base %s is not a directory and/or not writeable" % log_base)
        os._exit(2)
        
    # Set fallbacks for ctrl_port and server_port if needed
    if ctrl_port is None:
        ctrl_port = CTRL_PORT
    if server_port is None:
        server_port = SERVER_PORT

    # Set fallback for favicon
    if favicon is None:
        if config_file is not None:
            favicon = os.path.dirname(config_file) + FAVICON_FILE
        else:
            favicon = "." + FAVICON_FILE 

    # Default to not providing NRS service
    if (provide_nrs is None):
        provide_nrs = False

    # Determine cache mechanism to use and load module as appropriate
    if (cache_mode is None) or (cache_mode == "file"):
        import file_store
        print "Using filesystem only cache"
    elif cache_mode == "redis":
        import redis_store
        print "Using Redis and filesystem cache"
    else:
        parser.error("Unrecognised cache mode - possibilities are 'file' and 'redis'")

    # Default to database #0 if using Redis
    if (redis_db is None):
        redis_db = REDIS_DB_NUM

    # Default to not running HTTP<->DTN gateway
    if (run_gateway is None):
        run_gateway = False
        
    # Now load the main server module so that it gets the right cache module loaded            
    from niserver import ni_http_server

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    # Setup logging...
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
    
    #print log_config_file, storage_root, log_base, logger, ctrl_port, \
    #      server_port, getputform, nrsform, provide_nrs, favicon

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    # Check object cache directories exist and create them if necessary
    if not os.path.isdir(storage_root):
        logerror("Storage root directory %s does not exist." % storage_root)
        sys.exit(-1)
                    
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    # Check getput and nrs configuration form HTML files exist and are readable.
    if not os.path.isfile(getputform):
        logerror("Code file for getputform.html (%s) is missing." % getputform)
        sys.exit(-1)
    if not os.access(getputform, os.R_OK):
        logerror("Code file for getputform.html (%s) is not readable." % getputform)
        sys.exit(-1)
    if not os.path.isfile(nrsform):
        logerror("Code file for getputform.html (%s) is missing." % nrsform)
        sys.exit(-1)
    if not os.access(nrsform, os.R_OK):
        logerror("Code file for getputform.html (%s) is not readable." % nrsform)
        sys.exit(-1)
        
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    # Check favicon file exists and is readable.
    if not os.path.isfile(favicon):
        logerror("File for favicon (%s) is missing." % favicon)
        sys.exit(-1)
    if not os.access(getputform, os.R_OK):
        logerror("File for favicon (%s) is not readable." % favicon)
        sys.exit(-1)

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    # If NRS server is required, check if redis module is available.
    if provide_nrs:
        try:
            import redis
        except ImportError:
            logerror("Unable to import redis module to support NRS server")
            sys.exit(-1)
       
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -#
    # Create server to handle HTTP requests
    ni_server = ni_http_server(storage_root, authority, server_port,
                               niserver_logger, config, getputform, nrsform,
                               provide_nrs, favicon, redis_db, run_gateway)

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    ni_server_listener = threading.Thread(target=ni_server.serve_forever,
                                        name="niserver")
    # Exit the server thread when the main thread terminates
    ni_server_listener.setDaemon(True)
    ni_server_listener.start()
    
    loginfo("Serving for authority %s on port %s" % (authority, server_port))

    # Let everything have a chance to get going (old trick)
    time.sleep(0.1)
    loginfo("NI serverlistener running in thread: %s" %
            ni_server_listener.getName())

    # The main thread now goes to sleep until either an interrupt or incoming data
    # (any incoming data) on CTRL_PORT (typically 2114).
    # Shutdown control is restricted to local machine.
    HOST = "localhost"
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

#------------------------------------------------------------------------------#    
def py_niserver():
    """
    @brief Shim function to allow distuitils to create a script to start server
    """
    if not py_niserver_start("/var/niserver/niserver.conf"):
        os._exit(1)

#==============================================================================#
if __name__ == "__main__":
    py_niserver()

