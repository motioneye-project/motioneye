
all: locale/motioneye.pot locale/motioneye.js.pot \
	locale/fr/LC_MESSAGES/motioneye.mo \
	locale/en/LC_MESSAGES/motioneye.mo  \
	locale/de/LC_MESSAGES/motioneye.mo  \
	locale/de/LC_MESSAGES/motioneye.js.json static/js/motioneye.de.json \
	locale/en/LC_MESSAGES/motioneye.js.json static/js/motioneye.en.json \
	locale/fr/LC_MESSAGES/motioneye.js.json static/js/motioneye.fr.json \

static/js/motioneye.de.json: locale/en/LC_MESSAGES/motioneye.js.json
	cp -p locale/de/LC_MESSAGES/motioneye.js.json static/js/motioneye.de.json

static/js/motioneye.en.json: locale/en/LC_MESSAGES/motioneye.js.json
	cp -p locale/en/LC_MESSAGES/motioneye.js.json static/js/motioneye.en.json

static/js/motioneye.fr.json: locale/en/LC_MESSAGES/motioneye.js.json
	cp -p locale/fr/LC_MESSAGES/motioneye.js.json static/js/motioneye.fr.json

locale/motioneye.js.pot : static/js/*.js
	xgettext --no-wrap -o locale/motioneye.js.pot static/js/*.js
	for x in locale/?? ; do msgmerge --no-wrap -U $$x/LC_MESSAGES/motioneye.js.po locale/motioneye.js.pot;./traduki_po.sh $$x/LC_MESSAGES/motioneye.js.po ; done

locale/motioneye.pot : meyectl.py server.py templates/*.html
	pybabel extract -F babel.cfg -o locale/motioneye.pot .
	for x in locale/?? ; do msgmerge --no-wrap -U $$x/LC_MESSAGES/motioneye.po locale/motioneye.pot;./traduki_po.sh $$x/LC_MESSAGES/motioneye.po ; done

%.json: %.po
	scripts/po2json $*.po $*.json

%.mo: %.po
	msgfmt $*.po -o $*.mo

initde:
	mkdir -p locale/de/LC_MESSAGES
	msginit --input locale/motioneye.pot --output locale/de/LC_MESSAGES/motioneye.po -lde --no-translator
	msginit --input locale/motioneye.js.pot --output locale/de/LC_MESSAGES/motioneye.js.po -lde --no-translator

initfr:
	mkdir -p locale/fr/LC_MESSAGES
	msginit --input locale/motioneye.pot --output locale/fr/LC_MESSAGES/motioneye.po -lfr --no-translator
	msginit --input locale/motioneye.js.pot --output locale/fr/LC_MESSAGES/motioneye.js.po -lfr --no-translator

initen:
	mkdir -p locale/en/LC_MESSAGES
	msginit --input locale/motioneye.pot --output locale/en/LC_MESSAGES/motioneye.po -len --no-translator
	msginit --input locale/motioneye.js.pot --output locale/en/LC_MESSAGES/motioneye.js.po -len --no-translator

traduki :
	find locale -name "*.po" -exec ./traduki_po.sh {} \;
