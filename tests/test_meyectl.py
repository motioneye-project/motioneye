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

"""Tests verifying that the log_to_file setting is read from the config file."""

import os
import sys
import unittest
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import meyectl, settings


class LoadSettingsLogToFileTest(unittest.TestCase):
    # load_settings() assigns to these module globals directly, so patching
    # cannot undo it; snapshot and restore them to keep other tests isolated
    _SETTINGS = (
        'CONF_PATH',
        'RUN_PATH',
        'LOG_PATH',
        'MEDIA_PATH',
        'LOG_LEVEL',
        'LOG_TO_FILE',
        'config_file',
    )

    def setUp(self):
        self.conf_dir = mkdtemp()
        self.saved = {name: getattr(settings, name) for name in self._SETTINGS}

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(settings, name, value)

        rmtree(self.conf_dir)

    def _load_settings(self, conf, argv=()):
        conf_file = os.path.join(self.conf_dir, 'motioneye.conf')
        with open(conf_file, 'w') as f:
            f.write(conf)

        with patch.object(
            sys, 'argv', ['meyectl', 'startserver', '-c', conf_file, *argv]
        ):
            meyectl.load_settings()

    def test_log_to_file_disabled_by_default(self):
        self._load_settings('log_level info\n')
        self.assertEqual(False, settings.LOG_TO_FILE)

    def test_log_to_file_false_from_config(self):
        # the string is parsed as a bool, not fed to int() (#3330)
        self._load_settings('log_to_file false\n')
        self.assertEqual(False, settings.LOG_TO_FILE)

    def test_log_to_file_true_from_config(self):
        self._load_settings('log_to_file true\n')
        self.assertEqual(True, settings.LOG_TO_FILE)

    def test_l_argument_overrides_config(self):
        self._load_settings('log_to_file false\n', argv=('-l',))
        self.assertEqual(True, settings.LOG_TO_FILE)


if __name__ == '__main__':
    unittest.main()
