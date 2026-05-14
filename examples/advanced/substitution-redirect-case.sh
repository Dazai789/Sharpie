#!/bin/dash

# args and backticks

echo arg count is $#

name=`printf student`
echo hello $name

# echo -n

n=1
limit=3

while test $n -le $limit
do
    echo -n item
    echo $n
    n=$((n + 1))
done

# nested while

row=1
while [ $row -le 2 ]
do
    col=1
    while test $col -le 3
    do
        if test $row -eq $col
        then
            echo -n "X "
        else
            echo -n ". "
        fi
        col=$((col + 1))
    done
    echo
    row=$((row + 1))
done

# redirect

echo first line > demo04.out
echo second line >> demo04.out
cat demo04.out
rm -f demo04.out

# input redirect

echo alpha > tmp.numbers
cat < tmp.numbers
rm -f tmp.numbers

# case

case $limit in
    1)
        echo one
        ;;
    2|3|4)
        echo some
        ;;
    *)
        echo many
        ;;
esac