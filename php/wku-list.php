<?php

$urlprefix="http://village.n4c.eu/.well-known/ni/";
$wkd = "/home/dtnuser/data/www/statichtml/.well-known/ni";
$sha256str = "sha-256";

function getDirectoryList ($directory) {
    // create an array to hold directory list
    $results = array();
    // create a handler for the directory
    $handler = opendir($directory);
    // open directory and walk through the filenames
    while ($file = readdir($handler)) {
      // if file isn't this directory or its parent, add it to the results
      if ($file != "." && $file != "..") {
        $results[] = $file;
      }
    }
    // tidy up: close the handler
    closedir($handler);
    // done!
    return $results;
}

print "<html><head><title>Current List of NI .well-known URLs here</title></head><body>";
print "<h1>Current List of NI .well-known URLs here</h1>";

$arr=getDirectoryList($wkd . "/" . $sha256str);

print "<ul>";
foreach ( $arr as &$fname ) {
	$path = $urlprefix . $sha256str . "/" . $fname;
	print "<li><a href=\"" . $path . "\"> ni:///" . $sha256str . ";" . $fname.  "</a></li>\n";
}

print "</ul>";
print "</body></html>";

?>
