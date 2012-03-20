Copyright (C) 2012 Trinity College Dublin
Contact: Elwyn Davies, davieseb@scss.tcd.ie

This directory contains patch(es) for wget that adds ni: URL rewriting
to http .well-known URL. Currently self-contained (because of way that
wget parses URLs into components) but will be using the ni library for
the post-retrieval integrity checking.

patch_wget-1.13.4_ni_retrieval_20120126  - patch for wget 1.13.4

Assumptions:

 - Just a virgin wget-1.13.4 source download.
   From http://ftp.gnu.org/gnu/wget/wget-1.13.4.tar.gz

Application of patch:
- Make root directory of wget source tree (typically xxx/wget-1.13.4) 
  your workig directory.
- Get patch file 
- run:
  patch -p1 < patch_wget-1.13.4_ni_retrieval_20120126
- This should patch src/url.c, src/url.h
- Configure and compile wget as usual:
  ./configure --with-ssl=openssl
  make
- If you want to debug with gdb 
  export CFLAGS="-g -O2 -Wall"
  before configuring. 
  ./configure --with-ssl=openssl --enable-debug


