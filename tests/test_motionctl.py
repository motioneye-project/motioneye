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

"""Tests verifying where motion's output is sent, depending on log_to_file."""

import os
import unittest
from contextlib import ExitStack
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import config, motionctl, settings


class MotionLogFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = mkdtemp()

    def tearDown(self):
        rmtree(self.tmp_dir)

    def _start(self, log_to_file):
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

            popen = stack.enter_context(patch.object(motionctl, 'Popen'))
            popen.return_value.poll.return_value = None
            popen.return_value.pid = 1234
            motionctl.start()

        return popen.call_args.kwargs

    def test_no_log_file_when_log_to_file_disabled(self):
        # None makes Popen pass motionEye's own stdout/stderr on to motion
        kwargs = self._start(log_to_file=False)

        self.assertIsNone(kwargs['stdout'])
        self.assertIsNone(kwargs['stderr'])
        self.assertFalse(os.path.exists(os.path.join(self.tmp_dir, 'motion.log')))

    def test_log_file_opened_when_log_to_file_enabled(self):
        kwargs = self._start(log_to_file=True)

        log_file = kwargs['stdout']
        self.assertIs(log_file, kwargs['stderr'])
        self.assertEqual(os.path.join(self.tmp_dir, 'motion.log'), log_file.name)
        # motion holds its own copy of the file descriptor
        self.assertTrue(log_file.closed)


if __name__ == '__main__':
    unittest.main()
