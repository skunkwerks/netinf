#!/bin/bash

# run nigetlist.py and make a picture

TOPDIR=~/logs
NOW=`date --rfc-3339=seconds | sed -e 's/ /T/' | sed -e 's/+00:00//' | sed -e 's/:/-/g'`
WORKING=$TOPDIR/$NOW
TAG="nigetl.sh:$NOW"

# get parameters
# list of ni URIs to get
LIST=$TOPDIR/list
# SITE will be used for ni URIs that have no authority
SITE=php.netinf.eu
# set COUNT=0 for all
COUNT=100
# set procs >1 to use that many client processes
PROCS=1
# if you don't want to keep things
DIRTOSTORE=""
# pick where you want to keep things, if you do
#DIRTOSTORE=/home/stephen/wiki

PYBIN=/home/stephen/code/netinf_code/python/nilib

# internal parameters
# the client log file
CLILOG=getllog-$NOW
GPLFILE=getlpic-$NOW.gpl
CSVFILE=getlpic-$NOW.csv
PICTURE=getlpic-$NOW.png

# gnuplot parameters
# bytes
XMAX=250000
# milliseconds
YMAX=90000

echo "$TAG,Run a NetInf GET list test to $SITE"
echo "$TAG,"
echo "$TAG,Logs etc are in $WORKING"

rm -rf $WORKING
mkdir $WORKING
if [ ! -d $WORKING ]
then
	echo "Can't make $WORKING exiting"
	exit 1
fi

cd $WORKING

echo "$TAG,Fetching, this might be slow depending on parameters"

if [ "$DIRTOSTORE" == "" ]
then
	DOPT=""
else
	DOPT="-d $DIRTOSTORE"
fi

$PYBIN/nigetlist.py -l $LIST $DOPT -n $SITE -c $COUNT -m $PROCS >$CLILOG 2>&1
echo "$TAG,Finished Fetching: last line of log:"
LOGLAST=`tail -1 $CLILOG`
echo "$TAG,$LOGLAST"

echo "$TAG,Generatiing CSV for gnuplot with size,duration"

grep "rx fine" $CLILOG | awk -F, '{print $10","$12}' >$CSVFILE

echo "$TAG,Generating Client Picture"

cat >$GPLFILE <<EOF
# gnuplot for NetInf publish test $TAG
set datafile separator ","
set terminal png nocrop enhanced size 1024,768
set output '$PICTURE'
# set xrange [0:$XMAX]
# set yrange [0:$YMAX]
plot '$CSVFILE'
EOF

gnuplot $GPLFILE

echo "$TAG,Done - picture is $WORKING/$PICTURE"


