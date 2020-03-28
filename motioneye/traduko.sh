
src="$1"
dst="$2"
txt="$3"

cook=`find traduko.jar -mmin -15`
if [ x$cook = x ]
then
  curl -c traduko.jar -A 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0' \
   "https://translate.google.com" -o /dev/null 
fi

curl -b traduko.jar -A 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0' \
 --refer "https://translate.google.com/" \
 "https://translate.google.com/translate_a/single?client=webapp&sl=${src}&tl=${dst}&hl=${dst}&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t&dt=gt&pc=1&otf=1&ssel=0&tsel=0&kc=1&tk=&ie=UTF-8&oe=UTF-8" \
--data-urlencode "q=${txt}" 2>/dev/null \
  |grep "\",null,null,[0-9]"|egrep -v "\[[1-9],"|sed "s/\",\".*//;s/^[,\[]*\"//" \
  | tr -d "\n" 
 
#  |grep ",null,null,[0-9]"|sed "s/\",\".*//;s/^[,\[]*\"//" \
# "http://translate.google.com/translate_a/single?client=webapp&sl=en&tl=eo&hl=eo&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qc&dt=rw&dt=rm&dt=ss&dt=t&dt=gt&pc=1&otf=1&ssel=0&tsel=0&kc=1&tk=&ie=UTF-8&oe=UTF-8" \
# "http://translate.google.com/translate_a/single?client=webapp&sl=auto&tl=eo&hl=eo&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t&dt=gt&pc=1&otf=1&ssel=0&tsel=0&kc=1&tk=" \

