import json
from secrets import token_hex
from time import time
from unittest.mock import MagicMock, patch

import tornado.testing

from motioneye import config
from motioneye.handlers.base import BaseHandler
from motioneye.utils.authstate import generate_hmac_signature
from tests.test_handlers import HandlerTestCase


class BaseHandlerTest(HandlerTestCase):
    handler_cls = BaseHandler

    def test_get_argument(self):
        handler = self.get_handler(MagicMock(body='{"myarg":5}'))
        result = handler.get_argument('myarg')
        self.assertEqual(5, result)

    def test_get_argument_no_object_in_json(self):
        handler = self.get_handler(MagicMock(body='"{{{"'))
        with self.assertRaises(AttributeError):
            handler.get_argument('myarg')

    def test_get_argument_empty_json(self):
        handler = self.get_handler(MagicMock(body='""'))
        result = handler.get_argument('myarg')
        self.assertIsNone(result)

    def test_get_argument_invalid_json(self):
        handler = self.get_handler(MagicMock(body='{{{{'))
        with self.assertRaises(json.decoder.JSONDecodeError):
            handler.get_argument('myarg')

    def test_get_current_user_unauthenticated(self):
        # Without any auth credentials the handler returns None (no default user).
        handler = self.get_handler(MagicMock(body='""'))
        result = handler.get_current_user()
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    #  HMAC peer-authentication tests                                      #
    # ------------------------------------------------------------------ #

    def _make_hmac_request(
        self, secret, method, uri, body=b'', *, nonce=None, timestamp=None
    ):
        """Return a MagicMock request whose headers carry a valid HMAC signature."""
        ts = str(int(timestamp if timestamp is not None else time()))
        nc = nonce or token_hex(16)
        body_arg = body if body else None
        sig = generate_hmac_signature(secret, method, uri, ts, nc, body_arg)

        request = MagicMock()
        request.cookies = {}
        request.method = method
        request.uri = uri
        request.body = body

        _headers = {
            'X-HMAC-Signature': sig,
            'X-Timestamp': ts,
            'X-Nonce': nc,
        }
        request.headers.get = lambda name, default=None: _headers.get(name, default)
        return request

    def test_get_current_user_peer_valid_hmac(self):
        """A request with a valid HMAC signature is authenticated as 'peer'."""
        secret = 'unit-test-secret-' + token_hex(8)
        request = self._make_hmac_request(secret, 'GET', '/api/config/main/get')

        with patch.object(config, '_main_config_cache', {'@client_secret': secret}):
            handler = self.get_handler(request)
            result = handler.get_current_user()

        self.assertEqual('peer', result)

    def test_get_current_user_peer_invalid_signature(self):
        """A request with a tampered HMAC signature is rejected (returns None)."""
        secret = 'unit-test-secret-' + token_hex(8)
        request = self._make_hmac_request(secret, 'GET', '/api/config/main/get')

        # Overwrite the signature header with garbage
        original_get = request.headers.get
        request.headers.get = lambda name, default=None: (
            'deadbeef' if name == 'X-HMAC-Signature' else original_get(name, default)
        )

        with patch.object(config, '_main_config_cache', {'@client_secret': secret}):
            handler = self.get_handler(request)
            result = handler.get_current_user()

        self.assertIsNone(result)

    def test_get_current_user_peer_expired_timestamp(self):
        """A request whose timestamp is older than 10 minutes is rejected."""
        secret = 'unit-test-secret-' + token_hex(8)
        request = self._make_hmac_request(
            secret, 'GET', '/api/config/main/get', timestamp=time() - 700
        )

        with patch.object(config, '_main_config_cache', {'@client_secret': secret}):
            handler = self.get_handler(request)
            result = handler.get_current_user()

        self.assertIsNone(result)

    def test_get_current_user_peer_no_client_secret(self):
        """HMAC auth fails gracefully when no client_secret is configured."""
        secret = 'unit-test-secret-' + token_hex(8)
        request = self._make_hmac_request(secret, 'GET', '/api/config/main/get')

        # Config has no @client_secret entry
        with patch.object(config, '_main_config_cache', {}):
            handler = self.get_handler(request)
            result = handler.get_current_user()

        self.assertIsNone(result)


if __name__ == '__main__':
    tornado.testing.main()
