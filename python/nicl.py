#!/usr/bin/python
"""
@package nicl
@file nicl.py
@brief Basic command line client for NI names, make 'em and check 'em
@version $Revision: 0.01 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin
      This is an adjunct to the NI URI library developed as
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
import sys
from optparse import OptionParser
from ni import *

def main():
    """
    @brief Command line program to generate and validate digests in ni: URLs.
    
    Uses NIproc global instance of NI operations class

    Run:
    
    >  nicl.py --help

    to see usage and options.
    """
    
    # Options parsing and verification stuff
    usage = "%prog [-g|-v] -n <ni name> -f <pathname of content file>\n"
    usage = usage + "       Available hash options: %s" % NIname.list_algs()
    parser = OptionParser(usage)
    
    parser.add_option("-g", "--generate", default=False,
                      action="store_true", dest="generate",
                      help="Generate ni name from template matching content file")
    parser.add_option("-v", "--verify", default=False,
                      action="store_true", dest="verify",
                      help="Verify hash in ni name is correct for content file")
    parser.add_option("-n", "--ni-name", dest="ni_name",
                      type="string",
                      help="The ni name template for (-g) or ni name matching (-v) content file.")
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="File with content data named by ni name.")

    (options, args) = parser.parse_args()

    if not (options.generate or options.verify):
        parser.error( "Must specify either -g/--generate or -v/--verify.")
    if (options.ni_name == None) or (options.file_name == None):
        parser.error("Must specify both ni name and content file name.")
    if len(args) != 0:
        parser.error("Too many or unrecognised arguments specified")

    # Execute reuested action
    if options.generate:
        n = NIname(options.ni_name)
        ret = NIproc.makenif(n, options.file_name)
        if ret == ni_errs.niSUCCESS:
            print "Name generated successfully."
            print "%s" % n.get_url()
            sys.exit(0)
        print "Name could not be successfully generated."
    elif options.verify:
        n = NIname(options.ni_name)
        ret = NIproc.checknif(n, options.file_name)
        if ret == ni_errs.niSUCCESS:
            print "Name matches content file."
            print "%s" % n.get_url()
            sys.exit(0)
        print "Check of name against content failed."
    else:
        print"Should not have happened"
        sys.exit(2)

    # Print appropriate error message
    print "Error: %s" % ni_errs_txt[ret]
    sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
