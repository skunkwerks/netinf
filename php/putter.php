<?php

$wkd = "/home/dtnuser/data/www/statichtml/.well-known/ni";
$sha256str = "sha-256";
$sha256t16str = "sha-256-16";

// hackety hack
$nicl = "/home/stephen/code/nilib/c/nicl";

$urival = filter_input(INPUT_POST, 'URI');
$msgidval = $_REQUEST['msgid'];
$extval = $_REQUEST['ext'];
$loc1 = $_REQUEST['loc1'];
$loc2 = $_REQUEST['loc2'];
// get that file
$gotfile=false;
if ($_FILES["octets"]["error"] > 0 ) {
	$fname = "none";
	$ftmp = "none";
	// print "No file given";
} else {
	$fname = $_FILES["octets"]["name"];
	$ftmp = $_FILES["octets"]["tmp_name"];
	$gotfile = true;
	// print "Got a file -- " ;
}

// print $urival;
// print "--";
// print $fname;
// print "--";
// print $ftmp;
// print "--";

// What needs doing?
// Pseudo-code
// check_params() incl. name-data-integrity
// if no errors
//    put file someplace
//    put well-known link where it needs to be
// what to do with locators or if incomplete req?

// extract hashalg and hash and check for file, if it exists print it, otherwise 404
$hstr = "";
$badalg=true;
$hashalg = strstr($urival, $sha256t16str, false);
if ($hashalg===false) {
	// print "it's not $sha256t16str \n";
	$hashalg = strstr($urival, $sha256str, false);
	if ($hashalg===false) {
		// print "it's unknown \n";
		$badalg=true;
	} else {
		// print "it is $sha256str \n";
		$badalg=false;
		$hstr = $sha256str;
	}
} else {
	// print "it is $sha256t16str \n";
	$hstr = $sha256t16str;
	$badalg=false;
}

if ($badalg) {
	header('HTTP/1.0 404 Not Found');
	print "Unknown hash algorithm in $urival \n";
	exit("done");
}

$hashend = strpos($hashalg,"?");
if ($hashend === false ) {
	$hashval = substr($hashalg,strlen($hstr) + 1);
	// print "no ?\n";
} else {
	$hashval = substr($hashalg,strlen($hstr) + 1, $hashend -(strlen($hstr)+1));
	// print "hashend $hashend got ?\n";
}

if ($gotfile) {
	// check name-data-integrity
	$niclcmd = $nicl . " -v -n '" . $urival . "' -f " . $ftmp;
	// print "--";
	// print $niclcmd;
	// print "--";
	exec($niclcmd,$results);
	$answer = $results[0];
	// print $answer;
	$ndifile=($answer=="good");
	if ($ndifile) {
		print "Good - nice";
	} else {
		header('HTTP/1.0 404 Not Found');
		print "Bad - feck off";
		exit("done");
	} 

	$filename = $wkd . "/" . $hstr . "/" . $hashval ;

	$filename = $wkd . "/" . $hstr . "/" . $hashval ;
	if (file_exists($filename)) {
		header('HTTP/1.0 404 Not Found');
		print "I already have $urival \n";
	} else {
		// print "File; $filename\n";
		move_uploaded_file($ftmp,$filename);
		print "Ok, I've put that there. (for now!)";
		exit("testing testing");

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
	} 

}



?>
