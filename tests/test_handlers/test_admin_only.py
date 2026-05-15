from json import loads
from unittest.mock import patch

import tornado.testing

from motioneye import config, settings, utils
from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import _FAKE_CAMERA_CONFIG, HandlerTestCase


class AdminOnlyPictureHandlerTest(HandlerTestCase):
    handler_cls = PictureHandler

    async def _stub_current(self, camera_id, retry=0):
        self.finish_json({'ok': True})

    def setUp(self):
        super().setUp()
        # Backup caches
        self._main_config_cache = config._main_config_cache

        # Prepare test configuration
        self.admin_user = 'superadmin'
        self.admin_pass = 's3cret'
        self.normal_user = 'viewer'
        self.normal_pass = ''
        config._main_config_cache = {
            '@admin_username': self.admin_user,
            '@admin_password': self.admin_pass,
            '@normal_username': self.normal_user,
            '@normal_password': self.normal_pass,
        }

    def tearDown(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = False
        config._main_config_cache = self._main_config_cache
        super().tearDown()

    def test_normal_user_allowed_when_not_admin_only(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = False
        with patch.object(
            PictureHandler, 'current', new=AdminOnlyPictureHandlerTest._stub_current
        ):
            response = self.fetch('/picture/1/current')
        self.assertEqual(200, response.code)
        self.assertEqual({'ok': True}, loads(response.body))

    def test_normal_user_denied_when_admin_only(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = True
        response = self.fetch('/picture/1/current')
        self.assertEqual(403, response.code)
        body = loads(response.body)
        self.assertIn('admin-only', body.get('error', ''))

    def test_admin_allowed_when_admin_only(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = True
        # perform login to get session cookie
        response = self.fetch(
            '/login',
            method='POST',
            body=f'username={self.admin_user}&password={self.admin_pass}',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        cookie = response.headers.get('Set-Cookie', '')
        with patch.object(
            PictureHandler, 'current', new=AdminOnlyPictureHandlerTest._stub_current
        ):
            response = self.fetch('/picture/1/current', headers={'Cookie': cookie})
        self.assertEqual(200, response.code)
        self.assertEqual({'ok': True}, loads(response.body))

    def test_admin_allowed_when_admin_only_with_basic_auth(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = True
        auth_header = utils.build_basic_header(self.admin_user, self.admin_pass)
        with patch.object(settings, 'HTTP_BASIC_AUTH', True):
            with patch.object(
                PictureHandler, 'current', new=AdminOnlyPictureHandlerTest._stub_current
            ):
                response = self.fetch(
                    '/picture/1/current', headers={'Authorization': auth_header}
                )
        self.assertEqual(200, response.code)
        self.assertEqual({'ok': True}, loads(response.body))


if __name__ == '__main__':
    tornado.testing.main()
