/*
 * 
 * send_request and NI URI implementation in C
 *
 *
 * This is the NI URI library developed as
 * part of the SAIL project. (http://sail-project.eu)
 *
 * Specification(s) - note, versions may change::
 * * http://tools.ietf.org/html/farrell-decade-ni-00
 * * http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00
 *
 * Author:: Claudio Imbrenda <Claudio.Imbrenda@neclab.eu>
 * Copyright:: Copyright © 2012 Claudio Imbrenda <Claudio.Imbrenda@neclab.eu>
 * Specification:: http://tools.ietf.org/html/draft-farrell-decade-ni-00
 *
 * License:: http://www.apache.org/licenses/LICENSE-2.0.html
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
**/
#include <stdlib.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <unistd.h>
#include <string.h>
#include <strings.h>
#include <netdb.h>
#include <arpa/inet.h>
#include "ni.h"

// size of buffers... increase in case of problems (shouldn't be needed)
#define BUFSIZE 8192

/**
 Struct representing a key=value parameter of the URI
 */
struct parameter{
 /** The key */
 char*key; 
 /** The value */
 char*value;
 /** The next parameter */
 struct parameter*next;
};

/**
 Struct representing a NI URI
 */
struct ni_name{
 /** The full plain name of the object */
 char*full_name;
 /** The authority part */
 char*authority;
 /** The name of the hash function */
 char*hash_function;
 /** The value of the hash, calculated with the specified hash function */
 char*hash_string;
 /** List of additional parameters to the URI */
 struct parameter*options;
};


/** Properly allocates and initializes a struct ni_name
 * @return a newly allocated struct ni_name
 */
struct ni_name*new_ni_name(){
 struct ni_name*res=(struct ni_name*)malloc(sizeof(struct ni_name));
 
 res->full_name=res->authority=res->hash_function=res->hash_string=NULL;
 res->options=NULL;

 return res;
}

/** Correctly frees a struct ni_name
 * @param res the object to be freed
 * @return NULL
 */
void* free_ni_name(struct ni_name*res){
 struct parameter*p,*q;
 free(res->authority);
 free(res->hash_function);
 free(res->hash_string);
 free(res->full_name);
 
 p=res->options;
 while(p!=NULL){
  q=p->next;
  free(p->key);
  free(p->value);
  free(p);
  p=q;
 }

 free(res);
 return NULL;
}


/**Parses a parameter from a string in key=value format. 
 * @param s the string to parse. WILL BE OVERWRITTEN AND MANGLED.
 * @return a new struct parameter representing the parsed parameter
 */
struct parameter*parse_tagval(char*s){
 struct parameter*res;
 char*q=strchr(s,'=');
 
 if((q==NULL)||(q==s))return NULL;
 *q++='\0';
 res=(struct parameter*)malloc(sizeof(struct parameter));
 res->next=NULL;
 res->key=strdup(s);
 res->value=strdup(q);
 
 return res;
}


/**Parses a NI name.
 * @param n the string to parse
 * @return a struct ni_name representing the parsed name
 */
struct ni_name*parse_ni(const char*n){
 struct ni_name*res=new_ni_name();
 char*name_orig = strdup(n);
 char*tmp,*tmp2;

 tmp=name_orig; 
 
 if(strncasecmp(tmp,"ni://",5)!=0)goto errorhandling;

 tmp+=5; 
 tmp2=strchr(tmp,'/');
 if(tmp2==NULL)goto errorhandling;
 *tmp2='\0';
 
 if(tmp!=tmp2)res->authority=strdup(tmp);

 tmp=tmp2+1;
 tmp2=strchr(tmp,';');
 if(tmp2==NULL)goto errorhandling;
 *tmp2='\0';
 
 if(tmp==tmp2)goto errorhandling;
 else res->hash_function=strdup(tmp);
 
 tmp=tmp2+1;
 tmp2=strchr(tmp,'?');
 if(tmp2!=NULL)*tmp2='\0';
 res->hash_string=strdup(tmp);
 
 if(tmp2!=NULL){
  struct parameter*p;
  
  do{
   tmp=tmp2+1;
   tmp2=strchr(tmp,'&');
   if(tmp2!=NULL)*tmp2='\0';
   
   p=parse_tagval(tmp);
   
   if(p!=NULL){
    p->next=res->options;
    res->options=p;
   }
  }while(tmp2!=NULL);
 }
 
 free(name_orig);
 res->full_name=strdup(n);
 return res;
 
errorhandling:
 free(name_orig);
 free_ni_name(res);
 return NULL;
}



/** Copies a string to a destination buffer, performing percent-encoding
 * of most characters.
 * @param dest the destination buffer. WARNING: it must be long enough to hold the result.
 * @param src the source buffer. 
 */
void strpercentcpy(char* dest, char*src){
 char buf[4];
 
 do{
  switch(*src){
   case ' ':
    *dest++='+';
    break;
   case '"':
   case '%':
   case '-':
   case '.':
   case '<':
   case '>':
   case '\\':
   case '^':
   case '`':
   case '{':
   case '|':
   case '}':
   case '~':
    *dest++='%';
    snprintf(buf,4,"%02X",(int)*src);
    *dest++=buf[0];
    *dest++=buf[1];
    break;
   default:
    *dest++=*src;
    break;
  }
 }while(*src++);
}


/** Sends a request for an object.
 * @param next_hop the next hop to which the request should be sent to.
 *                 can be NULL, in which case the next hop will be
 *                 determined by the authority part in the name.
 * @param ni_uri the parsed name of the object to fetch.
 */
void send_request(char*next_hop,struct ni_name*ni_uri){
  struct addrinfo * addresses=NULL;
  struct addrinfo * addrptr; 
  int ffd,tmp,size,res,offset;
  char postbuf[BUFSIZE];
  char formbuf[BUFSIZE];
  unsigned char*mybuf,*objectstart;
  int blen=0,content_length=0;
  char buf[BUFSIZE]; /* used for debugging purposes */

  postbuf[0]='\0';
  if(next_hop==NULL)next_hop=ni_uri->authority;
  if(next_hop==NULL){
   
  }
  
  
  /* SET UP THE SOCKET */
  tmp=getaddrinfo(next_hop,"80",NULL,&addresses);
  if(tmp!=0){
    fprintf(stderr,"ERROR during name resolution: %s at %s:%d\n",
                                               gai_strerror(tmp),__FILE__,__LINE__);
    exit(2);
  }
  
  ffd=socket(addresses->ai_family,SOCK_STREAM,addresses->ai_protocol);
  if(ffd<0){
    fprintf(stderr,"Error during initialization of socket");
      exit(2);
  }
  
  for(addrptr=addresses;addrptr!=NULL;addrptr=addrptr->ai_next){
   switch(addrptr->ai_family){
     case AF_INET:
      fprintf(stderr,"attempting inet connection to %s:%d (addrlen:%d), %s\n",
        inet_ntoa(((struct sockaddr_in*)(addrptr->ai_addr))->sin_addr),   
        (int)ntohs(((struct sockaddr_in*)(addrptr->ai_addr))->sin_port),  
        addrptr->ai_addrlen, addrptr->ai_canonname
        );
     break;
     case AF_INET6:
      inet_ntop(AF_INET6,
          &((struct sockaddr_in6*)&(addrptr->ai_addr))->sin6_addr,
          buf, sizeof(buf)
          );
      fprintf(stderr,"attempting inet6 connection to %s:%d (addrlen:%d), %s\n",
        buf,
        (int)ntohs(((struct sockaddr_in6*)(addrptr->ai_addr))->sin6_port),
        addrptr->ai_addrlen, addrptr->ai_canonname
        );
     break;
     default:
      fprintf(stderr,"Address family %d!!\n",addrptr->ai_family);
   }
    
   if(0==(tmp=connect(ffd,addresses->ai_addr,addresses->ai_addrlen)))
    break;
   else   
    perror("Error during connection");
  }
 if(tmp!=0)exit(2);
 

 
 /* PREPARE THE ACTUAL REQUEST AND SEND IT */
 formbuf[0]='\0';
 strcat(formbuf,"URI=");
 strpercentcpy(formbuf+4,ni_uri->full_name);
 strcat(formbuf,"&msgid=foobar&ext=anything");
 content_length=strlen(formbuf);
 
 snprintf(postbuf,BUFSIZE-1,"POST /.well-known/netinfproto HTTP/1.1\r\nHost: %s\r\nConnection: close\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\n\r\n",next_hop,content_length);
 blen=strlen(postbuf); 
 
 fprintf(stderr,"%s%s\n\n",postbuf,formbuf);
 write(ffd,postbuf,blen);
 write(ffd,formbuf,content_length);
 
 
 /* NOW GET BACK THE OBJECT WITH HEADERS */
 
 mybuf=(unsigned char*)malloc(BUFSIZE*sizeof(char));
 size=0;
 
 while((blen=read(ffd,mybuf+size,BUFSIZE))!=0){
  if(blen<0)goto errorhandling;
  
  fwrite(mybuf+size,blen,1,stdout);
  size+=blen;
  mybuf=(unsigned char*)realloc(mybuf,size+BUFSIZE);
 }
 
 close(ffd);
 
 objectstart=mybuf;
 /* FIND THE HEADERS AND SKIP THEM */
 for(offset=0;offset<size-4;offset++){
  if(strncmp((const char*)mybuf+offset,"\n\n",2)==0){
   offset+=2;
   objectstart=mybuf+offset;
   break;
  }else if(strncmp((const char*)mybuf+offset,"\r\n\r\n",4)==0){
   offset+=4;
   objectstart=mybuf+offset;
   break;
  }
 }

// intentionally mangle the content to test the hash verification
// for(tmp=0;tmp<size/2;tmp++)mybuf[2*tmp]=' ';
 
 /* CHECK THE HASH */
 
 fprintf(stderr,"checking this: size=%d, content=%s\n",size-offset,objectstart);
 if(0==checknib(ni_uri->full_name,size-offset,objectstart,&res)){
  if(res==0)fprintf(stderr,"Object matches name!\n");
  else fprintf(stderr,"ERROR!!!11! Object does NOT match the name!!1!!!1!one1!\n");
 }else{
  fprintf(stderr,"checking function failed!\n");
  goto errorhandling;
 }
 
 return;
 
errorhandling:
 return; 
}



/** main. If only 1 parameter is present, it is assumed to be the the NI URI.
 * Otherwise the first parameter is considered for the next hop, the second
 * is used as URI and any additional parameters are ignored.
 * 
 */
int main(int argc, char*argv[]){
 char*next_hop;
 struct ni_name*ni_uri;
 
 if(argc<2){
  fprintf(stderr,"ERROR! usage:\n  %s [<next_hop>] <ni_uri>\n",argv[0]);
  return 2;
 }
 
 if(argc>2){
  next_hop=argv[1];
  ni_uri=parse_ni(argv[2]);
 }else{
  next_hop=NULL;
  ni_uri=parse_ni(argv[1]);
 }
 
 if(ni_uri==NULL){
  fprintf(stderr,"Error parsing the NI URI.\n");
  return 2;
 }
 
 send_request(next_hop,ni_uri);
 
 return 0;
}
 
