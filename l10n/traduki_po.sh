#!/usr/bin/env sh
#################################################################
# skripto por aŭtomate traduki frazojn sen traduko en po-dosieron
#################################################################

src=eo

#FIC=locale/en/LC_MESSAGES/motioneye.po
FIC=$1
dst=$(grep '^"Language: .*\n"$' "$FIC" | sed 's/^"Language: //;s/.n"$//')

awk -v "src=$src" -v "dst=$dst" '{
  if ( CONTMSG==1 && substr($1,1,1) != "\"")
  {
    CONTMSG=0;
  }
  if ($1 == "msgid")
  {
    MSGID=substr($0,7);
    if(MSGID=="\"\"")
      CONTMSG=1;
  }
  else if ( CONTMSG==1 && substr($1,1,1) == "\"")
  {
    MSGID=MSGID $0;
  }
  else if ($1 == "msgstr")
  {
    if($2 != "\"\"" || MSGID == "\"\"")
    {
      print ("msgid " MSGID);
      print $0;
    }
    else
    {
      print ("#, fuzzy");
      print ("msgid " MSGID);
      printf("msgstr \"");
      MSG=system("l10n/traduko.sh " src " " dst " " MSGID )
      printf("\"\n");
    }
  }
  else
    print $0;
}' "$FIC" > "$FIC.$$"
mv "$FIC" "$FIC.old"
mv "$FIC.$$" "$FIC"
