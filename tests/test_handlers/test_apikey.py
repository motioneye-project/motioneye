from base64 import b64encode
from json import dumps, loads
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, patch

import tornado.testing

from motioneye import apikeys
from motioneye.handlers.apikey import ApiKeyHandler
from motioneye.handlers.base import BaseHandler
from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import _FAKE_CAMERA_CONFIG, HandlerTestCase


# the same guard as the real method, around a body that needs no camera
@BaseHandler.auth(prompt=False)
async def _stub_current(self, camera_id, retry=0):
    self.finish_json({'ok': True, 'user': self.current_user})


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def basic(token, username='anything'):
    credentials = b64encode(f'{username}:{token}'.encode()).decode()
    return {'Authorization': f'Basic {credentials}'}


class ApiKeyTestCase(HandlerTestCase):
    def setUp(self):
        super().setUp()
        self.conf_path = mkdtemp()
        self._conf_patch = patch('motioneye.settings.CONF_PATH', self.conf_path)
        self._conf_patch.start()
        apikeys.reset()

    def tearDown(self):
        self._conf_patch.stop()
        apikeys.reset()
        rmtree(self.conf_path, True)
        _FAKE_CAMERA_CONFIG['@admin_only'] = False
        super().tearDown()


class ApiKeyAuthTest(ApiKeyTestCase):
    handler_cls = PictureHandler

    def fetch_current(self, headers):
        with patch.object(PictureHandler, 'current', new=_stub_current):
            return self.fetch('/picture/1/current/', headers=headers)

    def test_bearer_key_authenticates_with_its_role(self):
        _, admin_token = apikeys.add('admin script', 'admin')
        _, normal_token = apikeys.add('viewer script', 'normal')

        response = self.fetch_current(bearer(admin_token))
        self.assertEqual(200, response.code)
        self.assertEqual('admin', loads(response.body)['user'])

        response = self.fetch_current(bearer(normal_token))
        self.assertEqual(200, response.code)
        self.assertEqual('normal', loads(response.body)['user'])

    def test_basic_auth_password_is_a_key(self):
        _, token = apikeys.add('home assistant', 'normal')

        response = self.fetch_current(basic(token))
        self.assertEqual(200, response.code)
        self.assertEqual('normal', loads(response.body)['user'])

        response = self.fetch_current(basic(token, username=''))
        self.assertEqual(200, response.code)

    def test_basic_auth_without_a_key_is_not_a_login(self):
        response = self.fetch_current(basic('a password'))
        self.assertEqual(403, response.code)

        response = self.fetch_current({'Authorization': 'Basic %%%'})
        self.assertEqual(403, response.code)

    def test_wrong_or_revoked_key_is_refused(self):
        key, token = apikeys.add('script', 'admin')

        self.assertEqual(403, self.fetch_current(bearer(token + 'x')).code)
        self.assertEqual(403, self.fetch_current(bearer('meye_unknown')).code)

        apikeys.remove(key['id'])
        self.assertEqual(403, self.fetch_current(bearer(token)).code)

    def test_wrong_key_does_not_fall_back_to_the_session_cookie(self):
        headers = bearer('meye_unknown')
        headers['Cookie'] = self.make_session_cookie('admin')

        self.assertEqual(403, self.fetch_current(headers).code)

    def test_normal_key_is_kept_from_admin_only_cameras(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = True
        _, admin_token = apikeys.add('admin script', 'admin')
        _, normal_token = apikeys.add('viewer script', 'normal')

        self.assertEqual(403, self.fetch_current(bearer(normal_token)).code)
        self.assertEqual(200, self.fetch_current(bearer(admin_token)).code)

    def test_normal_key_is_kept_from_admin_endpoints(self):
        _, normal_token = apikeys.add('viewer script', 'normal')

        response = self.fetch('/config/main/get/', headers=bearer(normal_token))
        self.assertEqual(403, response.code)
        self.assertEqual('unauthorized', loads(response.body)['error'])


class ApiKeyHandlerTest(ApiKeyTestCase):
    handler_cls = ApiKeyHandler

    def admin(self):
        return {'Cookie': self.make_session_cookie('admin')}

    def post(self, path, body, headers):
        return self.fetch(
            path,
            method='POST',
            body=dumps(body),
            headers=dict(headers, **{'Content-Type': 'application/json'}),
        )

    def test_admin_adds_lists_and_removes_keys(self):
        response = self.post(
            '/apikey/add/', {'name': 'Home Assistant', 'role': 'normal'}, self.admin()
        )
        self.assertEqual(200, response.code)
        body = loads(response.body)
        token, key = body['token'], body['key']

        response = self.fetch('/apikey/list/', headers=self.admin())
        self.assertEqual(200, response.code)
        listed = loads(response.body)['keys']
        self.assertEqual([key], listed)
        self.assertNotIn(token, response.body.decode())
        self.assertEqual('normal', apikeys.verify(token))

        response = self.post(f'/apikey/{key["id"]}/rem/', {}, self.admin())
        self.assertEqual(200, response.code)
        self.assertIsNone(apikeys.verify(token))

        response = self.post(f'/apikey/{key["id"]}/rem/', {}, self.admin())
        self.assertEqual(404, response.code)

    def test_invalid_key_settings_are_refused(self):
        response = self.post(
            '/apikey/add/', {'name': '', 'role': 'admin'}, self.admin()
        )
        self.assertEqual(400, response.code)
        self.assertIn('name', loads(response.body)['error'])

        response = self.post(
            '/apikey/add/', {'name': 'x', 'role': 'root'}, self.admin()
        )
        self.assertEqual(400, response.code)

        self.assertEqual([], apikeys.list_keys())

    def test_only_the_admin_manages_keys(self):
        normal = {'Cookie': self.make_session_cookie('normal')}

        self.assertEqual(403, self.fetch('/apikey/list/').code)
        self.assertEqual(403, self.fetch('/apikey/list/', headers=normal).code)
        response = self.post('/apikey/add/', {'name': 'x', 'role': 'admin'}, normal)
        self.assertEqual(403, response.code)
        self.assertEqual([], apikeys.list_keys())

    def test_keys_cannot_manage_keys(self):
        key, token = apikeys.add('admin script', 'admin')

        response = self.fetch('/apikey/list/', headers=bearer(token))
        self.assertEqual(403, response.code)
        self.assertIn('API key', loads(response.body)['error'])

        response = self.post(
            '/apikey/add/', {'name': 'another', 'role': 'admin'}, bearer(token)
        )
        self.assertEqual(403, response.code)

        response = self.post(f'/apikey/{key["id"]}/rem/', {}, bearer(token))
        self.assertEqual(403, response.code)
        self.assertEqual(1, len(apikeys.list_keys()))

    def test_peers_cannot_manage_keys(self):
        with patch.object(ApiKeyHandler, 'get_current_user', return_value='peer'):
            self.assertEqual(403, self.fetch('/apikey/list/').code)


class DetectionActionTest(ApiKeyTestCase):
    def test_key_pauses_and_resumes_detection(self):
        # an alarm panel disarming and arming the cameras
        _, token = apikeys.add('alarm panel', 'normal')

        with patch(
            'motioneye.motionctl.set_motion_detection',
            new_callable=AsyncMock,
            return_value=None,
        ) as set_motion_detection:
            for action, state in (
                ('detectionpause', 'pause'),
                ('detectionstart', 'start'),
            ):
                response = self.fetch(
                    f'/action/1/{action}/',
                    method='POST',
                    body='',
                    headers=bearer(token),
                )
                self.assertEqual(200, response.code)
                self.assertEqual({'error': None}, loads(response.body))
                set_motion_detection.assert_awaited_with(1, state)


if __name__ == '__main__':
    tornado.testing.main()
