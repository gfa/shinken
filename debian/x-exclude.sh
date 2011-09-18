#!/bin/sh -e

# $1 version
TAR=shinken_$1.orig.tar.gz
DIR=shinken-$1

PWD=`pwd`

DEBIAN_EXCLUDE="$PWD/debian/x-exclude"

cd ..

TMP=`mktemp -d --tmpdir=\`pwd\``

cd $TMP
tar zxf ../$TAR
tar -zcf $TAR -X $DEBIAN_EXCLUDE $DIR
mv $TAR ../$TAR
cd ..

rm -rf $TMP

exit 0
