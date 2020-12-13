#!/usr/bin/env sh
#################################################################
# skripto por aŭtomate traduki frazojn sen traduko en po-dosieron
#################################################################

src=eo
if [ x$TRADUKI_SRC != x ]
then
  src=$TRADUKI_SRC
fi

FIC=$1
BASEDIR=`dirname $0`
dst=`grep "^\"Language: .*\\n\"$" $FIC|sed "s/^\"Language: //;s/.n\"$//"`

#echo "cat $FIC|gawk -v BASEDIR=$BASEDIR -v src=$src -v dst=$dst -f $BASEDIR/traduki_po.awk >$FIC.$$"
cat $FIC|gawk -v BASEDIR=$BASEDIR -v src=$src -v dst=$dst -f $BASEDIR/traduki_po.awk >$FIC.nova
