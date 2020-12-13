{
  if ( CONTMSG==1 && substr($1,1,1) != "\"")
  {
    CONTMSG=0;
  }
  if ($2 == "fuzzy")
  {
    FUZZY=1;
  }
  if ($1 == "msgid")
  {
    MSGID=substr($0,7);
    MSGSTR=substr($0,8,length($0)-8);
    MSGWRAP=0;
    if(MSGID=="\"\"")
    {
      CONTMSG=1;
      MSGWRAP=1;
    }
  }
  else if ( CONTMSG==1 && substr($1,1,1) == "\"")
  {
    MSGID=MSGID "\n" $0;
    MSGSTR=MSGSTR substr($0,2,length($0)-2);
  }
  else if ($1 == "msgstr")
  {
    if( ($2 != "\"\"" && $2 != "\"\\n\"") || MSGID == "\"\"")
    {
      print ("msgid " MSGID);
      print $0;
    }
    else
    {
      # msgstr "" kaj MSGID != ""
      $0="";
      getline
      if ( substr($1,1,1) == "\"")
      { # plurlinia mesaĝo
        print ("msgid " MSGID);
        printf("msgstr \"\"\n");
	print $0;
        FUZZY=0;
	next;
      }
      if(MATTER == "lang")
      {
        print ("msgid " MSGID);
        printf("msgstr \"" dst "\"\n");
      }
      else if(MATTER == "layout")
      {
        print ("msgid " MSGID);
        print ("msgstr " MSGID);
      }
      else if(MATTER == "lang-ref")
      {
        print ("msgid " MSGID);
        print ("msgstr " MSGID);
      }
      else if(MATTER == "lang-niv")
      {
        print ("msgid " MSGID);
        print ("msgstr \"auto\"" );
      }
      else if(MATTER == "Fenced")
      {
        print ("msgid " MSGID);
        print ("msgstr " MSGID);
      }
      else
      {
        if(FUZZY ==0)
          print ("#, fuzzy");
        print ("msgid " MSGID);
        printf("msgstr \"");
          split(MSGSTR,MSGS,"__| _|_ |_|<|>|\\\\n|**|\n|!|\\[|\\]|\\(|\\)|\\|\\\"|\"|\\\\|\\|",SEPS);
          for (x=1 ; x<=length(MSGS) ; x++)
          {
            if(match(MSGS[x],"[[:alpha:]]")==0 )
            {
              printf(MSGS[x]);
            }
            else if(MSGS[x] != "")
            {
	      while(substr(MSGS[x],1,1) == " ")
              {
		printf(" ");
	        MSGS[x]=substr(MSGS[x],2);
              }
              MSG=system(BASEDIR"/traduko.sh " src " " dst " \"" MSGS[x] "\"" )
	      #MSG=system(BASEDIR"/trans -no-warn -b --bidi " src ":" dst " \"" MSGS[x] "\"" )
	      while(substr(MSGS[x],length(MSGS[x]),1) == " ")
              {
		printf(" ");
	        MSGS[x]=substr(MSGS[x],1,length(MSGS[x])-1);
              }
#|sed "s/^  *//"
            }
            printf( SEPS[ x ] );
            if(SEPS[ x ] == "(")
            {
              do
              {
                x++;
                printf(MSGS[x] SEPS[x]);
              }
              while( x<=length(MSGS) && SEPS[x] != ")");
            }
            if(SEPS[ x ] == " _" || SEPS[ x ] == "_")
            {
              do
              {
                x++;
                printf(MSGS[x] SEPS[x]);
              }
              while( x<=length(MSGS) && SEPS[x] != "_ " && SEPS[x] != "_");
            }
            if(SEPS[ x ] == "<")
            {
              do
              {
                x++;
                printf(MSGS[x] SEPS[x]);
              }
              while( x<=length(MSGS) && SEPS[x] != ">" );
            }
          }
        print "\"";
      }
      FUZZY=0;
      MATTER="";
      print $0;
    }
  }
  else if (substr($0,1,28) == "#. type: YAML Front Matter: ")
  {
    MATTER=substr($0,29);
    print $0;
  }
  else if (substr($0,1,15) == "#. type: Fenced")
  {
    MATTER="Fenced";
    print $0;
  }
  else
  {
    print $0;
  }
}
