#!/usr/bin/env sh
################################################################
# skripto por aŭtomate traduki frazon
################################################################
DEBUG=
#DEBUG=1

src=$1
dst=$2
txt=$3

cook=$(find . -maxdepth 1 _traduko.jar -mmin -15 2>/dev/null)

PROVO=0

while [ "$PROVO" -lt 3 ]
do

if [ -z "$cook" ]
then
  curl -c _traduko.jar -A 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0' \
  'https://translate.google.com' -o /dev/null 2>/dev/null
fi

MSG0=$(curl -b _traduko.jar -A 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0' \
  --refer 'https://translate.google.com/' \
  "https://translate.google.com/translate_a/single?client=webapp&sl=${src}&tl=${dst}&hl=${dst}&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t&dt=gt&pc=1&otf=1&ssel=0&tsel=0&kc=1&tk=&ie=UTF-8&oe=UTF-8" \
  --data-urlencode "q=${txt}" 2>/dev/null \
)

[ "$DEBUG" ] && echo "$src txt=$txt" >&2

if echo "$MSG0" | grep -q 'sorry'
then
  # echo sorry
  BASEDIR=$(dirname "$(readlink -f "$0")")
  MSG=$("$BASEDIR/trans" -b -s "$src" -t "$dst" "$txt")
else
  # echo pas sorry
  MSG=$(echo "$MSG0" | jq '.[0][][0]' | grep -v '^null$' \
  | sed "s/\\\\u003d/=/g;s/\\\\u003c/</g;s/\\\\u003e/>/g" \
  | sed "s/\\\\u200b//g" \
  | sed "s/\xe2\x80\x8b//g" \
  | sed "s/^\"//;s/\"$//" \
  | tr -d "\n" \
  | sed "s/\\\ [nN]/n/g;s/] (/](/g;s/ __ / __/g" \
  | sed "s/\. \\\n$/.  \\\n/" \
  )
fi
[ "$DEBUG" ] && echo "$dst txt=$MSG" >&2

if [ -z "$MSG" ]
then
  cook=''
else
  printf '%s' "$MSG"
  break;
fi

PROVO=$((PROVO+1))
done
