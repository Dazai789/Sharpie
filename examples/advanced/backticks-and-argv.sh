#!/bin/dash

word=`printf hello`
echo $word

printf '[%s]\n' "$@"