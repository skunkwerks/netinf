/*!
 * @file test.cc
 * @brief This is a bit of test code
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
#include <getopt.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include "ni.h"

static void usage(int line, int argc, char *argv[])
{
	fprintf(stderr,"%s: [-g|-v|-l] -n <name> -f <file>\n",argv[0]);
	fprintf(stderr,"\twhere:\n");
	fprintf(stderr,"\t\tg: means generate a hash based on the file, and put it in the name after the hasalg string\n");
	fprintf(stderr,"\t\tv: means verify a hash based on the name and file\n");
	fprintf(stderr,"\t\tl: means test the low level loop routines based on the name and file\n");
	fprintf(stderr,"from %d\n",line);
	exit(-1);
}

static void doSomeMime(void)
{
	
	const char *fname="../samples/foo";

	// read foo, create a multipart mixed, add an application/json with 
	// some meta-data (creationTime, and ni-name)
	// spit that out to bar
	
}

/* 'Illegal' hash algoritm specifiers for testing ni_ic_set_alg */
typedef struct hashtest { const char *alg_name; const char*err_str; } hashtest_t;
static const hashtest_t bad_alg_names[] = {
	{ "",			"Empty string"},
	{ "nohyphen",		"No hyphen and no numbers" },
	{ "1234-numbers",	"Numbers before hyphen" },
	{ "sha256",		"Missing hyphen" },
	{ "sha-3ab",		"Not a number after hyphen" },
	{ "sha-a3;",		"Not a number after hyphen" },
	{ "sha-3456-",		"Empty second number" },
	{ "sha-1234-a",		"Not a number after second hyphen" },
	{ "sha-1234-1t6",	"Not a number after second hyphen" },
	{ "sha-7890-345a",	"Character after second number" },
	{ "sha-432-763-",	"Too many hyphens" },
	{ "sha-2741-678-12",	"Too many components" },
	{ "sha-35",		"First number not a multiple of 8" },
	{ "sha-258",		"First number not a multiple of 8" },
	{ "sha-256-75",		"Second number not a multiple of 8" },
	{ "sha-256-264",	"Second number bigger then first" },
	{ NULL,			NULL }
};

main(int argc, char *argv[])
{

	// getopt stuff
    extern char *optarg;/* used by getopt */
    extern int optind, opterr, optopt;
    int c;

	// generate or verify
	bool gen=true;
	bool low=false;
	bool gotfile=false;
	bool gotname=false;

#define MAXFILE 1024
	niname x;
	char file[MAXFILE];
	int rv;
	int res;

	FILE *f;
	const char *r;
	char hashalg[100];
	const hashtest_t *ht;
	unsigned char rb[MAXFILE];
	size_t g_in, g_out, g_total = 0;
	long digest_len;

	memset(x,0,NILEN);
	memset(file,0,MAXFILE);

	if (argc!=6) usage(__LINE__,argc,argv);
	while ((c=getopt(argc,argv,"gf:hn:vl?"))!=EOF) {
		switch (c) {
			case 'g': 
					gen=true; 
					break;
			case 'v': 
					gen=false; 
					break;
			case 'l':
					low=true;
					break;
			case 'n': 
					gotname=true;
					snprintf(x,NILEN,"%s",optarg); 
					break; 
			case 'f': 
					gotfile=true;
					snprintf(file,MAXFILE,"%s",optarg); 
					break; 
			case 'h':
	 		case '?':
			default:
				usage(__LINE__,argc,argv);
		}
	}

	if (!gotname || !gotfile) usage(__LINE__,argc,argv);

	// printf("\tHello NI world\n");
	
	if (low) {
		printf("\t====== TESTING LOWER LEVEL ROUTINES ======\n\n");
		printf("\tfile(in): %s\n",file);
		printf("\tname(in): %s\n",x);
		rv = ni_ic_get_file_compt(x, hashalg);
		if (rv!=0) {
			printf("\tError: URL %s does not appear to have a file component.\n", x);
			exit(-1);
		}
		printf("\tUsing hash algorithm identifier: %s\n", hashalg);
		if ((f = fopen(file, "rb")) == NULL) {
			printf("\tUnable to open file: %s\n", strerror(errno));
			usage(__LINE__,argc,argv);
			exit(-1);
			}

		printf("\tStarting low level tests - ni_ic_init\n");
		r = "ni_ic_init";
		rv = ni_ic_init();
		if (rv != 0) {
			printf("\tError in %s: %d, at %s: %d\n", r, rv, __FILE__, __LINE__);
			exit(-1);
			}
		printf("\tRetrying ni_ic_init - should return -1\n");
		rv = ni_ic_init();
		if (rv != -1) {
			printf("\tError in %s: %d, at %s: %d\n", r, rv, __FILE__, __LINE__);
			exit(-1);
			}
/* int ni_ic_set_alg(char *ni_alg_name) */
		/* Check that ni_ic_set_alg rejects silly hash algorithm names */
		printf("\tCheck parsing of proposed algrithm names detects errors as expected..\n");
		for (ht = bad_alg_names; ht->alg_name != NULL; ht++) {
			rv = ni_ic_set_alg(ht->alg_name);
			if (rv == 0) {
				printf("\tError: %s accepted as alg name in appropriately.\n", ht->alg_name);
				printf("\t       Should have been rejected: %s\n", ht->err_str);
				} 
			else if ((rv==(-6)) || (rv==(-7))) {
				printf("\tError: %s not detected as bad alg name but rejected by OpenSSL.\n", ht->alg_name);
				printf("\t       Should have been rejected: %s\n", ht->err_str);
				}
			else {
				printf("\tBad alg name %s rejected correctly - error code %d\n", ht->alg_name, rv);
				printf("\t       Rejected because: %s\n", ht->err_str);
				}		
			}
		printf("\tCheck OpenSSL detects correctly formed but unknown alg name...\n");
		rv = ni_ic_set_alg("sha-16");
		if (rv != (-6)) {
			printf("\tError: OpenSSL failed to reject alg name 'sha-16'. Returned: %d\n", rv); 
			}
		else {
			printf("\tIn ni_ic_set_alg  - OpenSSL correctly rejected alg name 'sha-16'\n");
			}
		printf("\tSelecting algorithm from supplied name (%s) in ni_ic_set_alg...\n", hashalg);
		rv = ni_ic_set_alg(hashalg);
		if (rv != 0) {
			printf("\tError: Unable to select hash algorithm '%s', returned %d\n", hashalg, rv);
			exit(-1);
			}
		printf("\tSelection succeeded - feeding file to digest algorithm...\n");
		printf("\tRead 10 octets from file and call ni_ic_update...\n");
		g_in = 10;
		g_out = fread(rb, sizeof(*rb), g_in, f);
		if ((g_out < g_in) && !feof(f)) {
			printf("\tError: Reading file - error %s\n", strerror(errno));
			exit(-1);
		}
		rv = ni_ic_update(rb, (long)g_out);
		if (rv != 0) {
			printf("\tError: ni_ic_update failed digesting %ld octets. Returned %d\n", g_out, rv);
			exit(-1);
			}
		g_total += g_out;
		g_in = MAXFILE;
		printf("\tSucceeded... loop reading %ld octet chunks and feeding to ni_ic_update until end of file.\n", g_in);
		printf("\tProcessing chunks: ");
		while (!feof(f)) {
			g_out = fread(rb, sizeof(*rb), g_in, f);
			if ((g_out < g_in) && !feof(f)) {
				printf("\n\tError: Reading file - error %s\n", strerror(errno));
				exit(-1);
			}
			if (g_out > 0) {
				rv = ni_ic_update(rb, (long)g_out);
				if (rv != 0) {
					printf("\n\tError: ni_ic_update failed digesting %ld octets. Returned %d\n", g_out, rv);
					exit(-1);
					}
				}
			g_total += g_out;
			printf(".");
			}
		printf("\n\tAll file (%ld octets) successfully digested.\n", (long)g_total);
		printf("\tCheck that ni_ic_get_digest returns an error because digest not finalized...\n");
		rv = ni_ic_get_digest(x, &digest_len);
		if (rv == 0) {
			printf("\tError: ni_ic_get_digest succeeded before digest finalized.\n");
			exit(-1);
			}
		printf("\tOK..Check that ni_ic_check_digest returns an error because digest not finalized...\n");
		rv = ni_ic_check_digest(x, 0);
		if (rv == 0) {
			printf("\tError: ni_ic_check_digest succeeded before digest finalized.\n");
			exit(-1);
			}
		printf("\tOK.. returned expected error\n");
		printf("\tFinalize digest and examine length...\n");
		rv = ni_ic_finalize((long *)&g_in);
		if (rv != 0) {
			printf("\tError: ni_ic_finalize failed - returned %d\n", rv);
			exit(-1);
			}
		printf("\tSucceeded - digest length is %ld\n", (long)g_in);
		printf("\tCheck result of calling ni_ic_finalize again...\n");
		rv = ni_ic_finalize((long *)&g_out);
		if (rv != 1) {
			printf("\tError: ni_ic_finalize failed - returned %d\n", rv);
			exit(-1);
			}
		if (g_in != g_out) {
			printf("\tError: Recalling ni_ic_finalize generated a different digest length %ld.", g_out);
			exit(-1);
			}
		printf("\tSuccess.. same digest length returned\n");
		printf("\tCheck result of calling ni_ic_finalize again with NULL length pointer...\n");
		rv = ni_ic_finalize((long *)NULL);
		if (rv != 1) {
			printf("\tError: ni_ic_finalize failed - returned %d\n", rv);
			exit(-1);
			}
		printf("\tSuccess.. no problem with NULL pointer\n");
		printf("\tRetrieve calculated digest with ni_ic_get_digest..\n");
		rv = ni_ic_get_digest(x, &digest_len);
		if (rv != 0) {
			printf("\tError: ni_ic_get_digest failed unexpectedly.\n");
			exit(-1);
			}
		printf("\tRetrieved digest is '%s' (length %ld)\n", x, digest_len);
		printf("\tChecking retrieved digest compares correctly with stored value..\n");
		rv = ni_ic_check_digest(x, digest_len);
		if (rv != 0) {
			printf("\tError: ni_ic_check_digest failed unexpectedly.\n");
			exit(-1);
			}
		printf("\tTests completed.\n");
		}
	else if (gen) {
		printf("\tfile(in): %s\n",file);
		printf("\tname(in): %s\n",x);
		rv=makenif(x,file);
		if (rv) {
			printf("\tError: %d, at %s: %d\n",rv,__FILE__,__LINE__);
			exit(-1);
		}
		printf("\tname(out): %s\n",x);
	} else {
		printf("\tfile(in): %s\n",file);
		printf("\tname(in): %s\n",x);
		rv=checknif(x,file,&res);
		if (rv) {
			printf("\tError: %d, at %s: %d\n",rv,__FILE__,__LINE__);
		} else {
			printf("\tres: %s\n",(res==0?"good":"bad"));
		}
	}
	exit(0);
}


