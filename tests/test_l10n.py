import builtins
import unittest
from unittest.mock import patch

from motioneye import meyectl, settings, template

_SAVED = ('lingvo', 'langlist', 'traduction', 'js_translations')


class L10nTest(unittest.TestCase):
    def setUp(self):
        for name in _SAVED:
            self.addCleanup(setattr, settings, name, getattr(settings, name, None))
        if hasattr(builtins, '_'):
            self.addCleanup(setattr, builtins, '_', builtins._)
        else:
            self.addCleanup(builtins.__dict__.pop, '_', None)
        patcher = patch.object(template, '_jinja_env', None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def load(self, lang):
        with patch('motioneye.meyectl.config.get_main', return_value={'@lang': lang}):
            meyectl.load_l10n()

    def render(self, lang):
        self.load(lang)
        template.add_context('static_path', 'static/')
        template._reload_lang()
        return template.render('main.html', main_sections={}, camera_sections={})

    def test_loads_page_translations(self):
        self.load('en')
        self.assertEqual('en', settings.js_translations['']['language'])

    def test_esperanto_needs_no_translations(self):
        self.load('eo')
        self.assertIsNone(settings.js_translations)

    def test_unreadable_translations_are_logged(self):
        with patch('motioneye.meyectl.open', side_effect=OSError('gone'), create=True):
            with self.assertLogs(level='ERROR'):
                self.load('en')
        self.assertIsNone(settings.js_translations)

    def test_page_embeds_translations(self):
        html = self.render('en')
        self.assertIn('i18n.loadJSON({', html)
        self.assertNotIn('XMLHttpRequest', html)

    def test_esperanto_page_loads_nothing(self):
        html = self.render('eo')
        self.assertNotIn('i18n.loadJSON', html)


if __name__ == '__main__':
    unittest.main()
