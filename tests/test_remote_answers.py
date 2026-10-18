from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from motioneye import remote, utils

_LOCAL_CONFIG = {
    '@proto': 'motioneye',
    '@host': 'hub.example',
    '@port': 8765,
    '@remote_camera_id': 2,
}


def _answer(body):
    return SimpleNamespace(error=None, code=200, body=json.dumps(body).encode())


class TestRemoteAnswerShapes(unittest.IsolatedAsyncioTestCase):
    """A remote's JSON answer of another shape than expected is an error, not an exception."""

    async def test_config_that_is_not_a_dict_is_an_error(self):
        for body in ([], 'x', 42, None):
            with patch.object(
                remote, '_send_request', AsyncMock(return_value=_answer(body))
            ):
                resp = await remote.get_config(_LOCAL_CONFIG)

            self.assertEqual('unexpected answer', resp.error, repr(body))
            self.assertIsNone(resp.remote_ui_config)

    async def test_camera_list_of_another_shape_is_an_error(self):
        for body in ([], {'cameras': 'x'}, {'cameras': [{'id': 1}, 'junk']}):
            with patch.object(
                remote, '_send_request', AsyncMock(return_value=_answer(body))
            ):
                resp = await remote.list_cameras(_LOCAL_CONFIG)

            self.assertEqual('unexpected answer', resp.error, repr(body))

    async def test_camera_list_entries_without_keys_are_tolerated(self):
        body = {
            'cameras': [
                {'enabled': True},
                {'id': 1, 'name': 'a', 'proto': 'mjpeg', 'enabled': True},
            ]
        }
        with patch.object(
            remote, '_send_request', AsyncMock(return_value=_answer(body))
        ):
            resp = await remote.list_cameras(_LOCAL_CONFIG)

        self.assertIsNone(resp.error)
        self.assertEqual([{'id': None, 'name': None}], resp.cameras)

    async def test_control_characters_in_a_remote_error_are_replaced(self):
        answer = _answer({})
        answer.error = utils.RemoteError('line one\r\nline two\x00')
        with patch.object(remote, '_send_request', AsyncMock(return_value=answer)):
            resp = await remote.get_config(_LOCAL_CONFIG)

        self.assertEqual('line one line two', resp.error)

    def test_pretty_http_error_replaces_control_characters(self):
        response = SimpleNamespace(
            code=500, error=Exception('HTTP 500: bad\nline\x1b[0m')
        )

        self.assertEqual('bad line [0m', utils.pretty_http_error(response))

    async def test_timelapse_status_that_is_not_a_dict_is_an_error(self):
        with patch.object(remote, '_send_request', AsyncMock(return_value=_answer([]))):
            resp = await remote.check_timelapse_movie(_LOCAL_CONFIG, group='g')

        self.assertEqual('unexpected answer', resp.error)
        self.assertIsNone(resp.result)
