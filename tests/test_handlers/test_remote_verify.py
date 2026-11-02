from __future__ import annotations

from json import dumps, loads
from unittest.mock import AsyncMock, patch

import tornado.testing

from motioneye.handlers.config import ConfigHandler
from motioneye.utils import GetConfigResponse
from tests.test_handlers import _FAKE_REMOTE_CAMERA_CONFIG, RemoteCameraTestCase


def _remote_answers(ui_config=None, error=None):
    answer = GetConfigResponse(ui_config, error)
    return patch('motioneye.remote.get_config', AsyncMock(return_value=answer))


class RemoteVerifyTest(RemoteCameraTestCase):
    """The certificate check of a remote camera is a setting of the hub, not of the remote."""

    handler_cls = ConfigHandler

    def setUp(self):
        super().setUp()
        # an https remote with the check turned off, as the hub stores it
        self.camera = dict(
            _FAKE_REMOTE_CAMERA_CONFIG, **{'@scheme': 'https', '@remote_verify': False}
        )
        self._extra_patches = [
            patch('motioneye.config.get_main', return_value={'@enabled': True}),
            patch('motioneye.config.get_camera', return_value=self.camera),
            patch('motioneye.config.set_camera'),
        ]
        self.set_camera = self._extra_patches[-1].start()
        for p in self._extra_patches[:-1]:
            p.start()

    def tearDown(self):
        for p in self._extra_patches:
            p.stop()
        super().tearDown()

    def _post_as_admin(self, path, body):
        return self.fetch(
            path,
            method='POST',
            body=dumps(body),
            headers={'Cookie': self.make_session_cookie('admin')},
        )

    def test_the_camera_config_tells_whether_the_certificate_is_checked(self):
        with _remote_answers({'enabled': True, 'name': 'cam'}):
            response = self.fetch_as_admin('/config/1/get/')

        self.assertEqual(200, response.code)
        body = loads(response.body)
        self.assertEqual('cam', body['name'])
        self.assertIs(False, body['remote_verify'])

    def test_a_failed_connection_still_tells_it(self):
        with _remote_answers(error='certificate verify failed'):
            response = self.fetch_as_admin('/config/1/get/')

        self.assertEqual(200, response.code)
        body = loads(response.body)
        self.assertTrue(body['connection_failed'])
        self.assertIn('certificate verify failed', body['error'])
        self.assertIs(False, body['remote_verify'])

    def test_the_check_is_stored_locally_and_not_sent_to_the_remote(self):
        for value in (True, False):
            with self.subTest(remote_verify=value):
                self.camera['@remote_verify'] = not value
                ui_config = {'enabled': True, 'name': 'cam', 'remote_verify': value}
                set_config = AsyncMock(return_value=None)
                with patch('motioneye.remote.set_config', set_config):
                    response = self._post_as_admin('/config/1/set/', ui_config)

                self.assertEqual(200, response.code)
                stored = self.set_camera.call_args.args[1]
                self.assertIs(value, stored['@remote_verify'])
                sent = set_config.call_args.args[1]
                self.assertNotIn('remote_verify', sent)
                self.assertEqual('cam', sent['name'])

    def test_the_credentials_dialog_can_change_the_check(self):
        for value in (False, True):
            with self.subTest(remote_verify=value):
                self.camera['@remote_verify'] = not value
                body = {'url': 'https://cam.example:8765/', 'remote_verify': value}

                response = self._post_as_admin('/config/1/credentials/', body)

                self.assertEqual(200, response.code)
                stored = self.set_camera.call_args.args[1]
                self.assertEqual('https', stored['@scheme'])
                self.assertIs(value, stored['@remote_verify'])

    def test_the_credentials_dialog_keeps_the_check_when_it_says_nothing(self):
        self.camera['@remote_verify'] = True

        response = self._post_as_admin(
            '/config/1/credentials/', {'url': 'https://cam.example:8765/'}
        )

        self.assertEqual(200, response.code)
        self.assertIs(True, self.set_camera.call_args.args[1]['@remote_verify'])

    def test_only_an_admin_sees_the_check_in_the_camera_list(self):
        answers = {
            'reachable': {'ui_config': {'enabled': True, 'name': 'cam'}},
            'failed': {'error': 'certificate verify failed'},
        }
        for state, answer in answers.items():
            for user, shown in (('normal', False), ('admin', True)):
                with self.subTest(camera=state, user=user):
                    cookie = self.make_session_cookie(user)
                    with _remote_answers(**answer):
                        response = self.fetch(
                            '/config/list/', headers={'Cookie': cookie}
                        )

                    self.assertEqual(200, response.code)
                    camera = loads(response.body)['cameras'][0]
                    self.assertEqual(shown, 'remote_verify' in camera)
                    if shown:
                        self.assertIs(False, camera['remote_verify'])

    def test_a_failed_camera_in_the_list_still_tells_it(self):
        with _remote_answers(error='certificate verify failed'):
            response = self.fetch_as_admin('/config/list/')

        self.assertEqual(200, response.code)
        camera = loads(response.body)['cameras'][0]
        self.assertTrue(camera['connection_failed'])
        self.assertIs(False, camera['remote_verify'])


if __name__ == '__main__':
    tornado.testing.main()
