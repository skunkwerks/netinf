<?php

$urlprefix="http://village.n4c.eu/.well-known/ni/";
$wkd = "/home/dtnuser/data/www/statichtml/.well-known/ni";

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

print "<html><head><title>Current List of NI .well-known URLs here</title></head><body>";
print "<h1>Current List of NI .well-known URLs here</h1>";

// For test purpuses use this and mkdir .../ni/there to check error handling here
// $alglist=array("sha-256","notthere","there","sha-256-128","sha-256-120","sha-256-96","sha-256-64","sha-256-32");

// sha-256 doesn't need to be last here and is better 1st
$alglist=array("sha-256","sha-256-128","sha-256-120","sha-256-96","sha-256-64","sha-256-32");

print "<ul>";
for ($i=0;$i!=count($alglist);$i++) {

	$hstr=$alglist[$i];
	$arr=getDirectoryList($wkd . "/" . $hstr);

	foreach ( $arr as &$fname ) {
		$path = $urlprefix . $hstr . "/" . $fname;
		print "<li><a href=\"" . $path . "\"> ni:///" . $hstr . ";" . $fname.  "</a></li>\n";
	}
}

print "</ul>";
print "</body></html>";

?>
