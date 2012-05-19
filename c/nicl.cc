/*!
 * @file nicl.cc
 * @brief basic command line client for NI names, make 'em and check 'em
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
#include <stdbool.h>
#include <getopt.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include "ni.h"

static void usage(int line, int argc, char *argv[])
{
	fprintf(stderr,"%s: [-g|-w|-v] -n <name> -f <file>\n",argv[0]);
	fprintf(stderr,"\twhere:\n");
	fprintf(stderr,"\t\tg: means generate a hash based on the file, and put it in the name after the hashalg string\n");
	fprintf(stderr,"\t\tw: means generate a hash based on the file, and put it in the .well_known URL after the hashalg string\n");
	fprintf(stderr,"\t\tv: means verify a hash based on the name and file\n");
	fprintf(stderr,"\tname here can be an ni: or nih: scheme URI\n");
	fprintf(stderr,"%s: -m -n <name> maps from an ni name to a .well-known URL\n",argv[0]);
	exit(-1);
}

main(int argc, char *argv[])
{

	// getopt stuff
    extern char *optarg;/* used by getopt */
    extern int optind, opterr, optopt;
    int c;

	// generate or verify
	bool gen=true;
	bool gotfile=false;
	bool gotname=false;
	bool wku=false; // well-known URL
	bool map=false; 

#define MAXFILE 1024
	niname x;
	char file[MAXFILE];
	int rv;
	int res;

	memset(x,0,NILEN);
	memset(file,0,MAXFILE);

	if (!(argc==6 || argc==4)) usage(__LINE__,argc,argv);
	while ((c=getopt(argc,argv,"gf:hmn:vw?"))!=EOF) {
		switch (c) {
			case 'g': 
					gen=true; 
					break;
			case 'm':
					map=true;
					break;
			case 'w': 
					wku=true; 
					gen=true;
					break;
			case 'v': 
					gen=false; 
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
	
	if (map && gotname) {
		niname y;
		rv=mapnametowku(x,y);
		if (rv) {
			printf("oops - failed to map %s\n",x);
		} else {
			printf("%s\n",y);
		}
		exit(rv);
	}

	if (!gotname || !gotfile) usage(__LINE__,argc,argv);

	// printf("\tHello NI world\n");
	
	if (gen) {
		// printf("\tfile(in): %s\n",file);
		// printf("\tname(in): %s\n",x);
		if (wku) {
			rv=makewkuf(x,file);
		} else {
			rv=makenif(x,file);
		}
		if (rv) {
			// printf("\tError: %d, at %s: %d\n",rv,__FILE__,__LINE__);
			exit(-1);
		}
		// printf("\tname(out): %s\n",x);
		printf("%s\n",x);
	} else {
		// printf("\tfile(in): %s\n",file);
		// printf("\tname(in): %s\n",x);
		rv=checknif(x,file,&res);
		if (rv) {
			printf("\tError: %d, at %s: %d\n",rv,__FILE__,__LINE__);
			exit(-1);
		} else {
			printf("%s\n",(res==0?"good":"bad"));
		}
	}
	exit(0);
}


