
src=eo

#FIC=locale/en/LC_MESSAGES/motioneye.po
FIC=$1
dst=`grep "^\"Language: .*\\n\"$" $FIC|sed "s/^\"Language: //;s/.n\"$//"`

cat $FIC|awk -v src=$src -v dst=$dst '{
  if ( CONTMSG==1 && substr($1,1,1) != "\"")
    CONTMSG=0;
  if ($1 == "msgid")
  {
    MSGID=substr($0,7);
    print $0;
    if(MSGID="\"\"")
      CONTMSG=1;
  }
  else if ( CONTMSG==1 && substr($1,1,1) == "\"")
  {
    MSGID=MSGID $0;
    print $0;
  }
  else if ($1 == "msgstr")
  {
    if($2 != "\"\"")
      print $0;
    else
    {
      printf("msgstr \"");
      MSG=system("./traduko.sh " src " " dst " " MSGID )
      printf("\"\n");
    }
  }
  else
    print $0;
}' >$FIC.$$
mv $FIC $FIC.old
mv $FIC.$$ $FIC
