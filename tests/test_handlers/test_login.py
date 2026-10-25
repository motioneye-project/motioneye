import json
from email.utils import parsedate_to_datetime
from hashlib import sha1
from http.cookies import SimpleCookie
from ipaddress import ip_network
from unittest import TestCase
from unittest.mock import patch

import tornado.testing
from argon2 import PasswordHasher
from tornado.httputil import HTTPHeaders, HTTPServerRequest

from motioneye import config
from motioneye.handlers import base, login
from motioneye.handlers.base import _session_store
from motioneye.handlers.login import LoginHandler
from tests.test_handlers import HandlerTestCase

ph = PasswordHasher()


class LoginAddressTest(TestCase):
    def test_proxy_trust_boundaries(self):
        cases = (
            ('192.0.2.10', '198.51.100.1', '', '192.0.2.10'),
            ('203.0.113.1', '198.51.100.1', '192.0.2.10', '203.0.113.1'),
            ('192.0.2.10', None, '192.0.2.10', '192.0.2.10'),
            ('192.0.2.10', '198.51.100.1', '192.0.2.10', '198.51.100.1'),
            ('192.0.2.10', '198.51.100.1', '192.0.2.0/24', '198.51.100.1'),
            (
                '192.0.2.10',
                '198.51.100.1, 203.0.113.10',
                '192.0.2.0/24,203.0.113.10',
                '198.51.100.1',
            ),
            (
                '192.0.2.10',
                '203.0.113.1, 198.51.100.1',
                '192.0.2.10',
                '198.51.100.1',
            ),
            ('192.0.2.10', '198.51.100.1, invalid', '192.0.2.10', '192.0.2.10'),
            ('192.0.2.10', '198.51.100.1, ', '192.0.2.10', '192.0.2.10'),
            ('192.0.2.10', '192.0.2.11', '192.0.2.0/24', '192.0.2.10'),
            (
                '2001:db8:1::10',
                '2001:db8:2::1',
                '2001:db8:1::/64',
                '2001:db8:2::1',
            ),
            ('::ffff:192.0.2.10', '198.51.100.1', '192.0.2.10', '198.51.100.1'),
            ('192.0.2.10', '::ffff:198.51.100.1', '192.0.2.10', '::ffff:198.51.100.1'),
        )
        for address, forwarded_for, proxies, expected in cases:
            with self.subTest(
                address=address, forwarded_for=forwarded_for, proxies=proxies
            ):
                request = HTTPServerRequest()
                request.remote_ip = address
                request.headers = HTTPHeaders({'X-Real-IP': '127.0.0.1'})
                if forwarded_for is not None:
                    request.headers['X-Forwarded-For'] = forwarded_for
                networks = tuple(
                    ip_network(proxy) for proxy in proxies.split(',') if proxy
                )
                with patch.object(login, '_TRUSTED_PROXIES', networks):
                    self.assertEqual(expected, login.get_login_address(request))
                    self.assertEqual(address, request.remote_ip)

    def test_normalize_address(self):
        cases = (
            (None, None),
            ('', ''),
            ('198.51.100.7', '198.51.100.7'),
            ('::ffff:198.51.100.7', '198.51.100.7'),
            ('2001:db8:1::5', '2001:db8:1::/64'),
            ('2001:db8:1:0:ffff::1', '2001:db8:1::/64'),
            ('invalid', 'invalid'),
        )
        for address, expected in cases:
            with self.subTest(address=address):
                self.assertEqual(expected, login.normalize_address(address))

    def test_parse_trusted_proxies(self):
        cases = (
            ('', ()),
            ('192.168.1.5', (ip_network('192.168.1.5'),)),
            (
                '10.0.0.1, 192.168.1.0/24',
                (ip_network('10.0.0.1'), ip_network('192.168.1.0/24')),
            ),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(expected, login.parse_trusted_proxies(value))

    def test_parse_trusted_proxies_ignores_all_on_invalid_entry(self):
        for value in ('192.168.1.5/24', '10.0.0.1, invalid'):
            with self.subTest(value=value), self.assertLogs(level='WARNING') as logs:
                self.assertEqual((), login.parse_trusted_proxies(value))

            self.assertIn('ignoring invalid trusted_proxies', logs.output[0])


class LoginFailureTableTest(TestCase):
    def setUp(self):
        for patcher in (
            patch.object(login, '_failed_logins', {}),
            patch.object(login, 'monotonic', return_value=100),
            patch.object(login, '_MAX_ENTRIES', 3),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _fail(self, client, count):
        for _ in range(count):
            login.record_failed_login(client)

    def test_full_table_drops_oldest_unblocked_client(self):
        self._fail('203.0.113.1', 5)
        self._fail('203.0.113.2', 1)
        self._fail('203.0.113.3', 1)
        with self.assertLogs(level='WARNING'):
            self._fail('203.0.113.4', 1)

        self.assertEqual(
            ['203.0.113.1', '203.0.113.3', '203.0.113.4'], list(login._failed_logins)
        )

    def test_full_table_drops_oldest_client_when_all_blocked(self):
        for client in ('203.0.113.1', '203.0.113.2', '203.0.113.3'):
            self._fail(client, 5)

        with self.assertLogs(level='WARNING'):
            self._fail('203.0.113.4', 1)

        self.assertEqual(
            ['203.0.113.2', '203.0.113.3', '203.0.113.4'], list(login._failed_logins)
        )


class LoginRateLimitTest(HandlerTestCase):
    handler_cls = LoginHandler

    def setUp(self):
        super().setUp()
        main_config = {
            '@admin_username': 'admin',
            '@admin_password': '',
            '@normal_username': 'user',
            '@normal_password': '',
        }
        for patcher in (
            patch.object(config, '_main_config_cache', main_config),
            patch.object(login, '_failed_logins', {}),
            patch.object(login, 'monotonic', return_value=100),
            patch.object(login, '_TRUSTED_PROXIES', (ip_network('127.0.0.1'),)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.clock = login.monotonic

    def _login(self, address, password, username='admin'):
        return self.fetch(
            '/login',
            method='POST',
            body=f'username={username}&password={password}',
            headers={'X-Forwarded-For': address},
        )

    def test_trusted_proxy_clients_are_limited_separately(self):
        for _ in range(5):
            self.assertEqual(401, self._login('198.51.100.1', 'wrong').code)

        blocked = self._login('198.51.100.1', '')
        self.assertEqual(429, blocked.code)
        self.assertEqual('5', blocked.headers['Retry-After'])
        self.assertEqual(5, json.loads(blocked.body)['retry_after'])
        self.assertEqual(200, self._login('198.51.100.2', '').code)

    def _fail(self, address, count):
        for _ in range(count):
            self.assertEqual(401, self._login(address, 'wrong').code)

    def test_retry_admitted_when_delay_has_passed(self):
        self._fail('198.51.100.1', 5)

        self.clock.return_value = 104
        blocked = self._login('198.51.100.1', '')
        self.assertEqual(429, blocked.code)
        self.assertEqual('1', blocked.headers['Retry-After'])

        self.clock.return_value = 105
        self.assertEqual(200, self._login('198.51.100.1', '').code)

    def test_backoff_doubles_up_to_cap(self):
        self._fail('198.51.100.1', 5)

        for delay in (5, 10, 20, 40, 80, 160, 320, 640, 900, 900):
            blocked = self._login('198.51.100.1', '')
            self.assertEqual(429, blocked.code)
            self.assertEqual(str(delay), blocked.headers['Retry-After'])
            self.clock.return_value += delay
            self._fail('198.51.100.1', 1)

    def test_failure_count_kept_for_one_hour(self):
        self._fail('198.51.100.1', 5)

        self.clock.return_value += 3600
        self._fail('198.51.100.1', 1)
        blocked = self._login('198.51.100.1', '')
        self.assertEqual(429, blocked.code)
        self.assertEqual('10', blocked.headers['Retry-After'])

    def test_failure_count_restarts_after_one_hour(self):
        self._fail('198.51.100.1', 5)

        self.clock.return_value += 3601
        self._fail('198.51.100.1', 5)
        blocked = self._login('198.51.100.1', '')
        self.assertEqual(429, blocked.code)
        self.assertEqual('5', blocked.headers['Retry-After'])

    def test_success_clears_failure_count(self):
        self._fail('198.51.100.1', 4)
        self.assertEqual(200, self._login('198.51.100.1', '').code)

        self._fail('198.51.100.1', 5)
        blocked = self._login('198.51.100.1', '')
        self.assertEqual(429, blocked.code)
        self.assertEqual('5', blocked.headers['Retry-After'])

    def test_success_after_wait_clears_backoff(self):
        self._fail('198.51.100.1', 5)

        self.clock.return_value += 5
        self.assertEqual(200, self._login('198.51.100.1', '').code)

        self._fail('198.51.100.1', 5)
        blocked = self._login('198.51.100.1', '')
        self.assertEqual(429, blocked.code)
        self.assertEqual('5', blocked.headers['Retry-After'])

    def test_normal_user_success_keeps_failure_count(self):
        self._fail('198.51.100.1', 4)
        self.assertEqual(200, self._login('198.51.100.1', '', 'user').code)

        self._fail('198.51.100.1', 1)
        self.assertEqual(429, self._login('198.51.100.1', '').code)

    def test_untrusted_clients_cannot_evade_limit_with_forwarded_headers(self):
        for networks in ((), (ip_network('192.0.2.10'),)):
            with (
                self.subTest(networks=networks),
                patch.object(login, '_TRUSTED_PROXIES', networks),
                patch.object(login, '_failed_logins', {}),
            ):
                for i in range(5):
                    self.assertEqual(
                        401, self._login(f'198.51.100.{i + 1}', 'wrong').code
                    )

                self.assertEqual(429, self._login('198.51.100.100', '').code)


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
        legacy_hash = sha1(plain.encode()).hexdigest()  # nosec: B324
        main_config = {
            '@admin_username': admin_user,
            '@admin_password': legacy_hash,
            '@normal_username': '',
            '@normal_password': '',
        }
        with (
            patch.object(config, '_main_config_cache', main_config),
            patch.object(config, 'set_admin_password') as mock_set_admin,
        ):
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
        with (
            patch.object(config, '_main_config_cache', main_config),
            patch.object(config, 'set_normal_password') as mock_set_normal,
        ):
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
        with (
            patch.object(base, 'NORMAL_SESSION_EXPIRY_HOURS', 5),
            patch.object(config, '_main_config_cache', main_config),
        ):
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
        with (
            patch.object(base, 'NORMAL_SESSION_EXPIRY_HOURS', 999),
            patch.object(config, '_main_config_cache', main_config),
        ):
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
        with (
            patch.object(base, 'NORMAL_SESSION_EXPIRY_HOURS', 0),
            patch.object(config, '_main_config_cache', main_config),
        ):
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
