# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for authenticating against the motion HTTP control interface."""

import os
import unittest
from contextlib import ExitStack
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import config, motionctl, settings


class ControlRequestTest(unittest.TestCase):
    def test_no_credentials_by_default(self):
        with patch.object(settings, 'MOTION_CONTROL_AUTHENTICATION', ''):
            request = motionctl._control_request('1/detection/status')

        self.assertEqual(
            f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/1/detection/status',
            request.url,
        )
        self.assertIsNone(request.auth_username)
        self.assertIsNone(request.auth_password)

    def test_sends_configured_credentials(self):
        with patch.object(settings, 'MOTION_CONTROL_AUTHENTICATION', 'user:pass'):
            request = motionctl._control_request('1/action/snapshot')

        self.assertEqual('user', request.auth_username)
        self.assertEqual('pass', request.auth_password)
        self.assertEqual('basic', request.auth_mode)

    def test_password_may_contain_colons(self):
        # motion compares the whole "username:password" string
        with patch.object(settings, 'MOTION_CONTROL_AUTHENTICATION', 'user:p:a:ss'):
            request = motionctl._control_request('1/action/snapshot')

        self.assertEqual('user', request.auth_username)
        self.assertEqual('p:a:ss', request.auth_password)


class SetMotionControlAuthTest(unittest.TestCase):
    def _apply(self, authentication, data):
        with patch.object(settings, 'MOTION_CONTROL_AUTHENTICATION', authentication):
            return config._set_motion_control_auth(data)

    def test_sets_credentials_and_basic_method(self):
        data = {}

        self.assertTrue(self._apply('user:pass', data))
        self.assertEqual('user:pass', data['webcontrol_authentication'])
        self.assertEqual(1, data['webcontrol_auth_method'])

    def test_overrides_other_credentials(self):
        data = {'webcontrol_authentication': 'old:old', 'webcontrol_auth_method': 2}

        self.assertTrue(self._apply('user:pass', data))
        self.assertEqual('user:pass', data['webcontrol_authentication'])
        self.assertEqual(1, data['webcontrol_auth_method'])

    def test_reports_no_change_when_up_to_date(self):
        data = {'webcontrol_authentication': 'user:pass', 'webcontrol_auth_method': 1}

        self.assertFalse(self._apply('user:pass', data))

    def test_removes_credentials_when_disabled(self):
        # motionEye would not be able to talk to motion with them left in place
        data = {'webcontrol_authentication': 'user:pass', 'webcontrol_auth_method': 1}

        self.assertTrue(self._apply('', data))
        self.assertNotIn('webcontrol_authentication', data)
        self.assertNotIn('webcontrol_auth_method', data)

    def test_reports_no_change_when_disabled_and_absent(self):
        self.assertFalse(self._apply('', {}))


class MotionConfAuthTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = mkdtemp()
        self.conf_file = os.path.join(self.tmp_dir, 'motion.conf')
        # existing secrets, so that only the authentication can trigger a save
        with open(self.conf_file, 'w') as f:
            f.write(
                '# @relay_secret secret\n'
                '# @client_secret secret\n'
                'webcontrol_port 7999\n'
            )

        os.chmod(self.conf_file, 0o600)

    def tearDown(self):
        config._main_config_cache = None
        rmtree(self.tmp_dir)

    def _read_motion_conf(self, authentication):
        with ExitStack() as stack:
            stack.enter_context(
                patch.multiple(
                    settings,
                    CONF_PATH=self.tmp_dir,
                    MOTION_CONTROL_AUTHENTICATION=authentication,
                )
            )
            stack.enter_context(patch.object(config, '_main_config_cache', None))
            for name in ('is_motion_pre42', 'is_motion_post43'):
                stack.enter_context(patch.object(motionctl, name, return_value=False))

            config.get_main()

        with open(self.conf_file) as f:
            return f.read().splitlines()

    def test_writes_credentials_before_motion_starts(self):
        lines = self._read_motion_conf('user:pass')

        self.assertIn('webcontrol_authentication user:pass', lines)
        self.assertIn('webcontrol_auth_method 1', lines)

    def test_removes_credentials_once_disabled(self):
        self._read_motion_conf('user:pass')
        lines = self._read_motion_conf('')

        self.assertFalse(any(line.startswith('webcontrol_auth') for line in lines))

    def test_leaves_file_alone_without_authentication(self):
        with open(self.conf_file) as f:
            before = f.read()

        self._read_motion_conf('')

        with open(self.conf_file) as f:
            self.assertEqual(before, f.read())


if __name__ == '__main__':
    unittest.main()
