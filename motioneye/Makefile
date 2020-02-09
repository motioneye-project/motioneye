
all: locale/motioneye.pot locale/fr/LC_MESSAGES/motioneye.mo locale/en/LC_MESSAGES/motioneye.mo locale/eo/LC_MESSAGES/motioneye.mo

locale/motioneye.pot : meyectl.py server.py templates/*.html
	pybabel extract -F babel.cfg -o locale/motioneye.pot .
	find locale -name "*.po" -exec msgmerge -U {} locale/motioneye.pot \;

locale/en/LC_MESSAGES/motioneye.mo: locale/en/LC_MESSAGES/motioneye.po
	msgfmt locale/en/LC_MESSAGES/motioneye.po -o locale/en/LC_MESSAGES/motioneye.mo

locale/eo/LC_MESSAGES/motioneye.mo: locale/eo/LC_MESSAGES/motioneye.po
	msgfmt locale/eo/LC_MESSAGES/motioneye.po -o locale/eo/LC_MESSAGES/motioneye.mo

locale/fr/LC_MESSAGES/motioneye.mo: locale/fr/LC_MESSAGES/motioneye.po
	msgfmt locale/fr/LC_MESSAGES/motioneye.po -o locale/fr/LC_MESSAGES/motioneye.mo

initfr:
	msginit --input locale/motioneye.pot --output locale/fr/LC_MESSAGES/motioneye.po -l=fr --no-translator

initen:
	mkdir -p locale/en/LC_MESSAGES
	msginit --input locale/motioneye.pot --output locale/en/LC_MESSAGES/motioneye.po -l=en --no-translator

