<?php

/*
 * @file N-GET.php
 * @brief PHP server side processing of NetInf PUBLISH for HTTP CL
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
$loc1 = $_REQUEST['loc1'];
$loc2 = $_REQUEST['loc2'];
$fullPut = $_REQUEST['fullPut'];

// get that file
$gotfile=false;
if ($_FILES["octets"]["error"] > 0 ) {
	// "No file given";
	$fname = "none";
	$ftmp = "none";
} else {
	// "Got a file -- " ;
	$fname = $_FILES["octets"]["name"];
	$ftmp = $_FILES["octets"]["tmp_name"];
	$gotfile = true;
}

// test - one I have
// $urival = "ni:///sha-256;zxGpiG2_HXy3dHY9HZ3RJqsrhhVmWTsedpFnBTXN9us";
// $msgidval = 100;
// $extval = "";
// $fname="/home/dtnuser/data/www/statichtml/.well-known/ni/sha-256/zxGpiG2_HXy3dHY9HZ3RJqsrhhVmWTsedpFnBTXN9us";
// $ftmp=$fname;
// $gotfile=false;
// $fullPut=false;
// $loc1="http://village.n4c.eu/foobar";
// $loc2="dtn:foobar";

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
	retErr($ni_errno,$nistr);
	exit(1);
}

if (!$algfound) {
	$ni_err=true;
	$ni_errno=491;
	$ni_errstr="Bummer:  $ni_errno  I don't have $urival \nBad algorithm, no good alg found.";
	retErr($ni_errno,$ni_errstr);
	exit(1);
} 

// What needs doing?
// Pseudo-code
// check_params() incl. name-data-integrity
// if no errors
//    put file someplace
//    put well-known link where it needs to be
// what to do with locators or if incomplete req?

// extract hashalg and hash and check for file, if it exists print it, otherwise 404


if ($fullPut && $gotfile) {
	// check name-data-integrity
	$niclcmd = $GLOBALS["cfg_nicl"] . " -v -n '" . $urival . "' -f " . $ftmp;
	exec($niclcmd,$results);
	$answer = $results[0];
	$ndifile=($answer=="good");
	if ($ndifile) {
		// print "Good - nice";
	} else {
		header('HTTP/1.0 404 Not Found');
		print "Bad - feck off";
		exit("done");
	} 

	// $filename = $GLOBALS["cfg_wkd"] . "/" . $hstr . "/" . $hashval ;
	$filename = getNDOfname($hstr,$hashval);
	if (file_exists($filename)) {
		header('HTTP/1.0 404 Not Found');
		print "I already have $urival \n";
	} else {
		// print "File; $filename\n";
		move_uploaded_file($ftmp,$filename);
		// make a link in .well-known/ni
		$wlname=$GLOBALS["cfg_wkd"]."/$hstr/$hashval";
		$rv=symlink($filename,$wlname);
	} 
} 

$extrameta="{ \"publish\" : \"php\" }";
$store_rv=storeMeta($hstr,$hashval,$urival,$loc1,$loc2,$extrameta);
if ($store_rv) {
	$ni_err=true;
	$ni_errno=494;
	$ni_errstr="Bummer: $ni_errno I don't have $urival \nBad algorithm, no good alg found.";
	retErr($ni_errno,$ni_errstr);
}


print "Ok, I've put that there. (for now!)";
exit(0);

?>
