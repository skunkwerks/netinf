<?php

/*
 * @file N-lib.php
 * @brief library for PHP server side processing of NetInf for HTTP CL
 * @version $Revision: 0.01 $ $Author: stephen $
 * @version Copyright (C) 2012 Trinity College Dublin
	This is the NI PHP Server library developed as
	part of the SAIL project. (http://sail-project.eu)
	Protocol Specification(s) - note, versions may change
		draft-netinf-proto.txt - unpublished
	Server spec: this code:-)
	
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

// Your web server docRoot
$cfg_myRoot="/home/dtnuser/data/www/statichtml";
// The place for .well-known
$cfg_wkd=$cfg_myRoot . "/.well-known/ni";
// Where to keep meta-data files
$cfg_metadir="/home/dtnuser/data/www/statichtml/ni-meta";
// Where to keep he NDO octets
// If this isn't below docRoot then some coding is needed!
$cfg_ndodir="/home/dtnuser/data/www/statichtml/ni-ndo";
// The site I'm working on 
$cfg_site="http://village.n4c.eu";
// nicl command
$cfg_nicl = "/home/stephen/code/netinf-code/c/nicl";
// cache directory
$cfg_cache="/home/dtnuser/data/www/statichtml/ni-cache";

// Whether to stuff debug output in /tmp for e.g. MIME responses
// set to non-zero to get debug, might add more options later
$cfg_debug=0;

?>

