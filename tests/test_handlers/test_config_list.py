import asyncio
from json import dumps, loads
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import tornado.testing

from motioneye.handlers.config import ConfigHandler
from motioneye.utils import GetConfigResponse
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


_LOCAL_CAMERA = {
    '@id': 1,
    '@enabled': True,
    '@admin_only': False,
    'camera_name': 'local',
    'netcam_url': 'http://localhost/stream',
}

_REMOTE_CAMERA = {
    '@id': 2,
    '@enabled': True,
    '@admin_only': False,
    '@proto': 'motioneye',
    '@host': 'hub.example',
    '@port': 8765,
    '@remote_camera_id': 2,
}


class ConfigListRemoteHubTest(HandlerTestCase):
    """A camera behind a remote motionEye which cannot reach it."""

    handler_cls = ConfigHandler

    def setUp(self):
        super().setUp()
        cameras = {1: _LOCAL_CAMERA, 2: _REMOTE_CAMERA}
        # answer of a remote motionEye which cannot reach its own camera
        answer = SimpleNamespace(
            error=None,
            body=dumps(
                {
                    'error': 'Failed to connect to cam.example:8765',
                    'connection_failed': True,
                    'connection_url': 'http://cam.example:8765',
                }
            ).encode(),
        )
        self._extra_patches = [
            patch('motioneye.config.get_main', return_value={'@enabled': True}),
            patch('motioneye.config.get_camera_ids', return_value=list(cameras)),
            patch('motioneye.config.get_camera', side_effect=cameras.get),
            patch(
                'motioneye.config.motion_camera_dict_to_ui',
                return_value=dict(_FAKE_UI_CONFIG),
            ),
            patch('motioneye.remote._send_request', AsyncMock(return_value=answer)),
        ]
        for p in self._extra_patches:
            p.start()

    def tearDown(self):
        for p in self._extra_patches:
            p.stop()
        super().tearDown()

    def test_unreachable_camera_behind_remote_hub_does_not_break_the_list(self):
        cookie = self.make_session_cookie('admin')
        response = self.fetch('/config/list/', headers={'Cookie': cookie})
        self.assertEqual(200, response.code)

        cameras = {c['id']: c for c in loads(response.body)['cameras']}
        self.assertEqual({1, 2}, set(cameras))
        self.assertTrue(cameras[1]['enabled'])
        self.assertFalse(cameras[2]['enabled'])
        self.assertTrue(cameras[2]['connection_failed'])
        self.assertIn('Failed to connect', cameras[2]['connection_error'])

    def test_normal_user_does_not_see_unreachable_admin_only_camera(self):
        remote_camera = dict(_REMOTE_CAMERA, **{'@admin_only': True})
        cameras = {1: _LOCAL_CAMERA, 2: remote_camera}
        cookie = self.make_session_cookie('normal')
        with patch('motioneye.config.get_camera', side_effect=cameras.get):
            response = self.fetch('/config/list/', headers={'Cookie': cookie})

        self.assertEqual(200, response.code)
        self.assertEqual([1], [c['id'] for c in loads(response.body)['cameras']])


class ConfigListParallelRemoteTest(HandlerTestCase):
    """Remote cameras are asked at the same time, not one after another."""

    handler_cls = ConfigHandler

    def setUp(self):
        super().setUp()
        self.cameras = {
            i: dict(_REMOTE_CAMERA, **{'@id': i, '@remote_camera_id': i})
            for i in (2, 3, 4)
        }
        self.asked = []
        self.all_asked = None
        self._extra_patches = [
            patch('motioneye.config.get_main', return_value={'@enabled': True}),
            patch(
                'motioneye.config.get_camera_ids',
                side_effect=lambda: list(self.cameras),
            ),
            patch('motioneye.config.get_camera', side_effect=self.cameras.get),
            patch('motioneye.remote.get_config', side_effect=self._get_config),
        ]
        for p in self._extra_patches:
            p.start()

    def tearDown(self):
        for p in self._extra_patches:
            p.stop()
        super().tearDown()

    async def _get_config(self, local_config):
        if self.all_asked is None:
            self.all_asked = asyncio.Event()

        self.asked.append(local_config['@remote_camera_id'])
        if len(self.asked) == len(
            [
                c
                for c in self.cameras.values()
                if '@remote_camera_id' in c and c['@enabled']
            ]
        ):
            self.all_asked.set()

        try:
            await asyncio.wait_for(self.all_asked.wait(), 1)

        except asyncio.TimeoutError:
            return GetConfigResponse(None, error='asked one after another')

        name = f"camera {local_config['@remote_camera_id']}"
        return GetConfigResponse({'enabled': True, 'name': name}, None)

    def test_remote_cameras_are_asked_at_the_same_time(self):
        cookie = self.make_session_cookie('admin')
        response = self.fetch('/config/list/', headers={'Cookie': cookie})
        self.assertEqual(200, response.code)

        cameras = loads(response.body)['cameras']
        self.assertEqual([2, 3, 4], [c['id'] for c in cameras])
        self.assertEqual(
            ['camera 2', 'camera 3', 'camera 4'], [c['name'] for c in cameras]
        )

    def test_disabled_remote_camera_is_not_asked(self):
        self.cameras[3]['@enabled'] = False
        del self.cameras[4]
        cookie = self.make_session_cookie('admin')
        response = self.fetch('/config/list/', headers={'Cookie': cookie})
        self.assertEqual(200, response.code)

        self.assertEqual([2], self.asked)
        cameras = {c['id']: c for c in loads(response.body)['cameras']}
        self.assertEqual('camera 2', cameras[2]['name'])
        self.assertTrue(cameras[3]['connection_failed'])

    def test_cameras_stay_in_order_when_one_is_hidden(self):
        self.cameras.clear()
        self.cameras.update(
            {
                1: dict(_LOCAL_CAMERA, **{'@id': 1, '@admin_only': True}),
                2: dict(_REMOTE_CAMERA, **{'@id': 2, '@remote_camera_id': 2}),
                3: dict(_LOCAL_CAMERA, **{'@id': 3}),
            }
        )
        cookie = self.make_session_cookie('normal')
        with patch(
            'motioneye.config.motion_camera_dict_to_ui',
            side_effect=lambda c: {'id': c['@id'], 'name': 'local', 'enabled': True},
        ):
            response = self.fetch('/config/list/', headers={'Cookie': cookie})

        self.assertEqual(200, response.code)
        self.assertEqual([2, 3], [c['id'] for c in loads(response.body)['cameras']])


if __name__ == '__main__':
    tornado.testing.main()
