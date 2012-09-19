Copyright (C) 2012 SICS, Swedish Institute of Computer Science AB
Contact: Bengt Ahlgren, bengta@sics.se

This directory contains patch(es) for curl that adds ni: URL rewriting
to http .well-known URL using the ni library.

curl-7.21.3-ni-rewrite-patch - patch for curl 7.21.3

Assumptions:

- the two nilib files ni.cc and ni.h are linked or copied to curl's
  lib directory

- ni.cc is renamed to ni.c
