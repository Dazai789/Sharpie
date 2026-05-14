#!/bin/dash

# args

echo program is $0
echo arg count is $#

first_arg=$1
second_arg=$2
third_arg=$3

echo arg1 is $first_arg
echo arg2 is $second_arg
echo arg3 is $third_arg
echo all args are $@

# test

if test $# -gt 1
then
    echo enough args
else
    echo need more args
fi