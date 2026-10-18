from __future__ import annotations

from unittest.mock import AsyncMock, patch
from urllib.parse import quote

from motioneye.handlers.picture import PictureHandler
from motioneye.utils import GetCurrentPictureResponse
from tests.test_handlers import RemoteCameraTestCase


class RemoteCurrentPictureTest(RemoteCameraTestCase):
    """The hub re-sends a remote camera's monitor info as one encoded cookie value."""

    handler_cls = PictureHandler

    def fetch_current(self, monitor_info):
        answer = GetCurrentPictureResponse(
            motion_detected=False,
            capture_fps=2.0,
            monitor_info=monitor_info,
            picture=b'jpg',
        )
        with patch(
            'motioneye.remote.get_current_picture', AsyncMock(return_value=answer)
        ):
            return self.fetch_as_admin('/picture/1/current/')

    def monitor_cookie(self, response):
        for cookie in response.headers.get_list('Set-Cookie'):
            if cookie.startswith('monitor_info_1='):
                return cookie.split(';')[0]
        return None

    def test_monitor_info_is_sent_fully_encoded(self):
        response = self.fetch_current('<b>x</b>; other_cookie=1')

        self.assertEqual(200, response.code)
        self.assertEqual(b'jpg', response.body)
        self.assertEqual(
            'monitor_info_1=' + quote('<b>x</b>; other_cookie=1', safe=''),
            self.monitor_cookie(response),
        )

    def test_an_already_encoded_monitor_info_is_sent_as_it_is(self):
        encoded = quote('load: 0.5', safe='')
        response = self.fetch_current(encoded)

        self.assertEqual('monitor_info_1=' + encoded, self.monitor_cookie(response))
