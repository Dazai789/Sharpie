#!/bin/dash

# if

name=Lucius

if test $name = great
then
    echo wrong branch
elif test $name = Lucius
then
    echo elif branch works
else
    echo wrong branch again
fi

# file test

if [ -d /dev ]
then
    echo /dev is a directory
fi

if test -r /dev/null
then
    echo /dev/null is readable
fi

# while

status=off
count=1

while test $count -le 3
do
    echo "status is $status"
    echo 'still running'

    if test $status = off
    then
        status=half
    else
        status=on
    fi

    count=$((count + 1))
done