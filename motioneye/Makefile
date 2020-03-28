
all: locale/??/LC_MESSAGES/motioneye.mo \
	static/js/motioneye.??.json 

%.mo: %.po
	msgfmt $*.po -o $*.mo

%/motioneye.po: locale/motioneye.pot
	msgmerge -N --no-wrap -U $@ $<
	./traduki_po.sh $@

static/js/motioneye.%.json : locale/%/LC_MESSAGES/motioneye.js.po
		./scripts/po2json locale/$*/LC_MESSAGES/motioneye.js.po static/js/motioneye.$*.json

%/motioneye.js.po: locale/motioneye.js.pot
	msgmerge -N --no-wrap -U $@ $<
	./traduki_po.sh $@

locale/motioneye.js.pot : static/js/*.js
	xgettext --no-wrap -o locale/motioneye.js.pot static/js/*.js

locale/motioneye.pot : meyectl.py server.py templates/*.html
	pybabel extract -F babel.cfg -o locale/motioneye.pot .

init%:
	mkdir -p locale/$*/LC_MESSAGES
	msginit --input locale/motioneye.pot --output locale/$*/LC_MESSAGES/motioneye.po -l$* --no-translator
	msginit --input locale/motioneye.js.pot --output locale/$*/LC_MESSAGES/motioneye.js.po -l$* --no-translator
	make locale/$*/LC_MESSAGES/motioneye.mo
	make locale/$*/LC_MESSAGES/motioneye.js.json

traduki :
	find locale -name "*.po" -exec ./traduki_po.sh {} \;
