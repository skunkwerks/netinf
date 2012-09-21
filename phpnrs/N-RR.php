<?php

/*
 * @file N-RR.php
 * @brief PHP NRS
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

// include 'N-lib.php';
require "../../predis/autoload.php";
Predis\Autoloader::register();



// read request attrs or use test value

// test for CLI
// $urival = "ni:///sha-256;ElI8UC-1uqkYzDbQ7x46GW8RmMai9Rgs_344rx7kx3E";
// $hint1 = "wikipedia.org";
// $hint2 = "tcd.ie";
// $loc1 = "http://wikipedia.org/bar";
// $loc2 = "http://example.com";
// $meta = "test content";
// $stage = "zero";

// read it from HTTP POST form data
$urival = filter_input(INPUT_POST, 'URI');
$hint1 = filter_input(INPUT_POST, 'hint1');
$hint2 = filter_input(INPUT_POST, 'hint2');
$loc1 = filter_input(INPUT_POST, 'loc1');
$loc2 = filter_input(INPUT_POST, 'loc2');
$meta = filter_input(INPUT_POST, 'meta');
$stage = filter_input(INPUT_POST, 'stage');

// print "Got it: URI = $urival\n";

/*
if ($stage=="zero") {
    print "you want me to register that\n";
}
if ($stage=="one") {
    print "you want me to look that up\n";
}
*/
if ($stage!="zero" && $stage!="one") {
    header('HTTP/1.0 404 stupid input');
    print "feck off\n";
}

try {
    $redis = new Predis\Client();
/*
    $redis = new Predis\Client(array(
        "scheme" => "tcp",
        "host" => "127.0.0.1",
        "port" => 6379));
*/
    // print "Successfully connected to Redis\n";
}
catch (Exception $e) {
    header('HTTP/1.0 500 stupid DB');
    print "Couldn't connected to Redis\n";
    print $e->getMessage();
	print "\n";
}

// update/add a record
if ($stage=="zero") {
	// replace any values provided that aren't empty
	if (strlen($loc1)>0) { $redis->hmset($urival,"loc1",$loc1); }
	if (strlen($loc2)>0) { $redis->hmset($urival,"loc2",$loc2); }
	if (strlen($hint1)>0) { $redis->hmset($urival,"hint1",$hint1); }
	if (strlen($hint2)>0) { $redis->hmset($urival,"hint2",$hint2); }
	if (strlen($meta)>0) { $redis->hmset($urival,"meta",$meta); }

	// $redis->hmset($urival,"loc1",$loc1,"loc2",$loc2,"hint1",$hint1,"hint2",$hint2,"meta",$meta);
}

// test
$stage="one";

// retrieve the record and return some JSON
header('MIME-Version: 1.0');
header("Content-Type: application/json");
$r->Netinf="v0.1a Stephen";
$r->ni=$urival;
$r->ts=date(DATE_ATOM);
$rloc1=$redis->hmget($urival,"loc1");
$rloc2=$redis->hmget($urival,"loc2");
$r->loc=array_merge($rloc1,$rloc2);
$rhint1=$redis->hmget($urival,"hint1");
$rhint2=$redis->hmget($urival,"hint2");
$r->hints=array_merge($rhint1,$rhint2);
$r->meta=$redis->hmget($urival,"meta");

$tmp=json_encode($r);
$jout=str_replace('\/','/',$tmp);

print $jout;
// test
print "\n";


exit(0);

?>

