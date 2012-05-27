<?php

$wkd = "/home/dtnuser/data/www/statichtml/.well-known/ni";
// sha-256 better be last here, or we'll get an error'd first match
$alglist=array("sha-256-128","sha-256-120","sha-256-96","sha-256-64","sha-256-32","sha-256");

// hackety hack
$nicl = "/home/stephen/code/netinf-code/c/nicl";

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
$hstr = "";
$algfound=false;
for ($i=0;!$algfound && $i<count($alglist);$i++) {
	$hstr=$alglist[$i];
	$hashalg = strstr($urival, $hstr, false);
	if ($hashalg===false) {
		// print "it's not $hstr \n";
	} else {
		// print "it *IS* $hstr \n";
		$algfound=true;
	}
}
if (!$algfound) {
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
		// print "Good - nice";
	} else {
		header('HTTP/1.0 404 Not Found');
		print "Bad - feck off";
		exit("done");
	} 

	$filename = $wkd . "/" . $hstr . "/" . $hashval ;
	if (file_exists($filename)) {
		header('HTTP/1.0 404 Not Found');
		print "I already have $urival \n";
	} else {
		// print "File; $filename\n";
		move_uploaded_file($ftmp,$filename);
		print "Ok, I've put that there. (for now!)";
		exit();

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
