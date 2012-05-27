<?php

$wkd = "/home/dtnuser/data/www/statichtml/.well-known/ni";
// sha-256 better be last here, or we'll get an error'd first match
$alglist=array("sha-256-128","sha-256-120","sha-256-96","sha-256-64","sha-256-32","sha-256");


// $urival = $_REQUEST['URI'];
// $urival = filter_input(INPUT_POST, 'URI', FILTER_SANITIZE_ENCODED);
$urival = filter_input(INPUT_POST, 'URI');
$msgidval = $_REQUEST['msgid'];
$extval = $_REQUEST['ext'];

// $urival = "http://village.n4c.eu/.well-known/ni/sha-256/2u8jwt1CTn7_XkvmjMvgIApWtWz34YaiF6Rbbdbj_c4?ct=foo";
// $urival = "ni:///sha-256/2u8jwt1CTn7_XkvmjMvgIApWtWz34YaiF6Rbbdbj_c4?ct=foo";
// $urival = "http://village.n4c.eu/.well-known/ni/sha-256/2U8JWT1ctN7_xKVMJmVGiaPwTwZ34YaiF6Rbbdbj_c4?ct=foo";
// $msgidval = "123";
// $extval =  "";
// $hashalg = "bar";


// print $urival;

// print "\n";

// extract hashalg and hash and check for file, if it exists print it, otherwise 404
$hstr = "";
$algfound=false;
for ($i=0;!$algfound && $i<count($alglist);$i++) {
	$hstr=$alglist[$i];
	$hashalg = strstr($urival, $hstr, false);
	if ($hashalg===false) {
		print "it's not $hstr \n";
	} else {
		print "it *IS* $hstr \n";
		$algfound=true;
	}
}

if (!$algfound) {
	header('HTTP/1.0 404 Not Found');
	print "I don't have $urival \n";
	print "Bad algorithm, no good alg found.";
} else {

	$hashend = strpos($hashalg,"?");
	if ($hashend === false ) {
		$hashval = substr($hashalg,strlen($hstr) + 1);
		print "no ?\n";
	} else {
		$hashval = substr($hashalg,strlen($hstr) + 1, $hashend -(strlen($hstr)+1));
		print "hashend $hashend got ?\n";
	}

	$filename = $wkd . "/" . $hstr . "/" . $hashval ;
	print "Checking $filename";
	if (file_exists($filename)) {
		header('Content-Description: File Transfer');
		$finfo = finfo_open(FILEINFO_MIME_TYPE); // return mime type ala mimetype extension
    	$mime = finfo_file($finfo, $filename);
		finfo_close($finfo);
		// header("Cache-Control: no-cache, must-revalidate"); // HTTP/1.1
		header('Content-Type: ' . $mime);
		header('Content-Length: ' . filesize($filename));
		header('Content-Disposition: inline; filename=' . basename($filename));
		readfile($filename);
		// print $filename;
	} else {
		header('HTTP/1.0 404 Not Found');
		print "I don't have $urival \n";
		// print "File; $filename\n";
	} 
}


?>
