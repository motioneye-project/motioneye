from json import dumps
from secrets import token_hex
from time import time
from unittest.mock import patch

import tornado.testing

from motioneye import config
from motioneye.utils.authstate import generate_hmac_signature
from tests.test_handlers import HandlerTestCase

_SECRET = 'peer-test-secret'
_MAIN_CONFIG = {
    '@admin_username': 'admin',
    '@admin_password': 'old-hash',
    '@normal_username': 'user',
    '@normal_password': '',
    '@client_secret': _SECRET,
}


class PeerMainConfigTest(HandlerTestCase):
    def setUp(self):
        super().setUp()
        self._main_patch = patch.object(config, 'get_main', return_value=_MAIN_CONFIG)
        self._main_patch.start()

    def tearDown(self):
        self._main_patch.stop()
        super().tearDown()

    def _peer_fetch(self, method, uri, body=None):
        timestamp = str(int(time()))
        nonce = token_hex(16)
        body_bytes = body.encode() if body is not None else None
        signature = generate_hmac_signature(
            _SECRET, method, uri, timestamp, nonce, body_bytes
        )
        return self.fetch(
            uri,
            method=method,
            body=body_bytes,
            headers={
                'X-HMAC-Signature': signature,
                'X-Timestamp': timestamp,
                'X-Nonce': nonce,
            },
        )

    def test_peer_can_still_get_camera_config(self):
        with patch.object(config, 'motion_camera_dict_to_ui', return_value={'id': 1}):
            response = self._peer_fetch('GET', '/config/1/get/')
        self.assertEqual(200, response.code)

    def test_peer_denied_main_get(self):
        with patch.object(config, 'main_dict_to_ui') as main_dict_to_ui:
            response = self._peer_fetch('GET', '/config/main/get/')
        self.assertEqual(403, response.code)
        main_dict_to_ui.assert_not_called()

    def test_peer_denied_main_get_via_camera_id_zero(self):
        with patch.object(config, 'main_dict_to_ui') as main_dict_to_ui:
            response = self._peer_fetch('GET', '/config/0/get/')
        self.assertEqual(403, response.code)
        main_dict_to_ui.assert_not_called()

    def test_peer_denied_main_set(self):
        body = dumps({'admin_username': 'admin', 'admin_password': 'pwned'})
        with patch.object(config, 'set_main') as set_main:
            response = self._peer_fetch('POST', '/config/main/set/', body)
        self.assertEqual(403, response.code)
        set_main.assert_not_called()

    def test_peer_denied_main_set_in_batched_body(self):
        body = dumps(
            {
                'main': {'admin_username': 'admin', 'admin_password': 'pwned'},
                '1': {'enabled': True},
            }
        )
        with patch.object(config, 'set_main') as set_main, patch.object(
            config, 'set_camera'
        ) as set_camera:
            response = self._peer_fetch('POST', '/config/0/set/', body)
        self.assertEqual(403, response.code)
        set_main.assert_not_called()
        set_camera.assert_not_called()


if __name__ == '__main__':
    tornado.testing.main()
