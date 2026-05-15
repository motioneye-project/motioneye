import json
from hashlib import sha1
from unittest.mock import patch

import tornado.testing
from argon2 import PasswordHasher

from motioneye import config
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
        legacy_hash = sha1(plain.encode()).hexdigest()
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
