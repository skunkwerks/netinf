#!/bin/bash
# @package ni
# @file pynilib_test.sh
# @brief Simple test script nicl.py and ni.py, part of Python nilib.
# @version $Revision: 0.01 $ $Author: elwynd $
# @version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
#       This is an adjunct to the NI URI library developed as
#       part of the SAIL project. (http://sail-project.eu)
# 
#       Specification(s) - note, versions may change
#           - http://tools.ietf.org/html/draft-farrell-decade-ni-10
#           - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03
#           - http://tools.ietf.org/html/draft-kutscher-icnrg-netinf-proto-00
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    
#        - http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
# ===============================================================================#
# 
# 
# @code
# Revision History
# ================
# Version   Date       Author         Notes
# 0.1	  13/10/2012 Elwyn Davies   Updated to new location and more recent formats
# 0.0	  20/03/2012 Elwyn Davies   Created.
# @endcode

sample_dir=../../../samples
bar_file=${sample_dir}/bar
foo_file=${sample_dir}/foo

if [ "$1" == "once" ]
then
	../nicl.py -g -n 'ni://tcd.ie/sha-256-32;?ct=image%2Fjson' -f $bar_file
	exit
fi

echo "usage"
../nicl.py -h
echo "generate" 
../nicl.py -g -n 'ni://tcd.ie/sha-256;?ct=image%2Fjson' -f $bar_file
echo "res: $?"; echo ""
echo "good verify - res should be 0"
../nicl.py -v -n 'ni://tcd.ie/sha-256;fdZ0A_iA9BIw2g_Ve8WaqZfmRS4Af1zy2hGdHOgM-Do?ct=image%2Fjson' -f $bar_file
echo "res: $?"; echo ""
echo "bad verify (wrong file) - res should be 1"
../nicl.py -v -n 'ni://tcd.ie/sha-256;fdZ0A_iA9BIw2g_Ve8WaqZfmRS4Af1zy2hGdHOgM-D?ct=image%2Fjson' -f $foo_file
echo "res: $?"; echo ""
echo "bad verify (wrong hash) - res should be 1"
../nicl.py -v -n 'ni://tcd.ie/sha-256;fdZ0A_xA9Byw2g_Ve8WaqZfmRS4Af1zy2hGdHOgM-Do?ct=image%2Fjson' -f $bar_file
echo "res: $?"; echo ""


