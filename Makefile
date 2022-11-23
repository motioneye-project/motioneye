
all: motioneye/locale/*/LC_MESSAGES/motioneye.mo \
	motioneye/static/js/motioneye.*.json

%.mo: %.po
	msgfmt -f $*.po -o $*.mo

%/motioneye.po: motioneye/locale/motioneye.pot
	# Wrap on 80 characters width to match Weblate
	msgmerge -w 80 -N -U $@ $<
	l10n/traduki_po.sh $@

motioneye/static/js/motioneye.%.json : motioneye/locale/%/LC_MESSAGES/motioneye.js.po
		l10n/po2json motioneye/locale/$*/LC_MESSAGES/motioneye.js.po motioneye/static/js/motioneye.$*.json

%/motioneye.js.po: motioneye/locale/motioneye.js.pot
	msgmerge -w 80 -N -U $@ $<
	l10n/traduki_po.sh $@

motioneye/locale/motioneye.js.pot : motioneye/static/js/*.js l10n/*.js
	xgettext --from-code=UTF-8 -w 80 -o motioneye/locale/motioneye.js.pot motioneye/static/js/*.js l10n/*.js

motioneye/locale/motioneye.pot : motioneye/*.py motioneye/*/*.py motioneye/templates/*.html
	pybabel extract -F l10n/babel.cfg -o motioneye/locale/motioneye.pot motioneye/
	# Remove trailing empty line, to satisfy pre-commit
	sed -i '${/^$/d}' motioneye/locale/motioneye.pot
#####
# regulo por krei novan tradukon
# ekz. : uzi "make initro" por krei la rumana traduko.
#####
init%:
	mkdir motioneye/locale/$*
	mkdir motioneye/locale/$*/LC_MESSAGES
	msginit -w 80 --input motioneye/locale/motioneye.js.pot --output motioneye/locale/$*.js.tmp -l$* --no-translator
	l10n/traduki_po.sh motioneye/locale/$*.js.tmp
	mv motioneye/locale/$*.js.tmp motioneye/locale/$*/LC_MESSAGES/motioneye.js.po
	make motioneye/static/js/motioneye.$*.json
	msginit -w 80 --input motioneye/locale/motioneye.pot --output motioneye/locale/$*.tmp -l$* --no-translator
	l10n/traduki_po.sh motioneye/locale/$*.tmp
	mv motioneye/locale/$*.tmp motioneye/locale/$*/LC_MESSAGES/motioneye.po
	make motioneye/locale/$*/LC_MESSAGES/motioneye.mo
	#msgattrib --set-fuzzy --clear-obsolete -w 80 locale/$*.tmp -o locale/$*/LC_MESSAGES/motioneye.po

traduki :
	find motioneye/locale -name "*.po" -exec l10n/traduki_po.sh {} \;
