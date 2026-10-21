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

    def relay_event(self, client_ip, relay_secret=_RELAY_SECRET):
        return self.fetch(
            '/_relay_event/?event=start&motion_camera_id=1',
            method='POST',
            body='{}',
            headers={
                'Content-Type': 'application/json',
                'X-Relay-Secret': relay_secret,
                'X-Real-Ip': client_ip,
            },
        )

    def test_loopback_allowed(self):
        self.assertEqual(200, self.relay_event('127.0.0.1').code)
        self.assertEqual(200, self.relay_event('::1').code)

    def test_invalid_secret_denied(self):
        response = self.relay_event('127.0.0.1', 'wrong')
        self.assertEqual(403, response.code)
        self.assertEqual('invalid_secret', loads(response.body)['error'])

    def test_other_address_denied(self):
        # The default `listen` setting (all interfaces) is not in the allowlist.
        response = self.relay_event('192.0.2.10')
        self.assertEqual(403, response.code)
        self.assertEqual('unauthorized', loads(response.body)['error'])

    def test_listen_address_allowed(self):
        with patch('motioneye.settings.LISTEN', '192.0.2.10'):
            self.assertEqual(200, self.relay_event('192.0.2.10').code)
            response = self.relay_event('192.0.2.11')
        self.assertEqual(403, response.code)
        self.assertEqual('unauthorized', loads(response.body)['error'])

    def test_listen_address_requires_secret(self):
        with patch('motioneye.settings.LISTEN', '192.0.2.10'):
            response = self.relay_event('192.0.2.10', 'wrong')
        self.assertEqual(403, response.code)
        self.assertEqual('invalid_secret', loads(response.body)['error'])


if __name__ == '__main__':
    tornado.testing.main()
