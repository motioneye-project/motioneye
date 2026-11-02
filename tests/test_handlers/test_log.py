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

"""Tests verifying the log handler when the requested log file is absent."""

import os
import unittest
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye.handlers.log import LogHandler
from tests.test_handlers import HandlerTestCase


class LogHandlerTest(HandlerTestCase):
    handler_cls = LogHandler

    def setUp(self):
        self.log_dir = mkdtemp()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        rmtree(self.log_dir)

    def _fetch_motion_log(self):
        cookie = self.make_session_cookie('admin')
        return self.fetch('/log/motion/', headers={'Cookie': cookie})

    def test_missing_log_file_returns_404(self):
        # with log_to_file disabled motion.log is never written (#3330);
        # the handler must not blow up trying to open it
        path = os.path.join(self.log_dir, 'motion.log')
        with patch.dict(LogHandler.LOGS, {'motion': (path, 'motion.log')}):
            response = self._fetch_motion_log()

        self.assertEqual(404, response.code)

    def test_existing_log_file_is_served(self):
        path = os.path.join(self.log_dir, 'motion.log')
        with open(path, 'w') as f:
            f.write('a motion log line\n')

        with patch.dict(LogHandler.LOGS, {'motion': (path, 'motion.log')}):
            response = self._fetch_motion_log()

        self.assertEqual(200, response.code)
        self.assertEqual(b'a motion log line\n', response.body)


if __name__ == '__main__':
    unittest.main()
