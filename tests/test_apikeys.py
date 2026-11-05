import json
import os
import stat
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase
from unittest.mock import patch

from motioneye import apikeys


class ApiKeysTest(TestCase):
    def setUp(self):
        self.conf_path = mkdtemp()
        self._patch = patch('motioneye.settings.CONF_PATH', self.conf_path)
        self._patch.start()
        apikeys.reset()

    def tearDown(self):
        self._patch.stop()
        apikeys.reset()
        rmtree(self.conf_path, True)

    def read_file(self):
        with open(os.path.join(self.conf_path, 'api_keys.json')) as f:
            return json.load(f)

    def test_add_returns_the_token_once_and_keeps_only_its_hash(self):
        key, token = apikeys.add('Home Assistant', 'admin')

        self.assertTrue(token.startswith(apikeys.TOKEN_PREFIX))
        self.assertEqual('Home Assistant', key['name'])
        self.assertEqual('admin', key['role'])
        self.assertEqual(token[-4:], key['hint'])
        self.assertNotIn('hash', key)
        self.assertNotIn(token, json.dumps(self.read_file()))
        self.assertNotIn('hash', json.dumps(apikeys.list_keys()))

    def test_file_is_private(self):
        apikeys.add('script', 'normal')
        mode = os.stat(os.path.join(self.conf_path, 'api_keys.json')).st_mode
        self.assertEqual(0o600, stat.S_IMODE(mode))

    def test_verify_returns_the_role(self):
        _, admin_token = apikeys.add('admin script', 'admin')
        _, normal_token = apikeys.add('viewer script', 'normal')

        self.assertEqual('admin', apikeys.verify(admin_token))
        self.assertEqual('normal', apikeys.verify(normal_token))
        self.assertIsNone(apikeys.verify(admin_token + 'x'))
        self.assertIsNone(apikeys.verify('not a key'))
        self.assertIsNone(apikeys.verify(''))

    def test_keys_survive_a_restart(self):
        key, token = apikeys.add('script', 'normal')
        apikeys.reset()

        self.assertEqual([key], apikeys.list_keys())
        self.assertEqual('normal', apikeys.verify(token))

    def test_remove(self):
        key, token = apikeys.add('script', 'admin')

        self.assertTrue(apikeys.remove(key['id']))
        self.assertIsNone(apikeys.verify(token))
        self.assertFalse(apikeys.remove(key['id']))
        apikeys.reset()
        self.assertEqual([], apikeys.list_keys())

    def test_last_use_is_recorded_to_the_hour(self):
        _, token = apikeys.add('camera poller', 'normal')

        with patch('motioneye.apikeys.time', return_value=1_000_000):
            apikeys.verify(token)
        self.assertEqual(1_000_000, self.read_file()[0]['last_used'])

        with patch('motioneye.apikeys.time', return_value=1_000_000 + 60):
            apikeys.verify(token)
        self.assertEqual(1_000_000, self.read_file()[0]['last_used'])

        with patch('motioneye.apikeys.time', return_value=1_000_000 + 3600):
            apikeys.verify(token)
        self.assertEqual(1_000_000 + 3600, self.read_file()[0]['last_used'])

    def test_invalid_input(self):
        for name, role in (
            ('', 'admin'),
            ('   ', 'admin'),
            (None, 'admin'),
            ('x' * 65, 'admin'),
            ('script', 'root'),
            ('script', None),
        ):
            with (
                self.subTest(name=name, role=role),
                self.assertRaises(apikeys.ApiKeyError),
            ):
                apikeys.add(name, role)

        self.assertEqual([], apikeys.list_keys())

    def test_name_is_stripped(self):
        key, _ = apikeys.add('  script  ', 'normal')
        self.assertEqual('script', key['name'])

    def test_unreadable_file_means_no_keys(self):
        with open(os.path.join(self.conf_path, 'api_keys.json'), 'w') as f:
            f.write('{not json')

        self.assertEqual([], apikeys.list_keys())
        self.assertIsNone(apikeys.verify(apikeys.TOKEN_PREFIX + 'x'))

    def test_entries_without_a_valid_role_are_ignored(self):
        with open(os.path.join(self.conf_path, 'api_keys.json'), 'w') as f:
            json.dump([{'id': 'abcd0123', 'role': 'root', 'hash': 'x'}], f)

        self.assertEqual([], apikeys.list_keys())
