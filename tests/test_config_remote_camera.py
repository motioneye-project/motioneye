from __future__ import annotations

import unittest
from unittest.mock import patch

from motioneye import config

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
    """The id a remote motionEye advertises for its camera is taken as an integer."""

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


class TestConfValues(unittest.TestCase):
    """A value written to a config file can never add a line of its own."""

    def test_line_breaks_in_a_value_are_written_as_spaces(self):
        lines = config._dict_to_conf([], {'@remote_camera_id': '1\r\nnetcam_url x'})

        self.assertEqual(['# @remote_camera_id 1  netcam_url x'], lines)

    def test_other_values_are_unchanged(self):
        self.assertEqual('on', config._python_to_value(True))
        self.assertEqual('5', config._python_to_value(5))
        self.assertEqual('plain', config._python_to_value('plain'))
