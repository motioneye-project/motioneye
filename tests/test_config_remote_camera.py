from __future__ import annotations

import unittest
from unittest.mock import patch

from motioneye import config
from tests.test_notification_settings import _ConfigCase

_REMOTE_DETAILS = {
    'proto': 'motioneye',
    'scheme': 'http',
    'host': 'cam.example',
    'port': 8765,
    'path': '',
    'remote_camera_id': '7',
    'remote_secret': 'secret',
}


class TestAddRemoteCamera(unittest.TestCase):
    """What add_camera() stores for a remote motionEye camera."""

    def setUp(self):
        self._set_camera = patch('motioneye.config.set_camera')
        self._patches = [
            patch('motioneye.config.get_camera_ids', return_value=[]),
            patch('motioneye.config.get_camera', return_value={}),
            self._set_camera,
        ]
        self.set_camera = self._set_camera.start()
        for p in self._patches[:2]:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_remote_camera_id_is_stored_as_an_integer(self):
        config.add_camera(dict(_REMOTE_DETAILS))

        camera_config = self.set_camera.call_args.args[1]
        self.assertEqual(7, camera_config['@remote_camera_id'])

    def test_remote_camera_id_with_other_characters_is_refused(self):
        details = dict(_REMOTE_DETAILS, remote_camera_id='1\nnetcam_url rtsp://x/y')

        with self.assertRaisesRegex(ValueError, 'invalid remote camera id'):
            config.add_camera(details)

    def test_a_missing_remote_camera_id_is_refused(self):
        details = dict(_REMOTE_DETAILS)
        del details['remote_camera_id']

        with self.assertRaisesRegex(ValueError, 'invalid remote camera id'):
            config.add_camera(details)

    def test_the_certificate_is_verified_by_default(self):
        config.add_camera(dict(_REMOTE_DETAILS))

        camera_config = self.set_camera.call_args.args[1]
        self.assertIs(True, camera_config['@remote_verify'])

    def test_the_certificate_check_can_be_turned_off(self):
        config.add_camera(dict(_REMOTE_DETAILS, remote_verify=False))

        camera_config = self.set_camera.call_args.args[1]
        self.assertIs(False, camera_config['@remote_verify'])


class TestConfValues(unittest.TestCase):
    """A value written to a config file can never add a line of its own."""

    def test_line_breaks_in_a_value_are_written_as_spaces(self):
        lines = config._dict_to_conf([], {'@remote_camera_id': '1\r\nnetcam_url x'})

        self.assertEqual(['# @remote_camera_id 1  netcam_url x'], lines)

    def test_other_values_are_unchanged(self):
        self.assertEqual('on', config._python_to_value(True))
        self.assertEqual('5', config._python_to_value(5))
        self.assertEqual('plain', config._python_to_value('plain'))


class TestRemoteCameraFile(_ConfigCase):
    """What camera-N.conf says about the certificate check of a remote motionEye camera."""

    _FILE = (
        '# @proto motioneye\n'
        '# @scheme https\n'
        '# @host cam.example\n'
        '# @port 8765\n'
        '# @remote_camera_id 7\n'
    )

    def test_a_turned_off_check_is_written_as_off(self):
        lines = config._dict_to_conf([], {'@remote_verify': False})

        self.assertEqual(['# @remote_verify off'], lines)
        self.assertIs(False, config._conf_to_dict(lines)['@remote_verify'])

    def test_a_file_without_the_key_verifies_the_certificate(self):
        self._write_text(1, self._FILE)

        self.assertIs(True, config.get_camera(1)['@remote_verify'])

    def test_a_file_can_turn_the_check_off(self):
        self._write_text(1, self._FILE + '# @remote_verify off\n')

        self.assertIs(False, config.get_camera(1)['@remote_verify'])

    def test_a_bare_or_unknown_value_keeps_the_check_on(self):
        for line in ('# @remote_verify\n', '# @remote_verify maybe\n'):
            with self.subTest(line=line.strip()):
                self._write_text(1, self._FILE + line)
                config.invalidate()

                self.assertIs(True, config.get_camera(1)['@remote_verify'])

    def test_an_explicit_off_word_turns_the_check_off(self):
        for line in ('# @remote_verify no\n', '# @remote_verify 0\n'):
            with self.subTest(line=line.strip()):
                self._write_text(1, self._FILE + line)
                config.invalidate()

                self.assertIs(False, config.get_camera(1)['@remote_verify'])

    def test_a_turned_off_check_stays_off_when_the_camera_is_saved(self):
        self._write_text(1, self._FILE)
        camera = config.get_camera(1)
        camera['@remote_verify'] = False
        config.set_camera(1, camera)
        config.invalidate()

        self.assertIn('# @remote_verify off', self._read(1).splitlines())
        self.assertIs(False, config.get_camera(1)['@remote_verify'])
