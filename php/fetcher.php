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
		// print "it's not $hstr \n";
	} else {
		// print "it *IS* $hstr \n";
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
		// print "no ?\n";
	} else {
		$hashval = substr($hashalg,strlen($hstr) + 1, $hashend -(strlen($hstr)+1));
		// print "hashend $hashend got ?\n";
	}

	// the name of the .well-known file for this name
	$filename = $wkd . "/" . $hstr . "/" . $hashval ;
	// print "Checking $filename";
	if (file_exists($filename)) {

		// new plan - if its a link then return a 307 for the file, if 
		// the file lives in the .wku directory then just return it
		if (!is_link($filename)) {
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
			// return 307 for that
 			$docRoot = getenv("DOCUMENT_ROOT");
			$realfilename=readlink($filename);
			// realfilename needs to be below docRoot or else
			if (substr($realfilename,0,strlen($docRoot))!=$docRoot) {
				header('HTTP/1.0 404 Not Found');
				print "I don't have $urival \n";
				print "I know the link, but its to a bad place";
			} else {
				print $realfilename;
				print $docRoot;
				print $top;
				print "<br/>";
				$top = $_SERVER['SERVER_NAME'];
				$reluri=substr($realfilename,strlen($docRoot));
				$location="http://" . $top .  $reluri;
				print $location;
    			$hs = headers_sent();
				// bits here inspired by http://edoceo.com/creo/php-redirect
				if ($hs) {
					header( "HTTP/1.1 307 Temporary Redirect HTTP/1.1",true,307);
					header("Location: " . $location);
        			header('Cache-Control: no-store, no-cache, must-revalidate, post-check=0, pre-check=0');
				} else {
       				$cover_div_style = 'background-color: #ccc; height: 100%; left: 0px; position: absolute; top: 0px; width: 100%;';
        				echo "<div style='$cover_div_style'>\n";
        				$link_div_style = 'background-color: #fff; border: 2px solid #f00; left: 0px; margin: 5px; padding: 3px; ';
        				$link_div_style.= 'position: absolute; text-align: center; top: 0px; width: 95%; z-index: 99;';
        				echo "<div style='$link_div_style'>\n";
        				echo "<p>Please See: <a href='$location'>".htmlspecialchars($location)."</a></p>\n";
        				echo "</div>\n</div>\n";
				}
			}
		}
	} else {
		header('HTTP/1.0 404 Not Found');
		print "I don't have $urival \n";
		// print "File; $filename\n";
	} 
}


?>
