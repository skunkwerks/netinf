<?php

/*
 * @file N-SEARCH.php
 * @brief PHP server side processing of NetInf SEARCH for HTTP CL
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
$tokens = filter_input(INPUT_POST, 'tokens');
$msgidval = $_REQUEST['msgid'];
$extval = $_REQUEST['ext'];
$rform = $_REQUEST['rform'];
if ($rform == "") $rform="json";
if ($rform != "html" && $rform!="json") {
    header('HTTP/1.0 404 Malformed response format');
    print "Can't respond with \"$rform\" use \"html\" or \"json\" only.\n";
    exit(1);
    
}


// test - one I have
// $tokens = 'Delay';
// $msgidval = 100;
// $extval = "";
	
// test - one I don't have (and is invalid)
// $tokens = "ni:///sha-256;xxxxxoQ-h1bb0Ovu99EJUVQqyarpRQ4EQ0bCmJgY";
// $msgidval = 100;
// $extval = "";

// Go check the wiki guys 


// fetch by title
// $wikistring="http://en.wikipedia.org/w/api.php?action=query&titles=$tokens&inprop=url&format=xml";

ini_set("user_agent","Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.0)");
ini_set("max_execution_time", 0);
ini_set("memory_limit", "10000M");

/*
// json variant, this is easier but responses don't contain URLs for objects, just titles
// which'd mean another roundtrip. Bummer.
// search, results in json
$wikistring="http://en.wikipedia.org/w/api.php?action=opensearch&search=$tokens&limit=10&namespace=0&format=json";
$json = file_get_contents($wikistring);
if ($json===false) {
    header('HTTP/1.0 500 Crappy Server error');
    print "Can't search for $tokens \n";
    exit(1);
}
$obj = json_decode($json);
print_r($obj);
*/

// XML variant
// search, results in xml 
$wikistring="http://en.wikipedia.org/w/api.php?action=opensearch&search=$tokens&limit=10&namespace=0&format=xml";
$xmlfile=simplexml_load_file($wikistring);
if ($xmlfile === false ) {
    header('HTTP/1.0 500 Crappy Server error');
    print "Can't search for $tokens \n";
    exit(1);
}

if ($rform=="html") {
    print "<html><head><title>NetInf Search results</title></head><body>";
    print "<h1>NetInf Search results</h1>";
    print "<br/>";
    print "<ul>";
}

$results=array();
$resind=0;
foreach ( $xmlfile->Section->Item as $item) {
    $results[$resind]=array();
    $results[$resind]['text']=$item->Text;
    $results[$resind]['loc']=$item->Url;
    $results[$resind]['desc']=$item->Description;
    // grab a copy to a temp place
    $tfname=tempnam("/tmp","ni-wiki-");
    // download, might be slow, optimise later (don't do it if I have copy)
    $rv=copy($item->Url,$tfname);
    // figure out ni name (fixed alg for now)
    $nresults=array();
	$niclcmd = $GLOBALS["cfg_nicl"] . " -g -n 'ni://wikipedia.org/sha-256;' -f " . $tfname;
	exec($niclcmd,$nresults);
	$nistr = $nresults[0];
    $results[$resind]['ni']=$nistr;
    // cache a copy, make the .well-known link, store the meta-data
    getAlg($nistr,$algfound,$hstr,$hashval);
    $filename=$GLOBALS["cfg_cache"]."/".$hstr.";".$hashval;
	rename($tfname,$filename);
    $results[$resind]['file']=$filename;
    // make a link
	$wlname=$GLOBALS["cfg_wkd"]."/$hstr/$hashval";
	$rv=symlink($filename,$wlname);
    $results[$resind]['wku']=$wlname;
    $wku = $GLOBALS["cfg_site"] . "/.well-known/ni/" . $hstr . "/" . $hashval ;
    // make meta-data file
    $extrameta="{ \"search\" : \"$tokens\"}";
    storeMeta($hstr,$hashval,$nistr,$item->Url,$wku,$extrameta);
    // some output please
    if ($rform=="html") {
        print "<li>";
        print "<a href=\"$wku\">$nistr</a>";
        print "</li>";
    }
    // increment, why not
    $resind++;
}

$timestamp= date(DATE_ATOM);
if ($rform=="html") {
    print "</ul><t>Generated at: $timestamp</t></html>";
}
if ($rform=="json") {
    // print "coming soon!";
    print "{\"NetInf\":\"v0.1a Stephen\",\"ts\":\"$timestamp\",\"msgid\"=\"$msgidval\",";
    print "\"results\":[";
    for ($i=0;$i!=$resind;$i++) {
        $nit=$results[$i]['ni'];
        print "{ \"name\":\"$nit\"}";
        if ($i!=($resind-1)) print ",";
    }
    print "]}";
    //print "\n\n\n<br/><br/>";
    //print_r($results);
}
// $xml=$xmlfile->xpath("//page");
// $page=$xml[0];
// if(!$page['missing']){
    // $title=$page['title'];
    // $url=rawurlencode($title);
    // echo'<a href="http://en.wikipedia.org/wiki/'.$url.'" title="'.$title.'">'.$title.'</a>';
// } 
// print_r($xmlfile);

exit(0);

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
print "Can't search for $tokens \n";

?>
