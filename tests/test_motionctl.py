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

"""Tests verifying where motion logs to, depending on log_to_file."""

import os
import unittest
from contextlib import ExitStack
from shutil import rmtree
from subprocess import DEVNULL
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import config, motionctl, settings


class MotionLogFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = mkdtemp()

    def tearDown(self):
        rmtree(self.tmp_dir)

    def _start(self, log_to_file, syslog=True):
        with ExitStack() as stack:
            stack.enter_context(
                patch.multiple(
                    settings,
                    LOG_TO_FILE=log_to_file,
                    LOG_PATH=self.tmp_dir,
                    CONF_PATH=self.tmp_dir,
                    RUN_PATH=self.tmp_dir,
                    MJPG_CLIENT_IDLE_TIMEOUT=10,
                )
            )
            stack.enter_context(
                patch.object(
                    config,
                    'get_enabled_local_motion_cameras',
                    return_value=[{'@id': 1}],
                )
            )
            for name, value in (
                ('running', False),
                ('find_motion', ('motion', '4.7.0')),
                ('is_motion_post43', True),
                ('sleep', None),
            ):
                stack.enter_context(patch.object(motionctl, name, return_value=value))

            stack.enter_context(
                patch.object(
                    motionctl,
                    'exists',
                    side_effect=lambda p: syslog and p == '/dev/log',
                )
            )

            popen = stack.enter_context(patch.object(motionctl, 'Popen'))
            popen.return_value.poll.return_value = None
            popen.return_value.pid = 1234
            motionctl.start()

        return popen.call_args

    def test_motion_logs_to_syslog_when_log_to_file_disabled(self):
        args, kwargs = self._start(log_to_file=False)

        self.assertNotIn('-l', args[0])
        # muted, as motion logs to syslog as well, which would duplicate lines
        self.assertIs(DEVNULL, kwargs['stdout'])
        self.assertIs(DEVNULL, kwargs['stderr'])

    def test_motion_logs_to_stderr_without_syslog(self):
        # e.g. in a container, where nothing listens on /dev/log
        args, kwargs = self._start(log_to_file=False, syslog=False)

        self.assertNotIn('-l', args[0])
        # None makes Popen pass motionEye's own stdout/stderr on to motion
        self.assertIsNone(kwargs['stdout'])
        self.assertIsNone(kwargs['stderr'])

    def _assert_log_file(self, args):
        motion_args = args[0]
        log_index = motion_args.index('-l')
        self.assertEqual(
            os.path.join(self.tmp_dir, 'motion.log'), motion_args[log_index + 1]
        )

    def test_motion_logs_to_file_when_log_to_file_enabled(self):
        args, kwargs = self._start(log_to_file=True)

        self._assert_log_file(args)
        # early startup logs go to syslog, until motion switches to the file
        self.assertIs(DEVNULL, kwargs['stdout'])
        self.assertIs(DEVNULL, kwargs['stderr'])

    def test_motion_logs_to_file_and_stderr_without_syslog(self):
        args, kwargs = self._start(log_to_file=True, syslog=False)

        self._assert_log_file(args)
        # keeps early startup logs, until motion switches to the file
        self.assertIsNone(kwargs['stdout'])
        self.assertIsNone(kwargs['stderr'])


if __name__ == '__main__':
    unittest.main()
