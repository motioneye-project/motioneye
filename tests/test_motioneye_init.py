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

import os
import shutil
import tempfile
import unittest
from unittest import mock

import motioneye
from motioneye import motioneye_init


class TestMotionEyeInit(unittest.TestCase):
    def setUp(self):
        self.scripts = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.scripts)
        self.linux_init = f'{motioneye.__path__[0]}/extra/linux_init'

    def _main(self, *argv):
        with (
            mock.patch.object(
                motioneye_init.sysconfig, 'get_path', return_value=self.scripts
            ),
            mock.patch.object(motioneye_init.sys, 'argv', ['motioneye_init', *argv]),
            mock.patch.object(motioneye_init, 'run') as run,
        ):
            motioneye_init.main()

        run.assert_called_once()
        return run.call_args.args[0]

    def test_meyectl_of_the_environment_is_passed(self):
        meyectl = os.path.join(self.scripts, 'meyectl')
        with open(meyectl, 'w'):
            pass
        os.chmod(meyectl, 0o700)

        # given first, so that --meyectl on the command line takes precedence
        self.assertEqual(
            [self.linux_init, '--meyectl', meyectl, '--skip-systemd'],
            self._main('--skip-systemd'),
        )

    def test_nothing_is_passed_without_meyectl(self):
        self.assertEqual(
            [self.linux_init, '--skip-systemd'], self._main('--skip-systemd')
        )


if __name__ == '__main__':
    unittest.main()
