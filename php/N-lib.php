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

include "N-dirs.php";

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
		header("Cache-Control: no-cache, must-revalidate"); // HTTP/1.1
		header('Content-Type: ' . $mime);
		header('Content-Length: ' . filesize($filename));
		header('Content-Disposition: inline; filename=' . basename($filename));
		ob_clean();
    	flush();
		readfile($filename);
		// bit of debug
		if ($GLOBALS["cfg_debug"]!=0) {
		    $fcp=fopen("/tmp/GET-RESP-fa","w");
		    fwrite($fcp,"Just sent $filename\n");
		    fclose($fcp);
        }
	}

	function sendMIMEWithFile($jfilename,$filename,$msgid) {

		$mime_boundary=hash("sha256",time());
		$shortfilename=basename($filename);
		$msg = "";
		// the application/json bit
		$msg .= "--".$mime_boundary. "\n";

		$msg .= "Content-Type: application/json". "\n";
		$msg .= "\n";
		$jmsg = file_get_contents($jfilename);
		$jmsg .= " ] }\n\n";

		// reduce jmsg
		$rjmsg="";
		$rv=jreduce($jmsg,$rjmsg);
		if ($rv==1) { // error, use original
			$msg .= $jmsg;
		} else { // nice - use reduced
			$msg .= $rjmsg;
			$msg .= "\n";
			$msg .= "\n";
		}

		// the payload

		$msg .= "--".$mime_boundary. "\n";
		$finfo = finfo_open(FILEINFO_MIME_TYPE); // return mime type ala mimetype extension
		$mime = finfo_file($finfo, $filename);
		finfo_close($finfo);
		$msg .= "Content-Type:  " . $mime  . " name=\"".$shortfilename."\"". "\n";
		$msg .= "\n";
		$msg .= file_get_contents($filename);
		$msg .= "\n--".$mime_boundary."--". "\n\n";

		// headers
		header('MIME-Version: 1.0');
		header("Content-Type: multipart/mixed; boundary=".$mime_boundary);
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

		// bit of debug
		if ($GLOBALS["cfg_debug"]!=0) {
		    $fcp=fopen("/tmp/GET-RESP-mf","w");
		    fwrite($fcp,$msg);
		    fclose($fcp);
        }

	}

	function sendMIMEJSONOnly($jfilename,$msgidval) {

		$mime_boundary=hash("sha256",time());
		$msg = "\n";
		$jmsg = file_get_contents($jfilename);
		$jmsg .= " ] }\n\n";
		//reduce jmsg

		// reduce jmsg
		$rjmsg="";
		$rv=jreduce($jmsg,$rjmsg);
		if ($rv==1) { // error, use original
			$msg .= $jmsg;
		} else { // nice - use reduced
			$msg .= $rjmsg;
			$msg .= "\n";
			$msg .= "\n";
		}

		// headers
		header('MIME-Version: 1.0');
		header("Content-Type: application/json; boundary=\"".$mime_boundary."\"");
		header('Content-Length: ' . strlen($msg));
		header('Content-Disposition: inline; filename=' . basename($filename));
		// definitely don't cache for now:-)
		header('Expires: Thu, 01-Jan-70 00:00:01 GMT');
		header('Last-Modified: ' . gmdate('D, d M Y H:i:s') . ' GMT');
		header('Cache-Control: no-store, no-cache, must-revalidate');
		header('Cache-Control: post-check=0, pre-check=0', false);
		header('Pragma: no-cache');
		print $msg;
		// bit of debug
		if ($GLOBALS["cfg_debug"]!=0) {
		    $fcp=fopen("/tmp/GET-RESP-jo","w");
		    fwrite($fcp,$msg);
		    fclose($fcp);
        }
	}

	function getMetaDir() {
		$metadir=$GLOBALS["cfg_metadir"];
		// check we can write there, if not fallback to /tmp
		$tf="$metadir/foobar";
		$fp=fopen($tf,"w");
		if (!$fp) {
			$metadir="/tmp";
		} else {
			fclose($fp);
			unlink("$metadir/foobar");
		} 
		return($metadir);
	}

	function storeMeta($hstr,$hashval,$urival,$loc1,$loc2,$extrameta) {
		// make locators a good JSON array
		$locstr="";
        if ($loc1=="" && $loc2=="") {
            $locstr = "[] ";
		} else if ($loc1=="") {
			$locstr = "[ \"$loc2\" ] ";
		} else if ($loc2=="") {
			$locstr = "[ \"$loc1\" ] ";
		} else {
			$locstr = "[ \"$loc1\" , \"$loc2\" ] ";
		}
		$timestamp= date(DATE_ATOM);
        if ($extrameta!="") {
		    $jsonev = "{ \"ts\" : \"$timestamp\", \"loc\" : $locstr, \"metadata\" : $extrameta }";
        } else {
		    $jsonev = "{ \"ts\" : \"$timestamp\", \"loc\" : $locstr }";
        }
		$metadir=getMetaDir();
		$jfilename = "$metadir/$hstr;$hashval";
		// print "time: $timestamp\nEV: $jsonev\nFile: $jfilename\n";
		if (file_exists($jfilename)) {
			$fh=fopen($jfilename,"a");
			if (!$fh) {
				$ni_err=true;
				$ni_errno=493;
				$ni_errstr="Bummer: $ni_errno I don't have $urival \nBad algorithm, no good alg found.";
				retErr($ni_errno,$ni_errstr);
			}
			fwrite($fh,",\n");
			fwrite($fh,$jsonev);
			fwrite($fh,"\n");
			fclose($fh);
		} else {
			$jsonhead="{ \"NetInf\" : \"v0.1a Stephen\"\n,\"ni\" : \"$urival\",\n\"details\" : [\n";
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
			fwrite($fh,"\n");
			fclose($fh);
		}
	}

	function checkMeta($hstr,$hashval) {
		$metadir=getMetaDir();
		$jfilename = "$metadir/$hstr;$hashval";
		if (file_exists($jfilename)) {
			return($jfilename);
		} else {
			return(false);
		}
	}

	// merge the locator arrays known about an NDO into one
	// with no repeats
	function jreduce($in,&$out) {
		$jstr=json_decode($in);
		if ($jstr==NULL) return(1);
		$ojstr->NetInf=$jstr->NetInf;
		$ojstr->ni=$jstr->ni;
		$oloccnt=0;
		$olocs=array();
        $metas=(object)NULL;
        $metacnt=0;
		foreach ($jstr->details as $det) {
            if (count($det->loc)!=0) {
			    foreach ($det->loc as $loc) {
                    if (count($loc)!=0) {
				        $olocs[$oloccnt]=$loc;
				        $oloccnt++;
                    }
                }
			}
            if ($det->metadata) {
                $metas=(object) array_merge((array)$metas,(array)$det->metadata);
                $metacnt++;
            }
		}
		$ojstr->ts=date(DATE_ATOM);
        if ($metacnt!=0) {
		    $ojstr->metadata=$metas;
            // $ojstr->metacnt="$metacnt";
        }
        if ($oloccnt==0) {
            $ojstr->loc=array();
        } else {
		    $ojstr->loc=array_values(array_unique($olocs));
        }
		$tmp=json_encode($ojstr);
		if ($tmp===false) return(1);
		// PHP 5.4.0 has JSON_UNESCAPED_SLASHES but not my version, so hack it
		$out=str_replace('\/','/',$tmp);
	}

	function getNDOfname($hstr,$hashval) {
		// check if we also have a well-known and where that
		// points
		$ndofile="";
		$wkf=$GLOBALS["cfg_wkd"]."/$hstr/$hashval";
		if (file_exists($wkf)) {
			if (!is_link($wkf)) {
				$ndofile=$wkf;
			} else {
				$ndofile=readlink($wkf);
			}
		} else {
			// if no sign so far check for the configured place
			$ndofile=$GLOBALS["cfg_ndodir"]."/$hstr;$hashval";
		}
		return($ndofile);
	}

?>
