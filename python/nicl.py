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
    usage = "%prog [-g|-w|-v] -n <name> -f <pathname of content file> [-V]\n"
    usage = usage + "       %prog -m -n <name> [-V]\n"
    usage = usage + "       %prog -b -s <suite_number> -f <pathname of content file> [-V]\n"
    usage = usage + "       The name can be either an ni: or nih: scheme URI\n"
    usage = usage + "       Return code: success 0, failure non-zero (-V for more info)\n"
    usage = usage + "       Available hashalg (suite number) options:\n"
    usage = usage + "       %s" % NIname.list_algs()
    parser = OptionParser(usage)
    
    parser.add_option("-g", "--generate", default=False,
                      action="store_true", dest="generate",
                      help="Generate hash based on content file, " + \
                           "and output name with encoded hash after the hashalg string")
    parser.add_option("-w", "--well-known", default=False,
                      action="store_true", dest="well_known",
                      help="Generate hash based on content file, " + \
                           "and output name with encoded hash in the .well_known URL " + \
                           "after the hashalg string. Applies to ni: scheme only.")
    parser.add_option("-v", "--verify", default=False,
                      action="store_true", dest="verify",
                      help="Verify hash in name is correct for content file")
    parser.add_option("-m", "--map", default=False,
                      action="store_true", dest="map_wkn",
                      help="Maps from an ni: name to a .well-known URL")
    parser.add_option("-b", "--binary", default=False,
                      action="store_true", dest="bin",
                      help="Outputs the name in binary format for a given suite number")
    parser.add_option("-V", "--verbose", default=False,
                      action="store_true", dest="verbose",
                      help="Be more long winded.")
    parser.add_option("-n", "--ni-name", dest="ni_name",
                      type="string",
                      help="The ni name template for (-g) or ni name matching (-v) content file.")
    parser.add_option("-f", "--file", dest="file_name",
                      type="string",
                      help="File with content data named by ni name.")
    parser.add_option("-s", "--suite-no", dest="suite_no",
                      type="int",
                      help="Suite number for hash algorithm to use.")

    (opts, args) = parser.parse_args()

    if not (opts.generate or opts.well_known or opts.verify or
            opts.map_wkn or opts.bin ):
        parser.error( "Must specify one of -g/--generate, -w/--well-known, -v/--verify, -m/--map or -b/--binary.")
    if opts.generate or opts.well_known or opts.verify:
        if (opts.ni_name == None) or (opts.file_name == None):
            parser.error("Must specify both name and content file name for -g, -w or -v.")
    if opts.map_wkn:
        if (opts.ni_name == None):
            parser.error("Must specify ni name for -m.")
    if opts.bin:
        if (opts.suite_no == None) or (opts.file_name == None):
            parser.error("Must specify both suite number and content file name for -b.")
    if len(args) != 0:
        parser.error("Too many or unrecognised arguments specified")

    # Execute requested action
    if opts.generate:
        n = NIname(opts.ni_name)
        ret = NIproc.makenif(n, opts.file_name)
        if ret == ni_errs.niSUCCESS:
            if opts.verbose:
                print("Name generated successfully.")
            print "%s" % n.get_url()
            sys.exit(0)
        if opts.verbose:
            print "Name could not be successfully generated."
    elif opts.well_known:
        n = NIname(opts.ni_name)
        if n.get_scheme() == "nih":
            if opts.verbose:
                print "Only applicable to ni: scheme names."
            sys.exit(1)
        ret = NIproc.makenif(n, opts.file_name)
        if ret == ni_errs.niSUCCESS:
            if opts.verbose:
                print("Name generated successfully.")
            print "%s" % n.get_wku_transform()
            sys.exit(0)
        if opts.verbose:
            print "Name could not be successfully generated."
    elif opts.verify:
        n = NIname(opts.ni_name)
        ret = NIproc.checknif(n, opts.file_name)
        if ret == ni_errs.niSUCCESS:
            if opts.verbose:
                print("Name matches content file.")
                print "%s" % n.get_url()
            sys.exit(0)
        if opts.verbose:
            print "Check of name against content failed."
    elif opts.map_wkn:
        n = NIname(opts.ni_name)
        ret = n.validate_ni_url(has_params = True)
        if ret == ni_errs.niSUCCESS:
            if n.get_scheme() == "nih":
                if opts.verbose:
                    print "Only applicable to ni: scheme names."
                sys.exit(1)
            if opts.verbose:
                print("Name validated successfully.")
            print "%s" % n.get_wku_transform()
            sys.exit(0)
        else:
            if opts.verbose:
                print "Name could not be successfully validated."
    elif opts.bin:
        (ret, bin_name) = NIproc.makebnf(opts.suite_no, opts.file_name)
        if ret == ni_errs.niSUCCESS:
            if opts.verbose:
                print("Name generated successfully.")
            print base64.b16encode(str(bin_name))
            sys.exit(0)
        else:
            if opts.verbose:
                print "Name could not be successfully generated."
    else:
        print"Should not have happened"
        sys.exit(2)

    # Print appropriate error message
    if opts.verbose:
        print "Error: %s" % ni_errs_txt[ret]
    sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
