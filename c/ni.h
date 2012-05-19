/*!
 * @file ni.h
 * @brief This is the external interface for 'C' implementation of the ni/nih URI handling library
 * @version $Revision: 1.32$ $Author: stephen$
 * @version Copyright (C) 2012 Trinity College Dublin

	This is the NI URI library developed as
	part of the SAIL project. (http://sail-project.eu)

	Specification(s) - note, versions may change
		http://tools.ietf.org/html/dratft-farrell-decade-ni-06
		http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-02
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

/*
*/

/// The length of an ni URI
#define NILEN 4096

/// For now, just a buffer on the stack, probably change in a bit
typedef char niname[NILEN];

/// Supported hash functions 
/// The URI maker will put the right hash value after the alg.
/// string (incl. ";") and leaves the rest of the input URI alone
#define SHA256STR "sha-256"
#define SHA256T32STR "sha-256-32"
#define SHA256T64STR "sha-256-64"
#define SHA256T96STR "sha-256-96"
#define SHA256T120STR "sha-256-120"
#define SHA256T128STR "sha-256-128"

/// matching status from checknif/checknib
#define NI_OK 0 /// success - good match
#define NI_BAD 1 /// fair - bad match
#define NI_CDBAD 2 /// weirdo - hash matches but check digit doesn't (nih: only)
#define NI_CDINBAD 3 /// input checkdigit doesn't match input name, probaby typo



/*!
 * @brief make an ni/nih URI for a filename
 * @param ni/nih is the URI (in/out)
 * @param fname is a file name (in)
 * @return zero on success, non-zero for error
 *
 * Given an ni/nih name, open a file, hash it and add the hash to
 * the URI after the hashalg string.
 * 
 * The input name should be like: ni://tcd.ie/sha-256;?query-stuff
 * or nih:sha-256-32;
 * 
 * The ";" after the hash alg is optional
 */
int makenif(niname name,char *fname);

/*!
 * @brief make an NI URI for a buffer
 * @param ni is the URI (in/out)
 * @param blen is the buffer length
 * @param buf is the buffer 
 * @return zero on success, non-zero for error
 *
 * See makenif for more details
 */
int makenib(niname name,long blen, unsigned char *buf);

/*!
 * @brief make a .well-known URL with a hash for a filename
 * @param wku is the URL (in/out)
 * @param fname is a file name (in)
 * @return zero on success, non-zero for error
 *
 * Given a URL, open a file, hash it and add the hash to
 * a .well-known URL after the hashalg.
 * 
 * The input URL should be like: http://tcd.ie/.well-known/ni/sha-256/path?query-stuff
 * Well Known URLs are defined in RFC 5785
 */
int makewkuf(niname wku,char *fname);

/*!
 * @brief make a .well-known URL with a hash for a buffer
 * @param wku is the URL (in/out)
 * @param blen is the buffer length
 * @param buf is the buffer 
 * @return zero on success, non-zero for error
 *
 * Given a URL, open a file, hash it and add the hash to
 * a .well-known URL after the hashalg.
 * 
 * The input URL should be like: http://tcd.ie/.well-known/ni/sha-256/path?query-stuff
 * Well Known URLs are defined in RFC 5785
 */
int makewkub(niname wku, long blen, unsigned char *buf);


/*!
 * @brief check if an ni/nih URI matches a file's content
 * @param ni is the URI (in)
 * @param fname is a file name (in)
 * @param res is the result (out)
 * @return zero on success, non-zero for error
 *
 * Given an ni name, open a file, hash it and compare the hash to
 * the URI (somewhere, details TBD)
 *
 * If the URI and file content match, res will be zero
 * If the URI and file content do not match, res will be non-zero
 * res is only meaninful if the function returns 0 (i.e. no error)
 * An example error would be if a hash function is not supported,
 * in that case the function returns an error and res is not set
 */
int checknif(niname name, char *fname, int *res);

/*!
 * @brief check if an ni/nih URI matches a buffer
 * @param ni is the URI (in)
 * @param blen is the buffer length
 * @param buf is the buffer 
 * @param res is the result (out)
 * @return zero on success, non-zero for error
 *
 * Given an ni name, open a file, hash it and compare the hash to
 * the URI (somewhere, details TBD)
 *
 * If the URI and file content match, res will be zero
 * If the URI and file content do not match, res will be non-zero
 * res is only meaninful if the function returns 0 (i.e. no error)
 * An example error would be if a hash function is not supported,
 * in that case the function returns an error and res is not set
 */
int checknib(niname name, long blen, unsigned char *buf, int *res);

/*!
 * @brief return a ptr to a string for the hash alg or NULL if we don't know
 * @param ni is the URI (in)
 * @param olen (out) is the length of those hashes in bits
 * @param basefnc (out) is the local id of the hash alg (0==sha256 only one for now)
 * @param pointer to a const char * string or null 
 * 
 * Scan the input name for a known hash alg and return our standard form
 * of that. If we can't find one, return null.
 */
const char *whichhash(niname name, int *olen, int *basefnc);

/*!
 * @brief map an ni/nih name to a .well-known URL
 * @param name is the URI (in)
 * @param wku is the .well-known URL (out)
 * @return zero for success, non-zero for error
 * 
 * Scan the input name for a known hash alg and return our standard form
 * of that. If we can't find one, return null.
 */
int mapnametowku(niname name, niname wku);

/*============== Lower Level Interface ==================================*/

/*!
 * @brief initialise hash digest mechanism of OpenSSL
 * @return zero for success, non-zero for error
 * 
 * Allows future use of selection of digest mechanism by name.
 */
int ni_ic_init();

/*!
 * @brief extract file component from URL which should be name of hash algorithm
 * @param original URL (might be relative) (in)
 * @param file component (out)
 * @return zero for success, non-zero for error
 * 
 * Finds part of URL between last slash (or beginning of URL if no slashes)
 * and next separator after slash (one of ";?#" or end of URL if no other separators)
 * No validation is done on string - this is postponed to ni_ic_set_alg.
 * The output is copied into a buffer provided by caller.
 */
int ni_ic_get_file_compt(const char *url,  char *ni_alg_name);

/*!
 * @brief select the hash algorithm to use by name and initialise digest construction
 * @param name of digest algorithm to be used (in(
 * @return zero for success, non-zero for error
 * 
 * The name should be in our standard form - 
 *   <alg type>-<base length in bits>-<truncated length in bits>
 * e.g. sha-256-16 - use SHA256 algorithm and truncate result to 16 bits
 * before URL safe encoding using base64 representation.
 * Sets up context so that multiple buffers of input can be fed in to
 * update the digest value before reading of final digest.
 * Returns error if name is in wrong form or OpenSSL doesn't support
 * algorithm.
 * 
 * not sure there - sha3 maybe wouldn't have names like that (SF)
 */
int ni_ic_set_alg(const char *ni_alg_name);

/*!
 * @brief update digest state with contents of a buffer
 * @param buffer to be scanned (in)
 * @param length of buffer in octets (out)
 * @return zero for success, non-zero for error
 * 
 * Update previously initialised hash context with contents of buffer.
 * Return error if context not initialized, digest has been generated
 * or update fails.
 */
int ni_ic_update(unsigned char * buf, long buflen);

/*!
 * @brief generate digest based on previous algorithm and buffer updates 
 * @param length of digest string (less terminating null) (out)
 * @return zero for success, 1 if called again after finalizing, other non-zero for error
 * 
 * Finalise the hash digest and create the URL-safe base64 encoding.	
 * Stores the digest internally for future comparison or retrieval.
 * Resets OpenSSL context ready for new digests.
 */
int ni_ic_finalize(long *digest_len);

/*!
 * @brief retrieve previously calculated digest
 * @param digest string (null terminated) (out) as a base64url encoded string
 * @param digest string length (excluding null termination) (out)
 * @return zero for success, non-zero for error
 *
 * Note caller allocated space for digest, error returned if not enough
 */
int ni_ic_get_digest(char *digest, long *digest_len);

/*!
 * @brief compare digest string with previously calculated digest
 * @param digest to be compared (in) as a base64url encoded string
 * @param length of digest to be compared (in)
 * @return zero if strings compare equal, non-zero otherwise.
 */
int ni_ic_check_digest(char *digest, long digest_len);


