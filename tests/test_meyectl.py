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

import logging
import os
import sys
import unittest
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import meyectl, settings

# load_settings() changes these, restore them after each test
_PATHS = ('CONF_PATH', 'RUN_PATH', 'LOG_PATH', 'MEDIA_PATH')


class LogLevelTest(unittest.TestCase):
    def _load(self, *log_levels):
        conf_dir = mkdtemp()
        self.addCleanup(rmtree, conf_dir)
        path = os.path.join(conf_dir, 'motioneye.conf')
        with open(path, 'w') as f:
            f.writelines(f'log_level {level}\n' for level in log_levels)

        paths = {name: getattr(settings, name) for name in _PATHS}
        with patch.multiple(
            settings, config_file=None, LOG_LEVEL=logging.INFO, **paths
        ):
            with patch.object(sys, 'argv', ['meyectl', 'startserver', '-c', path]):
                meyectl.load_settings()

            return settings.LOG_LEVEL

    def test_known_levels(self):
        for name, level in (
            ('debug', logging.DEBUG),
            ('info', logging.INFO),
            ('warning', logging.WARNING),
            ('error', logging.ERROR),
            ('Quiet', 100),
            ('  Warning', logging.WARNING),
            ('10', logging.DEBUG),
        ):
            with self.subTest(log_level=name):
                self.assertEqual(level, self._load(name))

    def test_unknown_level_keeps_the_previous_one(self):
        for name in ('debgu', 'basic_format', 'info # comment'):
            with self.subTest(log_level=name), self.assertLogs(level='WARNING') as logs:
                self.assertEqual(logging.ERROR, self._load('error', name))
                self.assertIn(f'unknown log level: {name}', '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
