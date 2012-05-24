#!/bin/bash

# set -x

# This script will crawl an Apache DocRoot and for each 
# file found, will generate an ni name, report on that
# and generate a .well-known URL for which it will 
# create a sym link pointing at the original file.

# TBD - guess the MIME type of the file and also create
# a sym link with the c= query string element

# You need to run this with relevant permissions, 
# e.g. as root or as www-user

LINKEM=/home/stephen/code/nilib/sh/linkem
DocRoot=/home/stephen/code/statichtml
# bit of a hack here, nicl -w with the prefix below gives us
# what we need so go with it
Prefix=sha-256

# ancilliary variables
WKD=$DocRoot/.well-known
NID=$WKD/ni
TNID=/tmp/ni

# a clean, temporary place for stuff, it'll move to $NID at the end
if [ ! -d $TNID ]
then
	echo "Making $TNID"
	mkdir $TNID
else
	rm -rf $TNID/*
fi
if [ ! -d $TNID/$Prefix ]
then
	# need a prefix/hash specific dir too
	mkdir $TNID/$Prefix
fi

# now trawl and do stuff
# omit .hg from the find
find $DocRoot -path $DocRoot/.hg -prune -o -type f -exec $LINKEM {} $Prefix $TNID \;

# Is there a .well-known directory to start with?
# If not make it.
if [ ! -d $WKD ]
then
	echo "Making $WKD"
	mkdir $WKD
fi
if [ -d $NID ]
then
	rm -rf $NID
fi
mv $TNID $NID

