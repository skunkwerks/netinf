<?php

/*
 * @file N-lib.php
 * @brief library for PHP server side processing of NetInf for HTTP CL
 * @version $Revision: 0.01 $ $Author: stephen $
 * @version Copyright (C) 2012 Trinity College Dublin
	This is the NI PHP Server library developed as
	part of the SAIL project. (http://sail-project.eu)
	Protocol Specification(s) - note, versions may change
		draft-netinf-proto.txt - unpublished
	Server spec: this code:-)
	
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

// Functions, move to library in a bit

	function getAlg($lurival,&$lalgfound,&$lhstr,&$lhashval) {
		$lalgfound=false;
		$lhashalg="";
		// sha-256 better be last here, or we'll get an error'd first match
		$alglist=array("sha-256-128","sha-256-120","sha-256-96","sha-256-64","sha-256-32","sha-256");
		for ($i=0;!$lalgfound && $i<count($alglist);$i++) {
			$lhstr=$alglist[$i];
			$lhashalg = strstr($lurival, $lhstr, false);
			if ($lhashalg===false) {
				; // nowt
			} else {
				$lalgfound=true;
			}
		}
		if (!$lalgfound) return(false);
		$lhashend = strpos($lhashalg,"?");
		if ($lhashend === false ) {
			$lhashval = substr($lhashalg,strlen($lhstr) + 1);
		} else {
			$lhashval = substr($lhashalg,strlen($lhstr) + 1, $lhashend -(strlen($lhstr)+1));
		}
		return(true);
	}

	// give an error return
	function retErr($errval,$errstr) {
		// handle $errval values later
		header('HTTP/1.0 404 Not Found');
		print $errstr;
		return(true);
	}

	// return the actual file
	function sendFileAns($filename,$msgid) {
		// new plan - if its a link then return a 307 for the file, if 
		// the file lives in the .wku directory then just return it
		header('Content-Description: File Transfer');
		$finfo = finfo_open(FILEINFO_MIME_TYPE); // return mime type ala mimetype extension
    	$mime = finfo_file($finfo, $filename);
		finfo_close($finfo);
		// header("Cache-Control: no-cache, must-revalidate"); // HTTP/1.1
		header('Content-Type: ' . $mime);
		header('Content-Length: ' . filesize($filename));
		header('Content-Disposition: inline; filename=' . basename($filename));
		readfile($filename);
	}
	
?>
