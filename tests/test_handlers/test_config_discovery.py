from json import loads
from unittest.mock import AsyncMock, patch

import tornado.testing

from motioneye.utils import GetCamerasResponse
from tests.test_handlers import HandlerTestCase

NAVIGATION = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
DISCOVERY = '/config/list/?proto=netcam&scheme=http&host=127.0.0.1&port=80&path=/'


class DiscoveryTest(HandlerTestCase):
    """Discovery connects to the address it is given, so with the SameSite=Lax
    session cookie a link from another site must not start it."""

    def _discover(self, accept):
        with patch(
            'motioneye.handlers.config.test_mjpeg_url',
            new=AsyncMock(return_value=GetCamerasResponse([], None)),
        ) as probe:
            response = self.fetch(
                DISCOVERY,
                headers={'Accept': accept, 'Cookie': self.make_session_cookie('admin')},
            )
        return response, probe

    def test_navigation_does_not_connect(self):
        response, probe = self._discover(NAVIGATION)
        self.assertEqual(403, response.code)
        probe.assert_not_called()

    def test_script_request_still_connects(self):
        response, probe = self._discover('*/*')
        self.assertEqual(200, response.code)
        self.assertEqual({'cameras': []}, loads(response.body))
        probe.assert_awaited_once()


if __name__ == '__main__':
    tornado.testing.main()
