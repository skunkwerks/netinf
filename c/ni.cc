/*!
 * @file ni.cc
 * @brief This is the external interface for the NI URI handling library
	 * @version $Revision: 1.32 $ $Author: stephen $
 * @version Copyright (C) 2012 Trinity College Dublin

	This is the NI URI library developed as
	part of the SAIL project. (http://sail-project.eu)

	Specification(s) - note, versions may change
		http://tools.ietf.org/html/farrell-decade-ni-00
		http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00
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

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <openssl/sha.h>
#include <openssl/bio.h>
#include <openssl/buffer.h>
#include <openssl/evp.h>
#include "ni.h"

/* ---------------- table of hash function ---------------*/
/// hash function table
typedef struct {
	const char *str; /// string form of hash name (case insensitive here)
	int olen; /// number of output bits to use 
	int basefnc; /// hash function on which this is based
} ht_str;

#define NUMHASHES 6

ht_str hashalgtab[NUMHASHES] = {
	{ SHA256T32STR,32,0}, 
	{ SHA256T64STR,64,0},
	{ SHA256T96STR,96,0},
	{ SHA256T120STR,120,0},
	{ SHA256T128STR,128,0},
	{ SHA256STR,256,0} /* NOTE: THIS NEEDS TO BE LAST, see whichhash() code */
};


/* ---------------- local stuff, utilities ---------------*/

#undef DEBUG
#ifdef DEBUG
#define RETURN(xXx) {fprintf(stderr,"Return %d at %s:%d\n",xXx,__FILE__,__LINE__);return(xXx);}
#else
#define RETURN(xXx) return(xXx)
#endif


/*!
 * @brief inefficiently read a file into a buffer
 * @param fname is a file name (in)
 * @param blen is the buffer length
 * @param buf is the buffer 
 * @return zero on success, non-zero for error
 *
 * Given an ni name, open a file, hash it and add the hash to
 * the URI (somewhere, details TBD)
 */
static int fname2buf(char *fname,long *blen, unsigned char **buf)
{
	if (!blen || !buf) RETURN(-1);
#ifdef DEBUG
	printf("fname= %s\n",fname);
#endif
	FILE *fp=fopen(fname,"rb");
	if (!fp) {
		RETURN(errno);
	}
	int rv=fseek(fp,0,SEEK_END);
	if (rv) {
		fclose(fp);
		RETURN(errno);
	}
	long flen=ftell(fp);
	rv=fseek(fp,0,SEEK_SET);
	if (rv) {
		fclose(fp);
		RETURN(errno);
	}
	unsigned char *lbuf=(unsigned char*)malloc((flen+1)*sizeof(char));
	if (!lbuf) {
		fclose(fp);
		RETURN(-1);
	}
	size_t read=fread(lbuf,flen,1,fp);
	if (read!=1) {
		free(lbuf);
		fclose(fp);
		RETURN(-1);
	}
	fclose(fp);
	*blen=flen;
	*buf=lbuf;
#ifdef DEBUG
	printf("flen= %ld\n",flen);
#endif
	RETURN(0);
}

/*
 * @brief base 64 encode with the base64url variant
 * @param ilen is the input length
 * @param ibuf is the input buffer
 * @param olen is the output length (in/out)
 * @param obuf is the output buffer (allocated by calle)
 * @return zero on success, non-zero for error
 *
 * This was inspired by:
 * http://www.ioncannon.net/programming/34/howto-base64-encode-with-cc-and-openssl/
 * Might need to rewrite again if that's an issue.
 */
static int b64url_enc(long ilen, const unsigned char *ibuf, long *olen, unsigned char *obuf)
{
  int i;
  BUF_MEM *bptr;
  BIO *bmem, *b64;
  b64 = BIO_new(BIO_f_base64());
  bmem = BIO_new(BIO_s_mem());
  b64 = BIO_push(b64, bmem);
  BIO_write(b64, ibuf, ilen);
  BIO_flush(b64);
  BIO_get_mem_ptr(b64, &bptr);
  char *buff = (char *)malloc(bptr->length);
  memcpy(obuf, bptr->data, bptr->length-1);
  *olen=bptr->length-1;
  obuf[bptr->length-1] = 0;
  BIO_free_all(b64);

  // ok that's probably base64 but we want base64url
  // http://en.wikipedia.org/wiki/Base64
  // (I think) that means:
  //      s/=// - nothing at the end
  //      s/+/-/  - minus rather than plus
  //      s/\//_/ - no slashes, but underscores

  // ok there's a better way but this'll do
  for (i=0;i!=(*olen);i++) {
		if (obuf[i]=='+') obuf[i]='-';
		if (obuf[i]=='/') obuf[i]='_';
  }
  // strip off an = at the end
  if (obuf[*olen-1]=='=') {
	obuf[*olen-1]='\0';
	(*olen)=(*olen)-1;
  }
  // apparently there's a corner case with == at
  // the end, so do it again just in case
  if (obuf[*olen-1]=='=') {
	obuf[*olen-1]='\0';
	(*olen)=(*olen)-1;
  }

  RETURN(0) ;
}

/*-------------- external API ---------------- */

/*!
 * @brief make an NI URI for a filename
 * @param ni is the URI (in/out)
 * @param fname is a file name (in)
 * @return zero on success, non-zero for error
 *
 * Given an ni name, open a file, hash it and add the hash to
 * the URI (somewhere, details TBD)
 */
int makenif(niname name,char *fname)
{

	long blen;
	unsigned char *buf;
	int rv=fname2buf(fname,&blen,&buf);
	if (rv) {
		RETURN(rv);
	}
	rv=makenib(name,blen,buf);
	if (rv) {
		free(buf);
		RETURN(rv);
	}
	free(buf);
	RETURN(0);

}

/*!
 * @brief check if an NI URI matches a file's content
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
int checknif(niname name, char *fname, int *res)
{

	long blen;
	unsigned char *buf;
	int rv=fname2buf(fname,&blen,&buf);
	if (rv) {
		RETURN(rv);
	}
	rv=checknib(name,blen,buf,res);
	if (rv) {
		free(buf);
		RETURN(rv);
	}
	free(buf);
	RETURN(0);
	RETURN(0);
}

/*!
 * @brief make an NI URI for a buffer
 * @param ni is the URI (in/out)
 * @param blen is the buffer length
 * @param buf is the buffer 
 * @return zero on success, non-zero for error
 *
 * Given an ni name, hash a buffer and add the hash to
 * the URI (somewhere, details TBD)
 */
int makenib(niname name,long blen, unsigned char *buf)
{

	int olen,basefnc;
	const char *hashalg=whichhash(name,&olen,&basefnc);
	if (hashalg==NULL) {
		RETURN(-1);
	}

#define MAXHASHLEN 1024 
	long hashlen=SHA256_DIGEST_LENGTH;
	unsigned char hashbuf[MAXHASHLEN];
	SHA256_CTX c;
	SHA256_Init(&c);
	SHA256_Update(&c,buf,blen);
	SHA256_Final(hashbuf,&c);

	// for now, just replace the first occurrence of <hashalg>; with <hashalg>;<value> and
	// leave the rest of the input URI alone

	// check if its a truncated hash or not
	unsigned char b64hashbuf[MAXHASHLEN];
	long b64hashlen=2*SHA256_DIGEST_LENGTH;
	hashlen=olen/8;
	int rv=b64url_enc(hashlen,hashbuf,&b64hashlen,b64hashbuf);
	if (rv) {
		RETURN(rv);
	}
#ifdef DEBUG
	printf("Hash: %s %ld\n",b64hashbuf,b64hashlen);
#endif

	long nameinlen=strlen(name);
	long hashalgnamelen=strlen(hashalg);
	char *ptr1=strstr(name,hashalg);
	if (!ptr1) {
		RETURN(-1);
	}
	long prefixlen=(ptr1-name);
	long postfixoffset=prefixlen+hashalgnamelen;
	if (name[postfixoffset]==';') {
		postfixoffset++;
		}
	niname newname;
	memset(newname,0,NILEN);
	memcpy(newname,name,prefixlen);
	memcpy(newname+strlen(newname),hashalg,hashalgnamelen+1);
	newname[strlen(newname)]=';';
	memcpy(newname+strlen(newname),b64hashbuf,b64hashlen);
	memcpy(newname+strlen(newname),name+postfixoffset,nameinlen-postfixoffset);
	memcpy(name,newname,NILEN);

	RETURN(0);
}

/*!
 * @brief check if an NI URI matches a buffer
 * @param ni is the URI (in)
 * @param blen is the buffer length
 * @param buf is the buffer 
 * @param res is the result (out, zero if good)
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
int checknib(niname name, long blen, unsigned char *buf, int *res)
{
	if (!res) RETURN(-1);
	*res=1;

	int olen,basefnc;
	const char *hashalg=whichhash(name,&olen,&basefnc);

	long hashlen=SHA256_DIGEST_LENGTH;
	unsigned char hashbuf[MAXHASHLEN];
	SHA256_CTX c;
	SHA256_Init(&c);
	SHA256_Update(&c,buf,blen);
	SHA256_Final(hashbuf,&c);
	// for now, just replace the first occurrence of sha256; with sha256;<value> and
	// leave the rest of the input URI alone
	long b64hashlen=2*SHA256_DIGEST_LENGTH;
	unsigned char b64hashbuf[MAXHASHLEN];
	hashlen=olen/8;
	int rv=b64url_enc(hashlen,hashbuf,&b64hashlen,b64hashbuf);
	if (rv) {
		RETURN(rv);
	}
#ifdef DEBUG
	printf("Hash: %s %ld\n",b64hashbuf,b64hashlen);
#endif
	char *ptr1=strstr(name,hashalg);
	if (!ptr1) {
		RETURN(-1);
	}
	ptr1+=strlen(hashalg)+1;

#ifdef DEBUG
	printf("T=%s, H=%s\n",ptr1,b64hashbuf);
#endif
	
	if (!memcmp(ptr1,b64hashbuf,b64hashlen)) *res=0;

	RETURN(0);
}


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
const char *whichhash(niname name, int *olen, int *basefnc)
{
	// find out which hash its to be. we'll go for the first one we
	// find

	if (!name || !olen || !basefnc) return (NULL); 

	const char *hashalg=NULL; // this'll point at a const char string
	int i; // counter

	for (i=0;i!=NUMHASHES;i++) {
		hashalg=strstr(name,hashalgtab[i].str);
		if (hashalg) {
			*olen=hashalgtab[i].olen; 
			*basefnc=hashalgtab[i].basefnc; 
			return(hashalgtab[i].str);
		}
	}
	return(NULL);

}

/*!
 * @brief make a .well-known URL with a hash for a filename
 * @param wku is the URL (in/out)
 * @param fname is a file name (in)
 * @return zero on success, non-zero for error
 *
 * Given a URL, open a file, hash it and add the hash to
 * a .well-known URL after the hashalg.
 * 
 * The input URL should be like: http://tcd.ie/.well-known/ni/sha-256//path?query-stuff
 * Well Known URLs are defined in RFC 5785
 */
int makewkuf(niname wku,char *fname)
{

	long blen;
	unsigned char *buf;
	int rv=fname2buf(fname,&blen,&buf);
	if (rv) {
		RETURN(rv);
	}
	rv=makewkub(wku,blen,buf);
	if (rv) {
		free(buf);
		RETURN(rv);
	}
	free(buf);
	RETURN(0);
}

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
 * The input URL should be like: http://tcd.ie/.well-known/ni/sha-256//path?query-stuff
 * Well Known URLs are defined in RFC 5785
 */
int makewkub(niname wku, long blen, unsigned char *buf)
{

	int olen,basefnc;
	const char *hashalg=whichhash(wku,&olen,&basefnc);
	if (hashalg==NULL) {
		RETURN(-1);
	}

#define MAXHASHLEN 1024 
	long hashlen=SHA256_DIGEST_LENGTH;
	unsigned char hashbuf[MAXHASHLEN];
	SHA256_CTX c;
	SHA256_Init(&c);
	SHA256_Update(&c,buf,blen);
	SHA256_Final(hashbuf,&c);

	// for now, just replace the first occurrence of <hashalg>; with <hashalg>;<value> and
	// leave the rest of the input URI alone

	// check if its a truncated hash or not
	unsigned char b64hashbuf[MAXHASHLEN];
	long b64hashlen=2*SHA256_DIGEST_LENGTH;
	if (hashalg==SHA256T32STR) {
		hashlen=2;
	} 
	int rv=b64url_enc(hashlen,hashbuf,&b64hashlen,b64hashbuf);
	if (rv) {
		RETURN(rv);
	}
#ifdef DEBUG
	printf("Hash: %s %ld\n",b64hashbuf,b64hashlen);
#endif

	long nameinlen=strlen(wku);
	long hashalgnamelen=strlen(hashalg);
	char *ptr1=strstr(wku,hashalg);
	if (!ptr1) {
		RETURN(-1);
	}
	long prefixlen=(ptr1-wku);
	long postfixoffset=prefixlen+hashalgnamelen;
	niname newname;
	memset(newname,0,NILEN);
	memcpy(newname,wku,prefixlen);
	memcpy(newname+strlen(newname),hashalg,hashalgnamelen+1);
	newname[strlen(newname)]='/';
	memcpy(newname+strlen(newname),b64hashbuf,b64hashlen);
	memcpy(newname+strlen(newname),wku+postfixoffset,nameinlen-postfixoffset);
	memcpy(wku,newname,NILEN);

	RETURN(0);
}

/*!
 * @brief map an niname to a .well-known URL
 * @param name is the URI (in)
 * @param wku is the .well-known URL (out)
 * @return zero for success, non-zero for error
 * 
 * Scan the input name for a known hash alg and return our standard form
 * of that. If we can't find one, return null.
 */
int mapnametowku(niname name, niname wku)
{
	int olen,basefnc;
	const char *hashalg=whichhash(name,&olen,&basefnc);
	if (hashalg==NULL) {
		RETURN(-1);
	}
	const char *startofni="ni://";
	if (memcmp(name,startofni,4)) {
		RETURN(-1);
	}
	size_t nlen=strlen(name);
	niname soa;
	snprintf(soa,NILEN,"%s",name+5);
	size_t alen=strcspn(soa,"/");
	soa[alen]='\0';
	niname newname;
	int hlen=strlen(hashalg);
	snprintf(newname,NILEN,"http://%s/.well-known/ni/%s/",soa,hashalg);
	snprintf(newname+strlen(newname),NILEN-strlen(newname),"%s",soa+(alen+hlen+2));
	memcpy(wku,newname,NILEN);
	
	RETURN(0);
}

/*!
 * @file 
 * ============== Lower Level Interface ==================================
 *
 * Uses OpenSSL EVP routines which allow the hash digest function to be
 * selected by name.  The routine ni_ic_initialized() is called to set up
 * the EVT_MD_CTX structure.  The routine ni_ic_set_alg() is called to
 * select the hash algorithm and record the length in bits of the hash
 * as generated (typically 256) and the truncated hash length (again in
 * bits taken from the name. Chunks of the data can then be fed to the 
 * digest function using ni_ic_update() and the digest finally calculated
 * using ni_ic_finalize().  The digest can be retrieved using 
 * ni_ic_get_digest() or checked against an existing URL digest component
 * using ni_ic_check_digest().
 */

/** @brief State flag indicating if OpenSSL EVP context is setup */
static bool ni_ic_initialized = false;

/** @brief State flag indicating if context is setup and in use */
static bool ni_ic_ready = false;

/** @brief State flag indicating if digest has been finalized and digest read out */
static bool ni_ic_finalized = false;

/** @brief OpenSSL EVP digest context state */
static EVP_MD_CTX mdctx;

/** @brief Buffer to hold generated digest - allow for base64 encoding */
static unsigned char digest_buf[2*EVP_MAX_MD_SIZE];

/** @brief Algorithm bit length */
static long alg_length = 0;

/** @brief Truncated bit length */
static long truncated_length = 0;

/** @brief Actual digest length */
static long digest_length;

/*!
 * @brief initialise hash digest mechanism of OpenSSL
 * @return zero for success, non-zero for error
 * 
 * Allows future use of selection of digest mechanism by name.
 */
int ni_ic_init()
{
	/* Check if already initialized*/
	if (ni_ic_initialized)
	{
		return -1;
	}

	/* set up to be able to select digests by name */
	OpenSSL_add_all_digests();

	/* Create the digest context - reusable provided cleared up */
	EVP_MD_CTX_init(&mdctx);
	ni_ic_initialized = true;
	ni_ic_ready = false;
	ni_ic_finalized = false;
	return 0;
}

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
int ni_ic_get_file_compt(const char *url,  char *ni_alg_name)
{
	const char *b, *e;

	assert(ni_alg_name != NULL);
	e = strpbrk(url, ";?#");
	if (e == NULL)
		{
		e = strchr(url, '\0');
		}
	b = strrchr(url, '/');
	if (b == NULL)
		{
		b = url;
		}
	else
		{
		b++;
		}
	strncpy(ni_alg_name, b, (e - b));
	ni_alg_name[e - b] = '\0';
	return (((e - b) != 0) ? 0 : 1);
}

/*!
 * @brief select the hash algorithm to use by name and initialise digest construction
 * @param name of digest algorithm to be used (in)
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
 */
int ni_ic_set_alg(const char *ni_alg_name)
{
	/* digest algorithm id in OpeenSSL EVP */
	 const EVP_MD *md;

	/* For parsing algorithm name */
	char alg_name[100];
	char temp_alg_name[100];
	char *sep1=NULL, *sep2 = NULL;
	int compt_len;
	
	/* Clear down context if it didn't get cleared up properly */
	if (ni_ic_ready)
	{
		EVP_MD_CTX_cleanup(&mdctx);
		ni_ic_ready = false;
		ni_ic_finalized = false;
	}

	/* Check out algorithm name */
	strcpy(temp_alg_name, ni_alg_name);
	if ((sep1 = strchr(temp_alg_name, '-')) == NULL)
	{
		/* Bad ni alg specifier */
		return (-1);
	}

	compt_len = sep1 - temp_alg_name;
	strncpy(alg_name, ni_alg_name, compt_len);
	alg_name[compt_len] = '\0';

	/* Could check if the name is one we want to go with */
	/* the remainder of the ni_alg_name is of the form
	 * [0-9]+(-[0-9]+)? where the first numeric field specifies
	 * the number of bits in the digest, and optionally, the second 
	 * number specifies the number of bits taken from the beginning
	 * of the full digest to be used as a truncated digest.
	 * In either case the digest bits will then be base64 encoded.
	 * The algorithm name looked up in the OpenSSL digest list consists
	 * of concatenating the combination of the piece before the firstt
	 * hyphen and the first number - typically this becomes sha256.
	 */
	sep1++; /* point after hyphen */
	compt_len = strspn(sep1, "0123456789");
	sep2 = sep1 + compt_len;
	if ((compt_len == 0) || !((*sep2 == '-') || (*sep2 =='\0')))
	{
		/* Syntax error - second component not a pure number */
		return (-2);
	}
	strncat(alg_name, sep1, compt_len);
	alg_length = atol(sep1);
	/* ought to be a multiple of 8 */
	if (alg_length & 0x7)
	{
		return (-3);
	}
	if (*sep2 != '\0')
	{
		sep2++;
		compt_len = strspn(sep2, "0123456789");
		if ((compt_len == 0) || (sep2[compt_len] != '\0'))
		{
			/* garbage on the end of the string */
			return (-4);
		}
		truncated_length = atol(sep2);
		if ((truncated_length & 0x7) || (truncated_length > alg_length))
		{
			return (-5);
		}
	}
	else
	{
		truncated_length = alg_length;
	}
	
	/* Finally we can look up the al;gorithm name */
	md = EVP_get_digestbyname(alg_name);

	if (!md)
	{
		/* Unknown message digest name */
		return(-6);
	}

	/* The DigestInit function returns 1 for success, 0 for failure
	 * where faikures are primarily memory allocation problems.
	 */
	if (!EVP_DigestInit_ex(&mdctx, md, NULL))
	{
		return (-7);
	}
	
	ni_ic_ready = true;
	
	return (0);
}

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
int ni_ic_update(unsigned char * buf, long buflen)
{
	assert(ni_ic_ready && !ni_ic_finalized);
	return ((int)((EVP_DigestUpdate(&mdctx, buf, buflen) == 1) ? 0 : 1));
}

/*!
 * @brief generate digest based on previous algorithm and buffer updates 
 * @param length of digest string (less terminating null) (out)
 * @return zero for success, 1 if called again after finalizing, other non-zero for error
 * 
 * Finalise the hash digest and create the URL-safe base64 encoding.	
 * Stores the digest internally for future comparison or retrieval.
 * Resets OpenSSL context ready for new digests.
 */
int ni_ic_finalize(long *digest_len)
{
	/* Buffer to hold binary intermediate form of digest */
	unsigned char bin_digest_buf[MAXHASHLEN];
	unsigned int bin_digest_length;

	/* Return codes */
	int rv;

	/* The return codes from EVP_DigestFinal_ex are not defined */
	/* Code inspection appears to indicate that errors are really 
	 * about memory allocation and bad parameters.
	 */
	assert(ni_ic_ready);
	if (ni_ic_finalized)
	{
		if (digest_len != NULL)
		{
			*digest_len = digest_length;
		}
		return (1);
	}
	if (EVP_DigestFinal_ex(&mdctx, bin_digest_buf, &bin_digest_length) != 1) {
		return(-2);
	}
	ni_ic_finalized = true;
	if ((long)bin_digest_length != (alg_length>>3))
	{
		return (-3);
	}

	/* Null terminate the digest */
	bin_digest_buf[bin_digest_length] ='\0';

	EVP_MD_CTX_cleanup(&mdctx);

	/* base64 encode digest */
	rv = b64url_enc((long)(truncated_length>>3), bin_digest_buf,
			&digest_length, digest_buf);
	/* Make it into a null-terminated string */
	digest_buf[digest_length] ='\0';
	if (rv != 0)
	{
		return (rv);
	}
	
	if (digest_len != NULL)
	{
		*digest_len = digest_length;
	}
	return (0);
}

/*!
 * @brief retrieve previously calculated digest
 * @param digest string (null terminated) (out)
 * @param digest string length (excluding null termination) (out)
 * @return zero for success, non-zero for error
 */
int ni_ic_get_digest(char *digest, long *digest_len)
{
	if (!ni_ic_finalized)
	{
		return(-1);
	}
	assert((digest != NULL) && (digest_len != NULL));
	memcpy(digest, digest_buf, (digest_length + 1));
	*digest_len = digest_length;
	return (0);
}

/*!
 * @brief compare digest string with previously calculated digest
 * @param digest to be compared (in)
 * @param length of digest to be compared (in)
 * @return zero if strings compare equal, non-zero otherwise.
 */
int ni_ic_check_digest(char *digest, long digest_len)
{
	if (!ni_ic_finalized)
	{
		return(-1);
	}
	assert(digest != NULL);
	if ((digest_len != digest_length) || (memcmp(digest, digest_buf, digest_length) != 0))
	{
		return (-1);
	}
	return (0);
}


