ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

.PHONY: all
all: $(ROOT)/motioneye/locale/*/LC_MESSAGES/motioneye.mo $(ROOT)/motioneye/static/js/motioneye.*.json

$(ROOT)/%.mo: $(ROOT)/%.po
	msgfmt -f $< -o $@

$(ROOT)/%/motioneye.po: $(ROOT)/motioneye/locale/motioneye.pot
	msgmerge --no-wrap -N -U $@ $<
	# Disable Google Translator usage for now, which does rarely work from GitHub CI due to rate limiting.
	# Also Weblate supports auto-translation from various sources as well.
	#$(ROOT)/l10n/traduki_po.sh $@

$(ROOT)/motioneye/static/js/motioneye.%.json: $(ROOT)/motioneye/locale/%/LC_MESSAGES/motioneye.js.po
	$(ROOT)/l10n/po2json $< $@

$(ROOT)/%/motioneye.js.po: $(ROOT)/motioneye/locale/motioneye.js.pot
	msgmerge --no-wrap -N -U $@ $<
	# Disable Google Translator usage for now, which does rarely work from GitHub CI due to rate limiting.
	# Also Weblate supports auto-translation from various sources as well.
	#$(ROOT)/l10n/traduki_po.sh $@

$(ROOT)/motioneye/locale/motioneye.js.pot: $(ROOT)/motioneye/static/js/*.js $(ROOT)/l10n/*.js
	xgettext --no-wrap --from-code=UTF-8 -o $@ $^

$(ROOT)/motioneye/locale/motioneye.pot: $(ROOT)/motioneye/*.py $(ROOT)/motioneye/*/*.py $(ROOT)/motioneye/templates/*.html
	pybabel extract -F $(ROOT)/l10n/babel.cfg -o $@ $(ROOT)/motioneye/
	# Remove trailing empty line to satisfy pre-commit
	sed -i '$${/^$$/d}' $@

#####
# regulo por krei novan tradukon
# ekz. : uzi "make initro" por krei la rumana traduko.
#####
.PHONY: init%
init%:
	mkdir $(ROOT)/motioneye/locale/$*
	mkdir $(ROOT)/motioneye/locale/$*/LC_MESSAGES
	msginit --no-wrap -i $(ROOT)/motioneye/locale/motioneye.js.pot -o $(ROOT)/motioneye/locale/$*.js.tmp -l$* --no-translator
	#$(ROOT)/l10n/traduki_po.sh $(ROOT)/motioneye/locale/$*.js.tmp
	mv $(ROOT)/motioneye/locale/$*.js.tmp $(ROOT)/motioneye/locale/$*/LC_MESSAGES/motioneye.js.po
	$(MAKE) $(ROOT)/motioneye/static/js/motioneye.$*.json
	msginit --no-wrap -i $(ROOT)/motioneye/locale/motioneye.pot -o $(ROOT)/motioneye/locale/$*.tmp -l$* --no-translator
	#$(ROOT)/l10n/traduki_po.sh $(ROOT)/motioneye/locale/$*.tmp
	#msgattrib --no-wrap --set-fuzzy --clear-obsolete $(ROOT)/motioneye/locale/$*.tmp -o $(ROOT)/motioneye/locale/$*/LC_MESSAGES/motioneye.po
	mv $(ROOT)/motioneye/locale/$*.tmp $(ROOT)/motioneye/locale/$*/LC_MESSAGES/motioneye.po
	$(MAKE) $(ROOT)/motioneye/locale/$*/LC_MESSAGES/motioneye.mo

.PHONY: traduki
traduki:
	find $(ROOT)/motioneye/locale -name "*.po" -exec $(ROOT)/l10n/traduki_po.sh {} \;
