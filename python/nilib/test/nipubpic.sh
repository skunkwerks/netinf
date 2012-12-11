#!/bin/bash

# run dopubdir.py a few times to a site

TOPDIR=~/logs
NOW=`date --rfc-3339=seconds | sed -e 's/ /T/' | sed -e 's/+00:00//' | sed -e 's/:/-/g'`
WORKING=$TOPDIR/$NOW
TAG="pub2.sh:$NOW"

# publish parameters
SITE=filesys.netinf.eu
# set COUNT=0 for all
COUNT=100
# set procs >1 to use that many client processes
PROCS=1
# pick what you want, this one is BIG
DIRTOLOAD=/home/stephen/wiki

PYBIN=/home/stephen/code/netinf_code/python/nilib

# internal parameters
# the client log file
CLILOG=clilog-$NOW
GPLFILE=clipic-$NOW.gpl
CSVFILE=clipic-$NOW.csv
PICTURE=clipic-$NOW.png

# gnuplot parameters
# bytes
XMAX=250000
# milliseconds
YMAX=90

echo "$TAG,Run a NetInf publish test to $SITE"
echo "$TAG,This assume you're on the same host as the server"
echo "$TAG,if not, you'll need to use pub2c.sh"
echo "$TAG,If you wanted to start clean, you should have first"  
echo "$TAG,zapped the server" 
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

echo "$TAG,Publishing, this might be slow depending on parameters"
$PYBIN/nipubdir.py -d $DIRTOLOAD -n $SITE -c $COUNT -m $PROCS >$CLILOG 2>&1
echo "$TAG,Finished publishing: last line of log:"
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
set xrange [0:$XMAX]
set yrange [0:$YMAX]
plot '$CSVFILE'
EOF

gnuplot $GPLFILE

echo "$TAG,Done - picture is $WORKING/$PICTURE"


