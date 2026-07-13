from json import loads
from unittest.mock import patch

import tornado.testing

from motioneye.handlers.config import ConfigHandler
from tests.test_handlers import HandlerTestCase

# a fake motion_camera_dict_to_ui() result that mixes viewer and admin-only fields
_FAKE_UI_CONFIG = {
    'id': 1,
    'name': 'test',
    'enabled': True,
    'proto': 'v4l2',
    'actions': ['snapshot'],
    'streaming_framerate': 25,
    'streaming_server_resize': False,
    'admin_only': False,
    'device_url': '/dev/video0',
    'network_username': 'secretuser',
    'network_password': 'secretpass',
    'upload_username': 'uploaduser',
    'upload_password': 'uploadpass',
    'upload_access_key': 'AKIAEXAMPLE',
    'upload_secret_key': 'shh-its-secret',
}

_SENSITIVE_FIELDS = (
    'admin_only',
    'device_url',
    'network_username',
    'network_password',
    'upload_username',
    'upload_password',
    'upload_access_key',
    'upload_secret_key',
)

_PUBLIC_FIELDS = (
    'id',
    'name',
    'enabled',
    'proto',
    'actions',
    'streaming_framerate',
    'streaming_server_resize',
)


class ConfigListHandlerTest(HandlerTestCase):
    handler_cls = ConfigHandler

    def setUp(self):
        super().setUp()
        self._extra_patches = [
            patch('motioneye.config.get_main', return_value={'@enabled': True}),
            patch('motioneye.utils.is_local_motion_camera', return_value=True),
            patch(
                'motioneye.config.motion_camera_dict_to_ui',
                return_value=dict(_FAKE_UI_CONFIG),
            ),
        ]
        for p in self._extra_patches:
            p.start()

    def tearDown(self):
        for p in self._extra_patches:
            p.stop()
        super().tearDown()

    def test_normal_user_does_not_get_admin_fields(self):
        cookie = self.make_session_cookie('normal')
        response = self.fetch('/config/list/', headers={'Cookie': cookie})
        self.assertEqual(200, response.code)

        cameras = loads(response.body)['cameras']
        self.assertEqual(1, len(cameras))
        camera = cameras[0]

        for field in _SENSITIVE_FIELDS:
            self.assertNotIn(field, camera)

        for field in _PUBLIC_FIELDS:
            self.assertIn(field, camera)

    def test_admin_gets_full_config(self):
        cookie = self.make_session_cookie('admin')
        response = self.fetch('/config/list/', headers={'Cookie': cookie})
        self.assertEqual(200, response.code)

        cameras = loads(response.body)['cameras']
        camera = cameras[0]

        for field in _SENSITIVE_FIELDS:
            self.assertIn(field, camera)

    def test_sanitize_camera_on_usertype_keeps_full_config_for_peer(self):
        handler = self.get_handler()
        handler._current_user = 'peer'
        camera = handler._sanitize_camera_on_usertype(dict(_FAKE_UI_CONFIG))
        self.assertEqual(_FAKE_UI_CONFIG, camera)

    def test_sanitize_camera_on_usertype_strips_for_normal(self):
        handler = self.get_handler()
        handler._current_user = 'normal'
        camera = handler._sanitize_camera_on_usertype(dict(_FAKE_UI_CONFIG))
        for field in _SENSITIVE_FIELDS:
            self.assertNotIn(field, camera)
        for field in _PUBLIC_FIELDS:
            self.assertIn(field, camera)


if __name__ == '__main__':
    tornado.testing.main()
