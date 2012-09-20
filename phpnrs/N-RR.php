<?php

/*
 * @file N-RR.php
 * @brief PHP route registration
 * @version $Revision: 0.01 $ $Author: stephen $
 * @version Copyright (C) 2012 Trinity College Dublin
	This is the NI PHP Server library developed as
	part of the SAIL project. (http://sail-project.eu)
	Protocol Specification(s) - note, versions may change
		draft-netinf-proto.txt - unpublished
	Server spec: this code:-)
    This one goes to wikipedia only, when that works:-)
	
 */
/* 
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
 
*/

include 'N-lib.php';



// read request attrs or use test value

// read it from HTTP POST form data
$urival = filter_input(INPUT_POST, 'URI');
$hint1 = filter_input(INPUT_POST, 'hint1');
$hint2 = filter_input(INPUT_POST, 'hint2');
$loc1 = filter_input(INPUT_POST, 'loc1');
$loc2 = filter_input(INPUT_POST, 'loc2');
$meta = filter_input(INPUT_POST, 'meta');
$stage = filter_input(INPUT_POST, 'stage');

print "Got it: URI = $urival\n";

if ($stage=="zero") {
    print "you want me to register that\n";
}
if ($stage=="one") {
    print "you want me to look that up\n";
}
if ($stage!="zero" && $stage!="one") {
    print "feck off\n";
}

exit(0);

