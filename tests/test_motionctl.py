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
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import motionctl, settings


class MotionLogFileTest(unittest.TestCase):
    def setUp(self):
        self.log_dir = mkdtemp()

    def tearDown(self):
        rmtree(self.log_dir)

    def test_no_log_file_when_log_to_file_disabled(self):
        # None makes Popen pass motionEye's own stdout/stderr on to motion
        with patch.object(settings, 'LOG_TO_FILE', False):
            self.assertIsNone(motionctl._get_motion_log_file())

    def test_log_file_opened_when_log_to_file_enabled(self):
        with patch.object(settings, 'LOG_TO_FILE', True), patch.object(
            settings, 'LOG_PATH', self.log_dir
        ):
            log_file = motionctl._get_motion_log_file()

        try:
            self.assertEqual(os.path.join(self.log_dir, 'motion.log'), log_file.name)
        finally:
            log_file.close()


if __name__ == '__main__':
    unittest.main()
