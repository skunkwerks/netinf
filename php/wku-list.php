<?php

include "N-dirs.php";
$wkd = $GLOBALS["cfg_wkd"];
$urlprefix=$GLOBALS["cfg_site"]."/.well-known/ni/";

function getDirectoryList ($directory) {
    // create an array to hold directory list
    $results = array();
    // create a handler for the directory
    $handler = @opendir($directory);
	if ($handler !== false) {
    	// open directory and walk through the filenames
    	while ($file = readdir($handler)) {
      		// if file isn't this directory or its parent, add it to the results
      		if ($file != "." && $file != "..") {
        		$results[] = $file;
      		}
    	}
    	// tidy up: close the handler
    	closedir($handler);
	}
    // done!
    return $results;
}

print "<html><head><title>Current List Named Data Objects here</title></head><body>";

print "<h1>Current List of NetInf Named Data Objects here</h1>";

print "<p>This is the list of things named with hashes here, see <a href=\"http://tools.ietf.org/html/draft-farrell-decade-ni/\">draft-farrell-decade-ni</a> for the specification.</p>";
print "<p>You can do NetInf protocols things <a href=\"/getputform.html\">here</a></p>";

// For test purpuses use this and mkdir .../ni/there to check error handling here
// $alglist=array("sha-256","notthere","there","sha-256-128","sha-256-120","sha-256-96","sha-256-64","sha-256-32");

// sha-256 doesn't need to be last here and is better 1st
$alglist=array("sha-256","sha-256-128","sha-256-120","sha-256-96","sha-256-64","sha-256-32");


print "<h2>Uploaded named data objects</h2>";
print "<p>Here, these get deleted hourly.";

print "<ul>";
$arr=getDirectoryList($GLOBALS["cfg_ndodir"]);
foreach ( $arr as &$fname ) {
	// fname is like sha-256-84.<base64url-hash>, so split those
	$harr=explode(";",$fname);
	$hstr=$harr[0];
	$hashval=$harr[1];
	$path = "$urlprefix$hstr/$hashval";
	$ndofile=$GLOBALS["cfg_ndodir"]."/$hstr;$hashval";
    $metafile=$GLOBALS["cfg_metadir"] . "/". $hstr . ";" . $hashval;
    $metalink="<a href=\"" . $GLOBALS["cfg_metasite"] . "/" . $hstr . ";" . $hashval  . "\">meta</a>";
    if (file_exists($metafile)) {
	    print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $hashval.  "</a> (".$metalink.")</li>\n";
    } else {
        print "Metafile is: $metafile \n";
	    print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $hashval.  "</a></li>\n";
    }
}
print "</ul>";

print "<h2>Cached search result named data objects</h2>";
print "<ul>";
$arr=getDirectoryList($GLOBALS["cfg_cache"]);
foreach ( $arr as &$fname ) {
	// fname is like sha-256-84.<base64url-hash>, so split those
	$harr=explode(";",$fname);
	$hstr=$harr[0];
	$hashval=$harr[1];
	$path = "$urlprefix$hstr/$hashval";
	$ndofile=$GLOBALS["cfg_cache"]."/$hstr;$hashval";
    $metafile=$GLOBALS["cfg_metadir"] . "/". $hstr . ";" . $hashval;
    $metalink="<a href=\"" . $GLOBALS["cfg_metasite"] . "/" . $hstr . ";" . $hashval  . "\">meta</a>";
    if (file_exists($metafile)) {
	    print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $hashval.  "</a> (".$metalink.")</li>\n";
    } else {
        print "Metafile is: $metafile \n";
	    print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $hashval.  "</a></li>\n";
    }
}
print "</ul>";

print "<h2>All known meta-data</h2>";
print "<ul>";
$arr=getDirectoryList($GLOBALS["cfg_metadir"]);
foreach ( $arr as &$fname ) {
	// fname is like sha-256-84.<base64url-hash>, so split those
	$harr=explode(";",$fname);
	$hstr=$harr[0];
	$hashval=$harr[1];
	$path = "$urlprefix$hstr/$hashval";
	$ndofile=$GLOBALS["cfg_cache"]."/$hstr;$hashval";
    $metafile=$GLOBALS["cfg_metadir"] . "/". $hstr . ";" . $hashval;
    $metalink="<a href=\"" . $GLOBALS["cfg_metasite"] . "/" . $hstr . ";" . $hashval  . "\">meta</a>";
    if (file_exists($metafile)) {
	    print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $hashval.  "</a> (".$metalink.")</li>\n";
    } else {
        print "Metafile is: $metafile \n";
	    print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $hashval.  "</a></li>\n";
    }
}
print "</ul>";

print "<h2>Static (DocRoot) named data objects, with .well-known/ni equivalents</h2>";
print "<p>Some of the above will also be here. That's ok:-)</p>";
print "<ul>";
for ($i=0;$i!=count($alglist);$i++) {
	$hstr=$alglist[$i];
	$arr=getDirectoryList($wkd . "/" . $hstr);
	foreach ( $arr as &$fname ) {
		$path = $urlprefix . $hstr . "/" . $fname;
		$fpath= $wkd . "/" . $hstr . "/" . $fname;
		// print $fpath;
		if (is_link($fpath)) {
			print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $fname.  "</a></li>\n";
		}
	}
}
print "</ul>";
print "</body></html>";

?>
