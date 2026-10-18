from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tornado.httputil import HTTPHeaders

from motioneye import remote

_LOCAL_CONFIG = {
    '@proto': 'motioneye',
    '@host': 'hub.example',
    '@port': 8765,
    '@remote_camera_id': 2,
}


def _answer(cookies, error=None):
    headers = HTTPHeaders()
    for cookie in cookies:
        headers.add('Set-Cookie', cookie)

    return SimpleNamespace(
        error=error, code=200 if error is None else 500, body=b'jpg', headers=headers
    )


class TestRemoteGetCurrentPicture(unittest.IsolatedAsyncioTestCase):
    """The cookies a remote camera sends with its picture are taken with care."""

    async def _get(self, answer):
        with patch.object(remote, '_send_request', AsyncMock(return_value=answer)):
            return await remote.get_current_picture(
                _LOCAL_CONFIG, width=None, height=None
            )

    async def test_frame_rate_that_is_not_a_number_counts_as_zero(self):
        resp = await self._get(_answer(['capture_fps_2=abc', 'monitor_info_2=load']))

        self.assertIsNone(resp.error)
        self.assertEqual(0.0, resp.capture_fps)
        self.assertEqual('load', resp.monitor_info)
        self.assertEqual(b'jpg', resp.picture)

    async def test_frame_rate_that_is_not_finite_or_negative_counts_as_zero(self):
        for value in ('inf', 'nan', '-1'):
            resp = await self._get(_answer(['capture_fps_2=' + value]))

            self.assertEqual(0.0, resp.capture_fps, value)

    async def test_cookies_of_an_error_answer_are_not_read(self):
        resp = await self._get(_answer(['capture_fps_2=abc'], error=Exception('boom')))

        self.assertEqual('boom', resp.error)
        self.assertIsNone(resp.picture)
