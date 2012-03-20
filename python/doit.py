#!/bin/bash

sample_dir=../samples
bar_file=${sample_dir}/bar
foo_file=${sample_dir}/foo

if [ "$1" == "once" ]
then
	./nicl.py -g -n 'ni://tcd.ie/sha-256-16;?c=image%2Fjson' -f $bar_file
	exit
fi

echo "usage"
./nicl.py -h
echo "generate" 
./nicl.py -g -n 'ni://tcd.ie/sha-256;?c=image%2Fjson' -f $bar_file
echo "res: $?"; echo ""
echo "good verify - res should be 0"
./nicl.py -v -n 'ni://tcd.ie/sha-256;fdZ0A_iA9BIw2g_Ve8WaqZfmRS4Af1zy2hGdHOgM-Do?c=image%2Fjson' -f $bar_file
echo "res: $?"; echo ""
echo "bad verify (wrong file) - res should be 1"
./nicl.py -v -n 'ni://tcd.ie/sha-256;fdZ0A_iA9BIw2g_Ve8WaqZfmRS4Af1zy2hGdHOgM-D?c=image%2Fjson' -f $foo_file
echo "res: $?"; echo ""
echo "bad verify (wrong hash) - res should be 1"
./nicl.py -v -n 'ni://tcd.ie/sha-256;fdZ0A_xA9Byw2g_Ve8WaqZfmRS4Af1zy2hGdHOgM-Do?c=image%2Fjson' -f $bar_file
echo "res: $?"; echo ""


