#!/bin/bash

# run wget on .well-known/ni URLs and make a pretty picture

TOPDIR=~/logs
NOW=`date --rfc-3339=seconds | sed -e 's/ /T/' | sed -e 's/+00:00//' | sed -e 's/:/-/g'`
WORKING=$TOPDIR/$NOW
TAG="wkugetl:$NOW"

# get parameters
# list of ni URIs to get
LIST=$TOPDIR/list
# SITE will be used for ni URIs that have no authority
SITE=filesys.netinf.eu
# set COUNT=0 for all
COUNT=0
# set procs >1 to use that many client processes
PROCS=1
# if you don't want to keep things
DIRTOSTORE=""
# pick where you want to keep things, if you do
#DIRTOSTORE=/home/stephen/wiki

# internal parameters
# the client log file
CLILOG=wkullog-$NOW
GPLFILE=wkulpic-$NOW.gpl
CSVFILE=wkulpic-$NOW.csv
PICTURE=wkulpic-$NOW.png

# gnuplot parameters
# bytes
XMAX=250000
# milliseconds
YMAX=90000

PYBIN=/home/stephen/code/netinf_code/python/nilib

echo "$TAG,Run a HTTP GET list test to $SITE"
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

# process $LIST to make .well-known URLs of those

WKULIST=wkulist-$NOW.list

while read line 
do
    # line has one of these formats, producing the output shown
    # case1   "ni:///sha-256[-N];val"             --> http://$SITE/.well-known/sha-256[-N]/val
    # case2   "ni://<auth>/sha-256[-N];val"       --> http://<auth>/.well-known/sha-256[-N]/val
    # case3   "sha-256[-N];val"                   --> http://$SITE/.well-known/sha-256[-N]/val

    # echo "in: $line "

    case $line in
        ni:///*) 
            # echo "case1"
            alg=`echo $line | sed -e 's/ni:\/\/\///' | sed -e 's/;.*//'`
            val=`echo $line | sed -e 's/ni:\/\/\///' | sed -e 's/.*;//'`
            wku="http://$SITE/.well-known/ni/$alg/$val"
            ;;
        ni://[a-z0-9]*) 
            # echo "case2"
            auth=`echo $line | sed -e 's/ni:\/\///' | sed -e 's/\/.*//'`
            alg=`echo $line | sed -e 's/.*\///' | sed -e 's/;.*//'`
            val=`echo $line | sed -e 's/.*\///' | sed -e 's/.*;//'`
            wku="http://$auth/.well-known/ni/$alg/$val"
            ;;
        sha-256*) 
            # echo "case3)"
            alg=`echo $line | sed -e 's/;.*//'`
            val=`echo $line | sed -e 's/.*;//'`
            wku="http://$SITE/.well-known/ni/$alg/$val"
            ;;
        *) 
            # ignore crap
            ;;
    esac 

    # get it and time it
    
    stime=`date +%s%N`
    curl_sztm=`curl -L -s -w "%{size_download},%{time_total}\n" -o /tmp/wkufile --url $wku`
    # hash but don't bother comparing, only care about timing for now
    openssl sha256 /tmp/wkufile >/dev/null 2>&1
    rm -rf /tmp/wkufile
    etime=`date +%s%N`
    
    dur=$(((etime-stime)/1000000))

    echo "$wku,$curl_sztm,$dur" >>$CLILOG
    
    
done <$LIST

echo "$TAG,Finished Fetching: last line of log:"
LOGLAST=`tail -1 $CLILOG`
echo "$TAG,$LOGLAST"

echo "$TAG,Generatiing CSV for gnuplot with size,duration"

cat $CLILOG | awk -F, '{print $2","$4}' >$CSVFILE

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


