from json import loads
from unittest.mock import patch

import tornado.testing

from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import _FAKE_CAMERA_CONFIG, HandlerTestCase


class AdminOnlyPictureHandlerTest(HandlerTestCase):
    handler_cls = PictureHandler

    async def _stub_current(self, camera_id, retry=0):
        self.finish_json({'ok': True})

    def tearDown(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = False
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
        # Set up an admin session directly in _session_store and obtain a
        # matching signed cookie – no login round-trip needed here since the
        # login flow is already covered by the dedicated login tests.
        cookie = self.make_session_cookie('admin')
        with patch.object(
            PictureHandler, 'current', new=AdminOnlyPictureHandlerTest._stub_current
        ):
            response = self.fetch('/picture/1/current', headers={'Cookie': cookie})
        self.assertEqual(200, response.code)
        self.assertEqual({'ok': True}, loads(response.body))


if __name__ == '__main__':
    tornado.testing.main()
