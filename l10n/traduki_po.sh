#!/usr/bin/env sh
#################################################################
# skripto por aŭtomate traduki frazojn sen traduko en po-dosieron
#################################################################

src=eo

#FIC=locale/en/LC_MESSAGES/motioneye.po
FIC=$1
dst=$(grep '^"Language: .*\n"$' "$FIC" | sed 's/^"Language: //;s/.n"$//')

awk -v "src=$src" -v "dst=$dst" '{
  if (CONTMSG==1 && substr($1,1,1) != "\"")
  {
    CONTMSG=0;
  }
  if ($1 == "msgid")
  {
    MSGID=substr($0,7);
    if (MSGID=="\"\"")
      CONTMSG=1;
  }
  else if (CONTMSG==1 && substr($1,1,1) == "\"")
  {
    MSGID = substr(MSGID,1,length(MSGID)-1) substr($0,2);
  }
  else if ($1 == "msgstr")
  {
    if ($2 != "\"\"" || MSGID == "\"\"")
    {
      print ("msgid " MSGID);
      print $0;
    }
    else
    {
      getline nextline
      if (nextline == "")
      {
        print ("msgid " MSGID);
        printf("msgstr \"");
        MSG=system("l10n/traduko.sh " src " " dst " " MSGID)
        printf("\"\n\n");
      }
      else
      {
        print ("msgid " MSGID);
        print $0;
        print nextline;
      }
    }
  }
  else
    print $0;
}' "$FIC" > "$FIC.$$"
mv "$FIC" "$FIC.old"
mv "$FIC.$$" "$FIC"
# Remove trailing empty line, to satisfy pre-commit
sed -i '${/^$/d}' "$FIC"
