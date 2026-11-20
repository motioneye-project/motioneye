from json import loads
from typing import ClassVar
from unittest.mock import patch

import tornado.testing

from motioneye import sendtelegram
from motioneye.handlers.relay_event import RelayEventHandler
from tests.test_handlers import HandlerTestCase

_RELAY_SECRET = 'relay-secret'


class RelayEventHandlerTest(HandlerTestCase):
    handler_cls = RelayEventHandler

    def get_httpserver_options(self):
        # Let the tests set the client address with the X-Real-Ip header.
        return {'xheaders': True}

    def setUp(self):
        super().setUp()
        self._relay_patches = [
            patch('motioneye.config.get_relay_secret', return_value=_RELAY_SECRET),
            # An unknown motion camera ID: an accepted event is then just ignored.
            patch(
                'motioneye.motionctl.motion_camera_id_to_camera_id', return_value=None
            ),
        ]
        for p in self._relay_patches:
            p.start()

    def tearDown(self):
        for p in self._relay_patches:
            p.stop()
        super().tearDown()

    def relay_event(self, client_ip, relay_secret=_RELAY_SECRET, cookie=None):
        headers = {
            'Content-Type': 'application/json',
            'X-Relay-Secret': relay_secret,
            'X-Real-Ip': client_ip,
        }
        if cookie:
            headers['Cookie'] = cookie
        return self.fetch(
            '/_relay_event/?event=start&motion_camera_id=1',
            method='POST',
            body='{}',
            headers=headers,
        )

    def test_loopback_allowed(self):
        self.assertEqual(200, self.relay_event('127.0.0.1').code)
        self.assertEqual(200, self.relay_event('::1').code)

    def test_invalid_secret_denied(self):
        response = self.relay_event('127.0.0.1', 'wrong')
        self.assertEqual(403, response.code)
        self.assertEqual('invalid_secret', loads(response.body)['error'])

    def test_non_local_denied(self):
        response = self.relay_event('192.0.2.10')
        self.assertEqual(403, response.code)
        self.assertEqual('unauthorized', loads(response.body)['error'])

    def test_non_local_admin_denied(self):
        cookie = self.make_session_cookie('admin')
        response = self.relay_event('192.0.2.10', cookie=cookie)
        self.assertEqual(403, response.code)
        self.assertEqual('unauthorized', loads(response.body)['error'])


class RelayMovieEndTest(HandlerTestCase):
    """The end of a movie sends it to Telegram, if the camera has that on (#3259)."""

    handler_cls = RelayEventHandler

    _CAMERA: ClassVar[dict] = {
        'target_dir': '/media/cam',
        'camera_name': 'Cam',
        '@upload_enabled': False,
        '@upload_movie': False,
    }

    def _movie_end(self, camera):
        with (
            patch('motioneye.config.get_relay_secret', return_value=_RELAY_SECRET),
            patch('motioneye.motionctl.motion_camera_id_to_camera_id', return_value=1),
            patch('motioneye.config.get_camera', return_value=camera),
            patch('motioneye.utils.is_local_motion_camera', return_value=True),
            patch('motioneye.tasks.add') as add,
        ):
            response = self.fetch(
                '/_relay_event/?event=movie_end&motion_camera_id=1'
                '&filename=/media/cam/2026-11-18/12-00-00.mp4',
                method='POST',
                body='{}',
                headers={'X-Relay-Secret': _RELAY_SECRET},
            )

        self.assertEqual(200, response.code)
        return {c.kwargs['tag']: c for c in add.call_args_list}

    def test_the_movie_is_sent_when_turned_on(self):
        camera = {**self._CAMERA, '@telegram_notifications_movies': 'True'}
        tasks = self._movie_end(camera)

        task = tasks['send_camera_movie(2026-11-18/12-00-00.mp4)']
        self.assertIs(sendtelegram.send_camera_movie, task.args[1])
        self.assertEqual(
            {'camera_id': 1, 'filename': '/media/cam/2026-11-18/12-00-00.mp4'},
            {k: v for k, v in task.kwargs.items() if k != 'tag'},
        )

    def test_not_when_turned_off(self):
        for camera in (
            self._CAMERA,
            {**self._CAMERA, '@telegram_notifications_movies': 'False'},
        ):
            with self.subTest(camera=camera):
                tasks = self._movie_end(camera)
                self.assertEqual(
                    ['make_movie_preview(2026-11-18/12-00-00.mp4)'], list(tasks)
                )


if __name__ == '__main__':
    tornado.testing.main()
