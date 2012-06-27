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

	function sendMIMEAns($jfilename,$filename,$msgid) {

		$mime_boundary=hash("sha256",time());
		$shortfilename=basename($filename);
		$msg = "";
		// the application/json bit
		$msg .= "--".$mime_boundary. "\n";
		$msg .= "Content-Type: application/json; charset=iso-8859-1". "\n";
		$msg .= "\n";
		$msg .= file_get_contents($jfilename);
		$msg .= "\n\n";
		// the payload
		$msg .= "--".$mime_boundary. "\n";
		$finfo = finfo_open(FILEINFO_MIME_TYPE); // return mime type ala mimetype extension
		$mime = finfo_file($finfo, $filename);
		finfo_close($finfo);
		$msg .= "Content-Type:  " . $mime  . " name=\"".$shortfilename."\"". "\n";
		$msg .= "\n";
		$msg .= file_get_contents($filename);
		$msg .= "--".$mime_boundary."--". "\n\n";
		// headers
		header('MIME-Version: 1.0');
		header("Content-Type: multipart/mixed; boundary=\"".$mime_boundary."\"");
		header('Content-Length: ' . strlen($msg));
		header('Content-Disposition: inline; filename=' . basename($filename));
		// definitely don't cache for now:-)
		header('Expires: Thu, 01-Jan-70 00:00:01 GMT');
		header('Last-Modified: ' . gmdate('D, d M Y H:i:s') . ' GMT');
		header('Cache-Control: no-store, no-cache, must-revalidate');
		header('Cache-Control: post-check=0, pre-check=0', false);
		header('Pragma: no-cache');
		// and now the payload
		print $msg;

	}

	function getMetaDir() {
		$metadir="/tmp";
		return($metadir);
	}

	function storeMeta($hstr,$hashval,$urival,$loc1,$loc2) {
		// make locators a good JSON array
		$locstr="";
		if ($loc1=="") {
			$locstr = "[ $loc2 ] ";
		} else if ($loc2=="") {
			$locstr = "[ $loc1 ] ";
		} else {
			$locstr = "[ $loc1 , $loc2 ] ";
		}
		$timestamp= date(DATE_ATOM);
		$jsonev = "{ \"ts\" : \" $timestamp \", \"loc\" : $locstr }";
		$metadir=getMetaDir();
		$jfilename = "$metadir/$hstr.$hashval";
		// print "time: $timestamp\nEV: $jsonev\nFile: $jfilename\n";
		if (file_exists($jfilename)) {
			$fh=fopen($jfilename,"a");
			if (!$fh) {
				$ni_err=true;
				$ni_errno=493;
				$ni_errstr="Bummer: $ni_errno I don't have $urival \nBad algorithm, no good alg found.";
				retErr($ni_errno,$ni_errstr);
			}
			fwrite($fh,"\n");
			fwrite($fh,$jsonev);
			fwrite($fh,",\n");
			fclose($fh);
		} else {
			$jsonhead="{ \"NetInf\" : \"v0.1a Stephen\"\n,\"ni\" : \"$urival\",\n[\n";
			$fh=fopen($jfilename,"w");
			if (!$fh) {
				$ni_err=true;
				$ni_errno=493;
				$ni_errstr="Bummer: $ni_errno I don't have $urival \nBad algorithm, no good alg found.";
				retErr($ni_errno,$ni_errstr);
			}
			fwrite($fh,$jsonhead);
			fwrite($fh,"\n");
			fwrite($fh,$jsonev);
			fwrite($fh,",\n");
			fclose($fh);
		}
	}

	function checkStore($hstr,$hashval) {
		$metadir=getMetaDir();
		$jfilename = "$metadir/$hstr.$hashval";
		if (file_exists($jfilename)) {
			return($jfilename);
		} else {
			return(false);
		}
	}

?>
