
all: locale/??/LC_MESSAGES/motioneye.mo \
	static/js/motioneye.??.json

%.mo: %.po
	msgfmt -f $*.po -o $*.mo

%/motioneye.po: locale/motioneye.pot
	msgmerge --no-wrap -N -U $@ $<
	./traduki_po.sh $@

static/js/motioneye.%.json : locale/%/LC_MESSAGES/motioneye.js.po
		./scripts/po2json locale/$*/LC_MESSAGES/motioneye.js.po static/js/motioneye.$*.json

%/motioneye.js.po: locale/motioneye.js.pot
	msgmerge --no-wrap -N -U $@ $<
	./traduki_po.sh $@

locale/motioneye.js.pot : static/js/*.js
	xgettext --from-code=UTF-8 --no-wrap -o locale/motioneye.js.pot static/js/*.js

locale/motioneye.pot : *.py templates/*.html
	pybabel extract -F babel.cfg -o locale/motioneye.pot .
#####
# regulo por krei novan tradukon
# ekz. : uzi "make initro" por krei la rumana traduko.
#####
init%:
	mkdir locale/$*
	mkdir locale/$*/LC_MESSAGES
	msginit --no-wrap --input locale/motioneye.js.pot --output locale/$*.js.tmp -l$* --no-translator
	./traduki_po.sh locale/$*.js.tmp
	mv locale/$*.js.tmp locale/$*/LC_MESSAGES/motioneye.js.po
	make static/js/motioneye.$*.json
	msginit --no-wrap --input locale/motioneye.pot --output locale/$*.tmp -l$* --no-translator
	./traduki_po.sh locale/$*.tmp
	mv locale/$*.tmp locale/$*/LC_MESSAGES/motioneye.po
	make locale/$*/LC_MESSAGES/motioneye.mo

#
#	msgattrib --set-fuzzy --clear-obsolete --no-wrap  locale/$*.tmp -o locale/$*/LC_MESSAGES/motioneye.po


traduki :
	find locale -name "*.po" -exec ./traduki_po.sh {} \;
