#!/bin/dash

# globbing

echo *.c
echo ?.py
echo *.[ch]

echo all of the single letter Python files are: ?.py

# for loops

for i in 1 2 3
do
    echo $i
done

for word in this is a string
do
    echo $word
done

# working directory and external commands

echo top: *.c
mkdir -p subdir
touch subdir/example.txt
cd subdir
echo inside: *.txt
cd ..

touch test_file.txt
ls test_file.txt

# read

echo What is your name:
read name

echo What is your quest:
read quest

echo Hello $name
echo Quest: $quest

# exit

echo hello world
exit 0
echo this line should never appear
