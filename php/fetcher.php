<?php

$wkd = "/home/dtnuser/data/www/statichtml/.well-known/ni";
$sha256str = "sha-256";
$sha256t16str = "sha-256-16";

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
$badalg=false;
$hashalg = strstr($urival, $sha256t16str, false);
if ($hashalg===false) {
	// print "it's not $sha256t16str \n";
	$hashalg = strstr($urival, $sha256str, false);
	if ($hashalg===false) {
		// print "it's unknown \n";
		$badalg=true;
	} else {
		// print "it is $sha256str \n";
		$hstr = $sha256str;
	}
} else {
	// print "it is $sha256t16str \n";
	$hstr = $sha256t16str;
}

$hashend = strpos($hashalg,"?");
if (!$badalg && $hashend === false ) {
	$hashval = substr($hashalg,strlen($hstr) + 1);
	// print "no ?\n";
} else {
	$hashval = substr($hashalg,strlen($hstr) + 1, $hashend -(strlen($hstr)+1));
	// print "hashend $hashend got ?\n";
}

if (!$badalg) {

	$filename = $wkd . "/" . $hstr . "/" . $hashval ;
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

} else {
	header('HTTP/1.0 404 Not Found');
	print "I don't have $urival \n";
}


?>
