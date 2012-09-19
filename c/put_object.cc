/*
 * 
 * put_object implementation in C
 *
 *
 * This is the put_object utility for NetInf developed as
 * part of the SAIL project. (http://sail-project.eu)
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
#include <sys/time.h>
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

#define NULLSTR(x) ( (x)==NULL? "" : (x) )


/** Initializes some library routines
 */
void init(void){
 struct timeval t;
 gettimeofday(&t,NULL);
 srandom((unsigned int)t.tv_usec);
}

/** Valid characters for MIME multipart boundary */
const char* validboundarychar="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'()+,-./:=?";

/** Generates a random string using only valid characters for a MIME
 *  multipart boundary.
 * @param buf the buffer to which the string should be written to.
 *            Can be NULL, in which case a new buffer is allocated.
 * @param len the desired length of the random string, including the terminating '\0'. 
 * @return buf, if not NULL; the newly allocated buffer otherwise.
 */
char*randomstring(char*buf,int len){
 struct timeval t;
 char*res=buf;
 int l;
 
 if(len==0)return NULL;
 if(buf==NULL) res=(char*)malloc((len+1)*sizeof(char));
 else res=buf;
 
 gettimeofday(&t,NULL);
 
 snprintf(res,len,"%x%lX%x",(short)(random()>>16),(long)t.tv_usec,(int)random());
 l=strlen(res);
 
 while(l<len-1){
  res[l++]=validboundarychar[(((unsigned)random())%73)];
 }
 res[l]='\0';
 
 return res;
}


/** Returns a copy of the authority part of a NI name.
 * @param ni the NI name
 * @return a copy of the authority part of the given NI name, or NULL in
 *         case of errors.
 */
char*getauthority(char*ni){
 char*tmp,*res;

 if(strncasecmp(ni,"ni://",5)!=0)return NULL;
 
 tmp=strchr(ni+5,'/');
 if(tmp==NULL)return NULL;
 res=strndup(ni+5,tmp-(ni+5));
 
 return res;
}


/** Sends a publish request.
 * @param next_hop the next hop. Can be NULL, in which case the next hop is
 *                 determined from the authority part of the URI.
 * @param ni_uri the NI URI to use to publish the object.
 * @param f an open FILE*, the object to publish. Can be NULL.
 * @param loc the locator of the object, in case it is not being published
 *            integrally (e.g. f is NULL).
*/
void send_request(char*next_hop,char*ni_uri,FILE*f,char*loc){
  struct addrinfo * addresses=NULL;
  struct addrinfo * addrptr; 
  int ffd,tmp,size;
  char postbuf[BUFSIZE];
  char formbuf1[BUFSIZE];
  char formbuf2[BUFSIZE];
  unsigned char*mybuf;
  int blen=0,content_length=0;
  char buf[BUFSIZE]; /* used for debugging purposes */
  char*separator=NULL,*filebuf=NULL;
  long filesize;
  char*port;
  char fixed80[3]={'8','0',0};

  postbuf[0]='\0';
  if(next_hop==NULL)next_hop=getauthority(ni_uri);
  if(next_hop==NULL)return;
  
  port=strchr(next_hop,':');
  if(port==NULL) port=fixed80;
  else *port++='\0';
  fprintf(stderr,"attempting connection to %s:%s.\n",next_hop,port);
  /* SET UP THE SOCKET */
  tmp=getaddrinfo(next_hop,port,NULL,&addresses);
  if(tmp!=0){
    fprintf(stderr,"ERROR during name resolution: %s at %s:%d\n",
                                               gai_strerror(tmp),__FILE__,__LINE__);
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
      fprintf(stderr,"attempting inet6 connection to [%s]:%d (addrlen:%d), %s\n",
        buf,
        (int)ntohs(((struct sockaddr_in6*)(addrptr->ai_addr))->sin6_port),
        addrptr->ai_addrlen, addrptr->ai_canonname
        );
     break;
     default:
      fprintf(stderr,"Address family %d!!\n",addrptr->ai_family);
   }
   
   ffd=socket(addrptr->ai_family,SOCK_STREAM,addrptr->ai_protocol);
   if(ffd<0){
    perror("Error during initialization of socket");
    continue;
   }
 
   if(0==(tmp=connect(ffd,addrptr->ai_addr,addrptr->ai_addrlen)))
    break;
   else{
    perror("Error during connection");
    close(ffd);
   }
  }
 if(tmp!=0)exit(2);
 

 if(f!=NULL){ /* TODO: proper error checking here! */
  fseek(f, 0L, SEEK_END);
  filesize = ftell(f);
  fseek(f, 0L, SEEK_SET);
  filebuf=(char*)malloc(filesize);
  fread(filebuf,1,filesize,f);
 }else filesize=0;
 
 /* PREPARE THE ACTUAL REQUEST AND SEND IT */
 separator=randomstring(NULL,42);
 snprintf(formbuf1,BUFSIZE-1,"\r\n--%s\r\n"
   "Content-Disposition: form-data; name=\"URI\"\r\n\r\n%s"
   "\r\n--%s\r\n"
   "Content-Disposition: form-data; name=\"msgid\"\r\n\r\n%s"
   "\r\n--%s\r\n"
   "Content-Disposition: form-data; name=\"ext\"\r\n\r\n%s"
   "\r\n--%s\r\n"
   "Content-Disposition: form-data; name=\"octets\"\r\nContent-Type: application/octet-stream\r\nContent-Transfer-Encoding: binary\r\n\r\n"
   ,separator,ni_uri,separator,"msgid_foo",separator,"ext_bar",separator);

 snprintf(formbuf2,BUFSIZE-1,"\r\n--%s\r\n"
   "Content-Disposition: form-data; name=\"loc1\"\r\n\r\n%s"
   "\r\n--%s\r\n"
   "Content-Disposition: form-data; name=\"loc2\"\r\n\r\n%s"
   "\r\n--%s\r\n"
   "%s" // full put?
   "%s%s" //full put?
   "Content-Disposition: form-data; name=\"submit\"\r\n\r\n%s"
   "\r\n--%s--\r\n",
   separator,NULLSTR(loc),separator,"",separator,
   f==NULL?"":"Content-Disposition: form-data; name=\"fullPut\"\r\n\r\n\r\n--",
   f==NULL?"":separator,f==NULL?"":"\r\n",
   "Submit",separator);
 
 content_length=strlen(formbuf1)+strlen(formbuf2)+filesize;
 
 snprintf(postbuf,BUFSIZE-1,"POST /.well-known/netinfproto/publish HTTP/1.1\r\nHost: %s\r\nConnection: close\r\nContent-Type: multipart/form-data; boundary=%s\r\nContent-Length: %d\r\n\r\n",next_hop,separator,content_length);
 blen=strlen(postbuf);
 
 fprintf(stderr,"%s%s%s%s\n\n",postbuf,formbuf1,f==NULL?"":"<ACTUAL FILE DATA HERE>",formbuf2);

 write(ffd,postbuf,blen);
 write(ffd,formbuf1,strlen(formbuf1));
 if(f!=NULL)write(ffd,filebuf,filesize);
 write(ffd,formbuf2,strlen(formbuf2));
 free(filebuf);
 
 /* NOW GET BACK THE OBJECT WITH HEADERS */
 
 mybuf=(unsigned char*)malloc(BUFSIZE*sizeof(char));
 size=0;
 
 while((blen=read(ffd,mybuf+size,BUFSIZE))!=0){
  if(blen<0)goto errorhandling;
  
  //fwrite(mybuf+size,blen,1,stdout);
  size+=blen;
  mybuf=(unsigned char*)realloc(mybuf,size+BUFSIZE);
 }
 
 mybuf[size]='\0';
 
 printf("REPLY:\n%s\n",mybuf);
 
 close(ffd);
 return;
 
errorhandling:
 return; 
}


/** main. Usage: [next_hop] ni_uri filename
 * any additional parameters are ignored.
 */
int main(int argc, char*argv[]){
 char*next_hop,*ni_uri,*filename,*loc=NULL;
 FILE*f;

 init();
  
 if(argc<3){
  fprintf(stderr,"ERROR! usage:\n  %s [<next_hop>] <ni_uri> <filename or locator>\n",argv[0]);
  return 2;
 }
 
 if(argc>3){
  next_hop=argv[1];
  ni_uri=argv[2];
  filename=argv[3];
 }else{
  next_hop=NULL;
  ni_uri=argv[1];
  filename=argv[2];
 }
  
 f=fopen(filename,"rb");
 if(f==NULL)loc=filename;
 send_request(next_hop,ni_uri,f,loc);
 
 return 0;
}
 
