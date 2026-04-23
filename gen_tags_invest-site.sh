#!/bin/bash

# print all arguments
# echo $@
# Number of arguments on the command line
# echo $#

LNX=$PWD
if [[ "$@" == "clean" ]]; then
	echo "Remove tag files: tags, cscope*"
	rm -rf tags cscope*
	exit 0
fi

echo "Generate tag files: tags, cscope*"
LNX=$PWD

find  $LNX                                                            \
    -path "$LNX/build"                                    -prune -o   \
    -path "$LNX/AUTOSAR"                                  -prune -o   \
    -name "*.py" -print > $LNX/cscope.files

find  $LNX                                                            \
    -path "$LNX/build"                                    -prune -o   \
    -path "$LNX/AUTOSAR"                                  -prune -o   \
    -name "*.html" -print >> $LNX/cscope.files

cscope -bkq -i cscope.files
ctags -R

