from __future__ import annotations

from json import loads
from secrets import token_hex
from time import time
from unittest.mock import AsyncMock, MagicMock, patch

import tornado.testing

from motioneye import mediafiles
from motioneye.handlers.picture import PictureHandler
from motioneye.utils.authstate import generate_hmac_signature
from tests.test_handlers import _FAKE_CAMERA_CONFIG, HandlerTestCase

_ALLOWED = {**_FAKE_CAMERA_CONFIG, 'movie_codec': 'mp4:h264'}
_ADMIN_ONLY = {**_ALLOWED, '@id': 2, '@admin_only': True, 'camera_name': 'private'}

_START = 'timelapse/g/?interval=60&framerate=20'
_SECRET = 'a-hub-signs-with-this'
# a hub's users all come as the peer, which no admin-only setting holds back
_OTHERS = ('normal', 'peer')
_BUSY = 'a timelapse movie of another camera is being made'


def _running(progress):
    process = MagicMock(spec=['poll', 'progress'])
    process.poll.return_value = None
    process.progress = progress
    return process


def _no_media_state():
    return patch.multiple(
        mediafiles,
        _prepared_files={},
        _timelapse_process=None,
        _timelapse_data=None,
        _timelapse_camera_id=None,
    )


class PreparedFilesPerCameraTest(HandlerTestCase):
    """A zip or timelapse of an admin-only camera never comes out through another camera."""

    handler_cls = PictureHandler

    def setUp(self):
        super().setUp()
        cameras = {1: _ALLOWED, 2: _ADMIN_ONLY}
        self._camera_patches = [
            patch('motioneye.config.get_camera_ids', return_value=[1, 2]),
            patch('motioneye.config.get_camera', side_effect=cameras.get),
            patch(
                'motioneye.config.get_main', return_value={'@client_secret': _SECRET}
            ),
            _no_media_state(),
        ]
        for p in self._camera_patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._camera_patches):
            p.stop()
        super().tearDown()

    def _get(self, path, user):
        uri = '/picture/' + path
        if user != 'peer':
            headers = {'Cookie': self.make_session_cookie(user)}

        else:
            timestamp, nonce = str(int(time())), token_hex(16)
            headers = {
                'X-HMAC-Signature': generate_hmac_signature(
                    _SECRET, 'GET', uri, timestamp, nonce, None
                ),
                'X-Timestamp': timestamp,
                'X-Nonce': nonce,
            }

        return self.fetch(uri, headers={'Accept': '*/*', **headers})

    def test_check_gives_no_key_for_another_camera_movie(self):
        mediafiles._timelapse_camera_id = 2
        mediafiles._timelapse_data = b'private movie'

        for user in _OTHERS:
            with self.subTest(user=user):
                response = self._get('1/timelapse/g/?check=true', user)

                self.assertEqual(200, response.code)
                self.assertEqual({'progress': -1, 'data': None}, loads(response.body))
                self.assertEqual({}, mediafiles._prepared_files)

    def test_check_shows_no_progress_of_another_camera(self):
        mediafiles._timelapse_camera_id = 2
        mediafiles._timelapse_process = _running(0.5)

        for user in _OTHERS:
            with self.subTest(user=user):
                response = self._get('1/timelapse/g/?check=true', user)

                self.assertEqual({'progress': -1, 'data': None}, loads(response.body))

    def test_timelapse_key_works_only_through_its_camera(self):
        mediafiles._timelapse_camera_id = 2
        mediafiles._timelapse_data = b'private movie'
        key = loads(self._get('2/timelapse/g/?check=true', 'admin').body)['key']

        for user in _OTHERS:
            with self.subTest(user=user):
                response = self._get(f'1/timelapse/g/?key={key}', user)
                self.assertEqual(404, response.code)

        # the wrong camera did not use the key up
        response = self._get(f'2/timelapse/g/?key={key}', 'admin')
        self.assertEqual(200, response.code)
        self.assertEqual(b'private movie', response.body)

    def test_zip_key_works_only_through_its_camera(self):
        with patch.object(
            mediafiles, 'get_zipped_content', AsyncMock(return_value=b'private zip')
        ):
            key = loads(self._get('2/zipped/g/', 'admin').body)['key']

        for user in _OTHERS:
            with self.subTest(user=user):
                response = self._get(f'1/zipped/g/?key={key}', user)
                self.assertEqual(404, response.code)

        response = self._get(f'2/zipped/g/?key={key}', 'admin')
        self.assertEqual(200, response.code)
        self.assertEqual(b'private zip', response.body)

    def test_start_while_another_camera_runs_is_an_error(self):
        mediafiles._timelapse_camera_id = 2
        mediafiles._timelapse_process = _running(0.5)

        for user in _OTHERS:
            with (
                self.subTest(user=user),
                patch.object(mediafiles, 'make_timelapse_movie') as make,
            ):
                response = self._get('1/' + _START, user)

                self.assertEqual({'error': _BUSY}, loads(response.body))
                make.assert_not_called()

    def test_start_while_the_same_camera_runs_gives_its_progress(self):
        mediafiles._timelapse_camera_id = 2
        mediafiles._timelapse_process = _running(0.5)

        with patch.object(mediafiles, 'make_timelapse_movie') as make:
            response = self._get('2/' + _START, 'admin')

        self.assertEqual({'progress': 0.5}, loads(response.body))
        make.assert_not_called()


class ForgetReusedIdTest(HandlerTestCase):
    """Camera ids are reused, so nothing prepared is kept when the cameras change."""

    def setUp(self):
        super().setUp()
        self._state = _no_media_state()
        self._state.start()

    def tearDown(self):
        self._state.stop()
        super().tearDown()

    def _post(self, path, **kwargs):
        headers = {'Cookie': self.make_session_cookie('admin')}
        headers.update(kwargs.pop('headers', {}))
        return self.fetch(path, method='POST', headers=headers, **kwargs)

    def _fill(self):
        mediafiles._prepared_files.update({(1, 'a'): b'one', (2, 'b'): b'two'})
        mediafiles._timelapse_camera_id = 1
        mediafiles._timelapse_data = b'movie'

    def _assert_forgotten(self):
        self.assertEqual({}, mediafiles._prepared_files)
        self.assertEqual(
            {'progress': -1, 'data': None}, mediafiles.check_timelapse_movie(1)
        )

    def test_removing_a_camera_forgets_the_movie_and_files(self):
        self._fill()

        with (
            patch('motioneye.config.rem_camera'),
            patch('motioneye.motionctl.stop'),
            patch('motioneye.motionctl.start'),
        ):
            response = self._post('/config/1/rem', body='')

        self.assertEqual(200, response.code)
        self._assert_forgotten()

    def test_adding_a_camera_forgets_the_movie_and_files(self):
        # the cameras are read anew then, also after a restore that failed halfway
        self._fill()

        with (
            patch('motioneye.config.add_camera', return_value=_FAKE_CAMERA_CONFIG),
            patch('motioneye.config.motion_camera_dict_to_ui', return_value={}),
            patch('motioneye.motionctl.stop'),
            patch('motioneye.motionctl.start'),
        ):
            response = self._post('/config/add', body='{}')

        self.assertEqual(200, response.code)
        self._assert_forgotten()

    def test_a_restore_forgets_every_camera(self):
        body = (
            '--b\r\n'
            'Content-Disposition: form-data; name="files"; filename="backup.tar.gz"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n'
            'backup\r\n'
            '--b--\r\n'
        )

        # without a reboot (the default) motionEye keeps running with what it holds,
        # and a restore that fails may have replaced some cameras already
        for result, answer in (
            ({'reboot': False}, {'ok': True, 'reboot': False}),
            ({'reboot': True}, {'ok': True, 'reboot': True}),
            (None, {'ok': False}),
        ):
            with self.subTest(result=result):
                self._fill()

                with (
                    patch('motioneye.config.restore', return_value=result),
                    patch('motioneye.migration.migrate_cameras'),
                ):
                    response = self._post(
                        '/config/restore',
                        body=body,
                        headers={'Content-Type': 'multipart/form-data; boundary=b'},
                    )

                self.assertEqual(answer, loads(response.body))
                self._assert_forgotten()


if __name__ == '__main__':
    tornado.testing.main()
