#!/usr/bin/env sh
################################################################
# skripto por aŭtomate traduki frazon
################################################################
#DEBUG=

src=$1
dst=$2
txt=$3

# Reuse cookie if not older than 15 minutes

cookie=$(find . -maxdepth 1 -name _traduko.jar -mmin -14)

# Obtain cookie
[ "$cookie" ] || curl -sSfc _traduko.jar -A 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0' 'https://translate.google.com' -o /dev/null > /dev/null

# Obtain translation from Google Translator API
MSG0=$(curl -sSfb _traduko.jar -A 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0' \
  --refer 'https://translate.google.com/' \
  "https://translate.google.com/translate_a/single?client=webapp&sl=${src}&tl=${dst}&hl=${dst}&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t&dt=gt&pc=1&otf=1&ssel=0&tsel=0&kc=1&tk=&ie=UTF-8&oe=UTF-8" \
  --data-urlencode "q=$txt" > /dev/null \
)

[ "$DEBUG" ] && printf '%s\n' "$src txt=$txt" >&2

if printf '%s' "$MSG0" | grep -q 'sorry'
then
  # Failed: Print error
  printf '%s\n%s\n' 'ERROR: Google Translator returned "sorry":' "$MSG0" >&2
else
  # Success: Extract translated txt
  MSG=$(printf '%s' "$MSG0" | jq '.[0][][0]' | grep -v '^null$' \
  | sed "s/\\\\u003d/=/g;s/\\\\u003c/</g;s/\\\\u003e/>/g" \
  | sed "s/\\\\u200b//g" \
  | sed "s/\xe2\x80\x8b//g" \
  | sed "s/^\"//;s/\"$//" \
  | tr -d "\n" \
  | sed "s/\\\ [nN]/n/g;s/] (/](/g;s/ __ / __/g" \
  | sed "s/\. \\\n$/.  \\\n/" \
  )
fi

[ "$DEBUG" ] && printf '%s\n' "$dst txt=$MSG" >&2

# Reset cookie if no message returned
if [ "$MSG" ]
then
  printf '%s' "$MSG"
else
  printf '%s\n' 'ERROR: Google Translator did not return a translation' >&2
  rm -f _traduko.jar
fi
