<?php

/*
 * @file N-GET.php
 * @brief PHP server side processing of NetInf GET for HTTP CL
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

include 'N-lib.php';


// read request attrs or use test value

// read it from HTTP POST form data
$urival = filter_input(INPUT_POST, 'URI');
$msgidval = $_REQUEST['msgid'];
$extval = $_REQUEST['ext'];

// test - one I have
// $urival = "ni:///sha-256;zxGpiG2_HXy3dHY9HZ3RJqsrhhVmWTsedpFnBTXN9us";
// $msgidval = 100;
// $extval = "";
	
// test - one I don't have (and is invalid)
// $urival = "ni:///sha-256;xxxxxoQ-h1bb0Ovu99EJUVQqyarpRQ4EQ0bCmJgY";
// $msgidval = 100;
// $extval = "";
	

// extract hashalg and hash and check for file, if it exists print it, otherwise 404
$hstr = "";
$algfound=false;
$hashval="";

$ni_err=false;
$ni_errno=0;

if (getAlg($urival,$algfound,$hstr,$hashval)===false) {
	$ni_err=true;
	$ni_errno=490;
	$ni_errstr="Bummer: $ni_errno I don't have $urival \nBad algorithm, no good alg found.";
	retErr($ni_errno,$ni_errstr);
	exit(1);
}

if (!$algfound) {
	$ni_err=true;
	$ni_errno=491;
	$ni_errstr="Bummer:  $ni_errno  I don't have $urival \nBad algorithm, no good alg found.";
	retErr($ni_errno,$ni_errstr);
	exit(1);
} 

// TODO: see if we have that file elsewhere (netinffs)

// Check if we have NDO metadata
$jfilename=checkMeta($hstr,$hashval);
if ($jfilename) { // we have meta data!
	// $filename = $GLOBALS["cfg_wkd"] . "/" . $hstr . "/" . $hashval ;
	$filename = getNDOfname($hstr,$hashval);
	if (file_exists($filename)) {
		sendMIMEWithFile($jfilename,$filename,$msgidval);	
	} else {
		sendMIMEJSONOnly($jfilename,$msgidval);	
	}
	exit(0);
}

// Fallback: See if we have one of those in .well-known locally
// $filename = $GLOBALS["cfg_wkd"] . "/" . $hstr . "/" . $hashval ;
$filename = getNDOfname($hstr,$hashval);
if (file_exists($filename)) {
	sendFileAns($filename,$msgidval);
	exit(0);
}

// see if we have a locator

// ultimate fallback HTTP 404
header('HTTP/1.0 404 Not Found');
print "I don't have $urival (N-GET 499) \n";

?>
