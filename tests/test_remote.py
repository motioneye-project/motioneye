# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the remote module functions."""

from __future__ import annotations

import inspect
import json
import ssl
import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock, patch

from tornado.httputil import HTTPHeaders

from motioneye import remote


class TestRemotePathTraversal(unittest.IsolatedAsyncioTestCase):
    """Tests verifying that path traversal elements are rejected in remote functions.

    Each remote function performs its path traversal check synchronously before
    any network I/O, so awaiting the coroutine raises immediately.
    """

    _LOCAL_CONFIG: ClassVar[dict[str, str | int]] = {
        '@proto': 'mjpeg',
        '@host': '127.0.0.1',
        '@port': 8765,
        '@username': '',
        '@password': '',
        '@path': '',
        '@remote_camera_id': 1,
    }

    # Traversal inputs to test for filenames/paths and groups/prefixes.
    _FILENAME_TRAVERSALS: ClassVar[list[str]] = [
        '../etc/passwd',
        '../../etc/passwd',
        'subdir/../../../etc/passwd',
        '../secret.jpg',
    ]
    _GROUP_TRAVERSALS: ClassVar[list[str]] = [
        '..',
        '../group',
        'subdir/..',
        'subdir/../../other',
    ]
    _PREFIX_TRAVERSALS: ClassVar[list[str]] = [
        '..',
        '../prefix',
        'prefix/../..',
    ]

    def _assert_raises_path_traversal(self, exception):
        self.assertIn('Path traversal', str(exception))

    async def test_list_media_rejects_prefix_traversal(self):
        for prefix in self._PREFIX_TRAVERSALS:
            with self.subTest(prefix=prefix):
                with self.assertRaises(Exception) as ctx:
                    await remote.list_media(
                        self._LOCAL_CONFIG, 'picture', prefix=prefix
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_media_content_rejects_traversal(self):
        for filename in self._FILENAME_TRAVERSALS:
            with self.subTest(filename=filename):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_media_content(
                        self._LOCAL_CONFIG, filename, 'picture'
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_make_zipped_content_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.make_zipped_content(
                        self._LOCAL_CONFIG, 'picture', group
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_zipped_content_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_zipped_content(
                        self._LOCAL_CONFIG, 'picture', 'key123', group
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_make_timelapse_movie_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.make_timelapse_movie(self._LOCAL_CONFIG, 2, 1, group)
                self._assert_raises_path_traversal(ctx.exception)

    async def test_check_timelapse_movie_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.check_timelapse_movie(self._LOCAL_CONFIG, group)
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_timelapse_movie_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_timelapse_movie(
                        self._LOCAL_CONFIG, 'key123', group
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_media_preview_rejects_traversal(self):
        for filename in self._FILENAME_TRAVERSALS:
            with self.subTest(filename=filename):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_media_preview(
                        self._LOCAL_CONFIG, filename, 'picture', None, None
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_del_media_content_rejects_traversal(self):
        for filename in self._FILENAME_TRAVERSALS:
            with self.subTest(filename=filename):
                with self.assertRaises(Exception) as ctx:
                    await remote.del_media_content(
                        self._LOCAL_CONFIG, filename, 'picture'
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_del_media_group_rejects_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.del_media_group(self._LOCAL_CONFIG, group, 'picture')
                self._assert_raises_path_traversal(ctx.exception)


def _http_answer(body, content_type='application/json'):
    return patch.object(
        remote,
        'AsyncHTTPClient',
        return_value=SimpleNamespace(
            fetch=AsyncMock(
                return_value=SimpleNamespace(
                    code=200,
                    body=body,
                    headers={'Content-Type': content_type},
                    error=None,
                )
            )
        ),
    )


class TestRemoteGetConfig(unittest.IsolatedAsyncioTestCase):
    """Tests for get_config() answers."""

    _LOCAL_CONFIG: ClassVar[dict[str, str | int]] = {
        '@proto': 'motioneye',
        '@host': 'hub.example',
        '@port': 8765,
        '@remote_camera_id': 2,
    }

    @staticmethod
    def _answer(body):
        return SimpleNamespace(error=None, body=json.dumps(body).encode())

    async def test_error_payload_is_returned_as_error(self):
        # answer of a remote motionEye which cannot reach its own camera
        error = 'Failed to connect to cam.example:8765'
        body = {
            'error': error,
            'connection_failed': True,
            'connection_url': 'http://cam.example:8765',
        }
        with _http_answer(json.dumps(body).encode()):
            resp = await remote.get_config(self._LOCAL_CONFIG)

        self.assertIsNone(resp.remote_ui_config)
        self.assertEqual(error, resp.error)

    async def test_camera_config_is_returned_with_host_and_port(self):
        body = {'enabled': True, 'name': 'cam'}
        with patch.object(
            remote, '_send_request', AsyncMock(return_value=self._answer(body))
        ):
            resp = await remote.get_config(self._LOCAL_CONFIG)

        self.assertIsNone(resp.error)
        self.assertEqual(
            {'enabled': True, 'name': 'cam', 'host': 'hub.example', 'port': 8765},
            resp.remote_ui_config,
        )

    async def test_empty_error_is_not_an_error(self):
        body = {'enabled': True, 'error': None}
        with patch.object(
            remote, '_send_request', AsyncMock(return_value=self._answer(body))
        ):
            resp = await remote.get_config(self._LOCAL_CONFIG)

        self.assertIsNone(resp.error)
        self.assertTrue(resp.remote_ui_config['enabled'])

    async def test_set_streaming_password_is_left_out(self):
        # older remotes send it masked, an unset one is empty
        for sent, expected in (('*****', {}), ('', {'streaming_password': ''})):
            body = {'streaming_username': 'viewer', 'streaming_password': sent}
            with patch.object(
                remote, '_send_request', AsyncMock(return_value=self._answer(body))
            ):
                resp = await remote.get_config(self._LOCAL_CONFIG)

            expected.update(streaming_username='viewer', host='hub.example', port=8765)
            self.assertEqual(expected, resp.remote_ui_config)


class TestRemoteErrorAnswers(unittest.IsolatedAsyncioTestCase):
    """A remote motionEye answers some failures with 200 and an error in the body."""

    _LOCAL_CONFIG: ClassVar[dict[str, str | int]] = {
        '@proto': 'motioneye',
        '@host': 'hub.example',
        '@port': 8765,
        '@remote_camera_id': 2,
    }

    async def test_failed_test_is_an_error(self):
        with _http_answer(json.dumps({'error': 'check SMTP port'}).encode()):
            resp = await remote.test(self._LOCAL_CONFIG, {'what': 'email'})

        self.assertEqual('check SMTP port', resp.error)

    async def test_failed_set_is_an_error(self):
        error = 'Failed to connect to cam.example:8765'
        with _http_answer(
            json.dumps({'reload': False, 'reboot': False, 'error': error}).encode(),
            content_type='application/json; charset=UTF-8',
        ):
            result = await remote.set_config(self._LOCAL_CONFIG, {'name': 'cam'})

        self.assertEqual(error, result)

    async def test_set_with_an_empty_error_succeeds(self):
        with _http_answer(
            json.dumps({'reload': False, 'reboot': False, 'error': None}).encode(),
            content_type='application/json; charset=UTF-8',
        ):
            result = await remote.set_config(self._LOCAL_CONFIG, {'name': 'cam'})

        self.assertIsNone(result)

    async def test_error_of_a_camera_further_away_is_kept_as_it_is(self):
        error = (
            'failed to get remote camera config for http://far.example:8765/config/1: '
            'request timed out'
        )
        with _http_answer(json.dumps({'error': error}).encode()):
            resp = await remote.get_config(self._LOCAL_CONFIG)

        self.assertEqual(error, resp.error)

    async def test_failed_list_is_an_error(self):
        with _http_answer(json.dumps({'error': 'motion is not running'}).encode()):
            resp = await remote.list_cameras(self._LOCAL_CONFIG)

        self.assertIsNone(resp.cameras)
        self.assertEqual('motion is not running', resp.error)

    async def test_other_answers_are_not_parsed(self):
        with _http_answer(b'\xff\xd8\xff\xe0', content_type='image/jpeg'):
            response = await remote._send_request(None)

        self.assertIsNone(response.error)


class TestRemoteVerifyCertificate(unittest.IsolatedAsyncioTestCase):
    """Requests to a remote motionEye verify its certificate unless the camera says not to."""

    _LOCAL_CONFIG: ClassVar[dict[str, str | int]] = {
        '@proto': 'motioneye',
        '@scheme': 'https',
        '@host': 'hub.example',
        '@port': 8765,
        '@remote_secret': 'secret',
        '@remote_camera_id': 2,
    }

    # every function that talks to the remote, with the arguments it needs
    _CALLS: ClassVar[dict[str, tuple]] = {
        'list_cameras': (),
        'get_config': (),
        'set_config': ({'name': 'cam'},),
        'test': ({'what': 'email'},),
        'get_current_picture': (None, None),
        'list_media': ('picture',),
        'get_media_content': ('a.jpg', 'picture'),
        'make_zipped_content': ('picture', 'group'),
        'get_zipped_content': ('picture', 'key123', 'group'),
        'make_timelapse_movie': (2, 1, 'group'),
        'check_timelapse_movie': ('group',),
        'get_timelapse_movie': ('key123', 'group'),
        'get_media_preview': ('a.jpg', 'picture'),
        'del_media_content': ('a.jpg', 'picture'),
        'del_media_group': ('group', 'picture'),
        'exec_action': ('snapshot',),
    }

    @staticmethod
    def _answer():
        # an answer each of the functions can take
        return SimpleNamespace(
            error=None,
            code=200,
            body=b'{"cameras": [], "key": "k"}',
            headers=HTTPHeaders({'Content-Type': 'application/json'}),
        )

    async def _assert_every_request_verifies(self, local_config, expected):
        send = AsyncMock(return_value=self._answer())
        with patch.object(remote, '_send_request', send):
            for name, args in self._CALLS.items():
                with self.subTest(function=name):
                    await getattr(remote, name)(local_config, *args)

                    self.assertIs(expected, send.call_args.args[0].validate_cert)

    def test_every_function_of_the_module_is_covered(self):
        functions = {
            name
            for name, value in vars(remote).items()
            if inspect.iscoroutinefunction(value) and not name.startswith('_')
        }

        self.assertEqual(functions, set(self._CALLS))

    async def test_the_certificate_is_verified_by_default(self):
        await self._assert_every_request_verifies(self._LOCAL_CONFIG, True)

    async def test_the_certificate_is_verified_when_the_camera_says_so(self):
        local_config = dict(self._LOCAL_CONFIG, **{'@remote_verify': True})

        await self._assert_every_request_verifies(local_config, True)

    async def test_the_certificate_check_can_be_turned_off_per_camera(self):
        local_config = dict(self._LOCAL_CONFIG, **{'@remote_verify': False})

        await self._assert_every_request_verifies(local_config, False)

    async def test_the_add_camera_dialog_can_turn_the_check_off(self):
        # camera discovery sends the dialog's fields without the '@', as booleans
        # from the JSON body or as strings from the deprecated query string
        for value, expected in ((False, False), ('false', False), ('true', True)):
            with self.subTest(remote_verify=value):
                details = {
                    'scheme': 'https',
                    'host': 'hub.example',
                    'port': 8765,
                    'remote_verify': value,
                }
                send = AsyncMock(return_value=self._answer())
                with patch.object(remote, '_send_request', send):
                    await remote.list_cameras(details)

                self.assertIs(expected, send.call_args.args[0].validate_cert)

    def test_the_flag_is_read_the_way_the_dialogs_send_it(self):
        for value, expected in (
            (None, True),
            (True, True),
            (False, False),
            ('true', True),
            ('on', True),
            ('1', True),
            ('false', False),
            ('off', False),
            ('0', False),
            ('no', False),
            ('', True),
            ('maybe', True),
            (' False ', False),
        ):
            with self.subTest(remote_verify=value):
                self.assertIs(expected, remote._verify_flag({'remote_verify': value}))

        self.assertIs(True, remote._verify_flag({}))
        stored = {'@remote_verify': False, 'remote_verify': True}
        self.assertIs(False, remote._verify_flag(stored))

    async def test_a_certificate_failure_is_shown_verbatim(self):
        failure = ssl.SSLCertVerificationError(
            1,
            '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: '
            'self-signed certificate',
        )
        client = SimpleNamespace(fetch=AsyncMock(side_effect=failure))
        failing_client = patch.object(remote, 'AsyncHTTPClient', return_value=client)
        with failing_client, self.assertLogs(level='ERROR'):
            resp = await remote.get_config(self._LOCAL_CONFIG)

        self.assertIsNone(resp.remote_ui_config)
        self.assertIn('CERTIFICATE_VERIFY_FAILED', resp.error)
        self.assertIn('self-signed certificate', resp.error)


if __name__ == '__main__':
    unittest.main()
