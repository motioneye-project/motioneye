import json
from email.utils import parsedate_to_datetime
from hashlib import sha1
from http.cookies import SimpleCookie
from unittest.mock import patch

import tornado.testing
from argon2 import PasswordHasher

from motioneye import config, settings
from motioneye.handlers.base import _session_store
from motioneye.handlers.login import LoginHandler
from tests.test_handlers import HandlerTestCase

ph = PasswordHasher()


class LoginHandlerTest(HandlerTestCase):
    handler_cls = LoginHandler

    def test_get_login_no_params(self):
        # without a session the endpoint should require authentication
        response = self.fetch('/login')
        self.assertEqual(403, response.code)
        self.assertEqual('application/json', response.headers.get('Content-Type'))
        self.assertEqual(
            {'error': 'unauthorized', 'prompt': True}, json.loads(response.body)
        )

    def test_get_login_success(self):
        # login first to obtain session cookie
        admin_user = 'admin'
        admin_pass = 's3cret'
        hashed_pass = ph.hash(admin_pass)
        main_config = {
            '@admin_username': admin_user,
            '@admin_password': hashed_pass,
            '@normal_username': '',
            '@normal_password': '',
        }
        with patch.object(config, '_main_config_cache', main_config):
            response = self.fetch(
                '/login',
                method='POST',
                body=f'username={admin_user}&password={admin_pass}',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            )
            self.assertEqual(200, response.code)
            body = json.loads(response.body)
            self.assertIn('user', body)
            cookie = response.headers.get('Set-Cookie', '')

            # use session cookie to access GET /login
            response2 = self.fetch('/login', headers={'Cookie': cookie})
            self.assertEqual(200, response2.code)
            body2 = json.loads(response2.body)
            self.assertIn('user', body2)
            self.assertIn('username', body2)

    def test_get_login_fail(self):
        response = self.fetch('/login?_admin=true')
        self.assertEqual(403, response.code)
        self.assertEqual('application/json', response.headers.get('Content-Type'))
        self.assertEqual(
            {'error': 'unauthorized', 'prompt': True}, json.loads(response.body)
        )

    def test_login_with_empty_password(self):
        admin_user = 'admin'
        main_config = {
            '@admin_username': admin_user,
            '@admin_password': '',
            '@normal_username': '',
            '@normal_password': '',
        }
        with patch.object(config, '_main_config_cache', main_config):
            response = self.fetch(
                '/login',
                method='POST',
                body=f'username={admin_user}&password=',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            )
            self.assertEqual(200, response.code)
            self.assertIn('user', json.loads(response.body))

    def test_login_legacy_password_migrates(self):
        admin_user = 'admin'
        plain = 's3cret'
        legacy_hash = sha1(plain.encode()).hexdigest()  # nosec B324
        main_config = {
            '@admin_username': admin_user,
            '@admin_password': legacy_hash,
            '@normal_username': '',
            '@normal_password': '',
        }
        with patch.object(config, '_main_config_cache', main_config):
            with patch.object(config, 'set_admin_password') as mock_set_admin:
                response = self.fetch(
                    '/login',
                    method='POST',
                    body=f'username={admin_user}&password={plain}',
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                )
                self.assertEqual(200, response.code)
                mock_set_admin.assert_called_once_with(plain)

    def test_login_plaintext_normal_password_migrates(self):
        admin_user = 'admin'
        normal_user = 'user'
        normal_plain = 'watcher'
        main_config = {
            '@admin_username': admin_user,
            '@admin_password': ph.hash('adminpass'),
            '@normal_username': normal_user,
            '@normal_password': normal_plain,
        }
        with patch.object(config, '_main_config_cache', main_config):
            with patch.object(config, 'set_normal_password') as mock_set_normal:
                response = self.fetch(
                    '/login',
                    method='POST',
                    body=f'username={normal_user}&password={normal_plain}',
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                )
                self.assertEqual(200, response.code)
                mock_set_normal.assert_called_once_with(normal_plain)

    def _assert_session_lifetime(
        self, response, user_type: str, expected_seconds: int
    ) -> None:
        response_date = parsedate_to_datetime(response.headers['Date'])
        cookie = SimpleCookie()
        cookie.load(response.headers.get('Set-Cookie', ''))
        cookie_expires = parsedate_to_datetime(cookie['user']['expires'])

        self.assertAlmostEqual(
            expected_seconds,
            (cookie_expires - response_date).total_seconds(),
            delta=1,
        )

        self.assertEqual(1, len(_session_store))
        session = next(iter(_session_store.values()))
        self.assertEqual(user_type, session['user'])
        self.assertAlmostEqual(cookie_expires.timestamp(), session['expires'], delta=1)

    def test_normal_session_lifetime_configurable(self):
        normal_user = 'user'
        normal_pass = 'watcher'
        main_config = {
            '@admin_username': 'admin',
            '@admin_password': ph.hash('adminpass'),
            '@normal_username': normal_user,
            '@normal_password': ph.hash(normal_pass),
        }
        with patch.object(settings, 'NORMAL_SESSION_EXPIRY_HOURS', 5):
            with patch.object(config, '_main_config_cache', main_config):
                response = self.fetch(
                    '/login',
                    method='POST',
                    body=f'username={normal_user}&password={normal_pass}',
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                )
        self.assertEqual(200, response.code)
        self._assert_session_lifetime(response, 'normal', 5 * 3600)

    def test_admin_session_lifetime_not_configurable(self):
        admin_user = 'admin'
        admin_pass = 's3cret'
        main_config = {
            '@admin_username': admin_user,
            '@admin_password': ph.hash(admin_pass),
            '@normal_username': '',
            '@normal_password': '',
        }
        # even a large normal-user lifetime must not affect the admin cookie
        with patch.object(settings, 'NORMAL_SESSION_EXPIRY_HOURS', 999):
            with patch.object(config, '_main_config_cache', main_config):
                response = self.fetch(
                    '/login',
                    method='POST',
                    body=f'username={admin_user}&password={admin_pass}',
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                )
        self.assertEqual(200, response.code)
        self._assert_session_lifetime(response, 'admin', 24 * 3600)

    def test_normal_session_lifetime_minimum_clamp(self):
        normal_user = 'user'
        normal_pass = 'watcher'
        main_config = {
            '@admin_username': 'admin',
            '@admin_password': ph.hash('adminpass'),
            '@normal_username': normal_user,
            '@normal_password': ph.hash(normal_pass),
        }
        with patch.object(settings, 'NORMAL_SESSION_EXPIRY_HOURS', 0):
            with patch.object(config, '_main_config_cache', main_config):
                response = self.fetch(
                    '/login',
                    method='POST',
                    body=f'username={normal_user}&password={normal_pass}',
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                )
        self.assertEqual(200, response.code)
        self._assert_session_lifetime(response, 'normal', 1 * 3600)

    def test_logout(self):
        cookie = self.make_session_cookie('admin')

        # logout
        logout_resp = self.fetch(
            '/logout',
            method='POST',
            body='',
            headers={'Cookie': cookie},
        )
        self.assertEqual(200, logout_resp.code)

        # ensure logout clears the cookie in the response
        cleared_cookie = logout_resp.headers.get('Set-Cookie', '')
        self.assertTrue(
            'expires=' in cleared_cookie.lower()
            or 'max-age=0' in cleared_cookie.lower()
        )

        # using the old cookie should no longer authenticate
        resp2 = self.fetch(
            '/login',
            headers={'Cookie': cookie},
        )
        self.assertEqual(403, resp2.code)


if __name__ == '__main__':
    tornado.testing.main()
