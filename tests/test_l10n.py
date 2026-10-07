import builtins
import json
import os
import re
import unittest
from unittest.mock import patch

from motioneye import meyectl, settings, template

_SAVED = ('lingvo', 'langlist', 'traduction', 'js_translations')
_PAGE_DATA = re.compile(r'<script type="application/json" id="pageData">(.*?)</script>')
_PAGE_KEYS = ('staticPath', 'frame', 'hasMotion', 'maskWidth', 'currentUser')


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

    def render(self, lang, **context):
        self.load(lang)
        template.add_context('static_path', 'static/')
        template._reload_lang()
        context.update(main_sections={}, camera_sections={})
        return template.render('main.html', **context)

    def page_data(self, html):
        m = _PAGE_DATA.search(html)
        self.assertIsNotNone(m)
        return json.loads(m.group(1))

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
        self.assertEqual('en', self.page_data(html)['translations']['']['language'])
        self.assertNotIn('XMLHttpRequest', html)

    def test_esperanto_page_loads_nothing(self):
        html = self.render('eo')
        self.assertIsNone(self.page_data(html)['translations'])

    def test_scripts_add_no_inline_style(self):
        for name in ('main.js', 'ui.js', 'frame.js'):
            path = os.path.join(settings.STATIC_PATH, 'js', name)
            with open(path, encoding='utf-8') as f:
                self.assertEqual([], re.findall(r'.*style=.*', f.read()), name)

    def page_values(self, html):
        data = self.page_data(html)
        return tuple(data[k] for k in _PAGE_KEYS)

    def test_pages_have_no_inline_script_or_style(self):
        main = self.render('en', has_motion=True, mask_width=32, current_user='admin')
        camera = {'stream_maxrate': 5, '@proto': 'mjpeg', '@url': 'http://cam/'}
        up = '../../../static/'
        ctx = dict(frame=True, camera_id=1, camera_config=camera, static_path=up)
        frame = self.render('en', **ctx)
        for html in (main, frame):
            for attrs in re.findall(r'<script\b([^>]*)>', html):
                self.assertRegex(attrs, r' src=|type="application/json"')
            self.assertIsNone(re.search(r'\son[a-z]+=', html))
            self.assertNotIn('javascript:', html)
            self.assertIsNone(re.search(r'\sstyle=|<style', html))

        self.assertEqual(('static/', False, True, 32, 'admin'), self.page_values(main))
        self.assertEqual((up, True, False, None, ''), self.page_values(frame))


if __name__ == '__main__':
    unittest.main()
