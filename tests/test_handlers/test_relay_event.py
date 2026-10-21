from json import loads
from unittest.mock import patch

import tornado.testing

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


if __name__ == '__main__':
    tornado.testing.main()
