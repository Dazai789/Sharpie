#!/bin/dash

word=$(printf hello)
echo $word

n=1
while test $n -le 2
do
    echo $((n + 1))
    n=$((n + 1))
done

test -x /dev/null || echo not-exec

case $# in
    0|1)
        echo small
        ;;
    *)
        echo big
        ;;
esac
