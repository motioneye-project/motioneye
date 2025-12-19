import json
from unittest.mock import patch

import tornado.testing

from motioneye import config, utils
from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import HandlerTestCase


class AdminOnlyPictureHandlerTest(HandlerTestCase):
    handler_cls = PictureHandler

    async def _stub_current(self, camera_id, retry=0):
        self.finish_json({'ok': True})

    def setUp(self):
        super().setUp()
        # Backup caches
        self._main_config_cache = config._main_config_cache
        self._camera_config_cache = dict(config._camera_config_cache)
        self._camera_ids_cache = config._camera_ids_cache

        # Prepare test configuration
        config._main_config_cache = {
            '@admin_username': 'admin',
            '@admin_password': 'adm1n',
            '@normal_username': 'user',
            '@normal_password': '',
        }
        config._camera_ids_cache = [1]
        config._camera_config_cache = {
            1: {'@proto': 'mjpeg', '@id': 1, '@enabled': True, '@admin_only': False}
        }

    def tearDown(self):
        config._main_config_cache = self._main_config_cache
        config._camera_config_cache = self._camera_config_cache
        config._camera_ids_cache = self._camera_ids_cache
        super().tearDown()

    def _set_admin_only(self, value: bool):
        config._camera_config_cache[1]['@admin_only'] = value

    def _admin_signature(self, path: str) -> str:
        return utils.compute_signature('GET', path, b'', 'adm1n')

    def test_normal_user_allowed_when_not_admin_only(self):
        self._set_admin_only(False)
        with patch.object(PictureHandler, 'current', new=AdminOnlyPictureHandlerTest._stub_current):
            response = self.fetch('/picture/1/current')
        self.assertEqual(200, response.code)
        self.assertEqual({'ok': True}, json.loads(response.body))

    def test_normal_user_denied_when_admin_only(self):
        self._set_admin_only(True)
        response = self.fetch('/picture/1/current')
        self.assertEqual(403, response.code)
        body = json.loads(response.body)
        self.assertIn('admin-only', body.get('error', ''))

    def test_admin_allowed_when_admin_only(self):
        self._set_admin_only(True)
        path = '/picture/1/current?_username=admin'
        signature = self._admin_signature(path)
        url = f'{path}&_signature={signature}'
        with patch.object(PictureHandler, 'current', new=AdminOnlyPictureHandlerTest._stub_current):
            response = self.fetch(url)
        self.assertEqual(200, response.code)
        self.assertEqual({'ok': True}, json.loads(response.body))


if __name__ == '__main__':
    tornado.testing.main()
