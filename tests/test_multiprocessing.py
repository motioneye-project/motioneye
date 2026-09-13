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
import multiprocessing
import os
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory

import motioneye

# Regression test for #3411: our multiprocessing children rely on inheriting
# the parent's settings and logging, which Python 3.14's 'forkserver' default
# breaks. The check runs in its own interpreter so the process-wide start
# method cannot leak into the rest of the run; the __main__ guard keeps the
# forkserver from re-running the parent part when it imports the script.
_SCRIPT = '''
import logging
import multiprocessing
import sys

from motioneye import meyectl, settings


def report(path):
    with open(path, 'w') as f:
        print(settings.CONF_PATH, file=f)
        print(logging.getLogger().level, file=f)


if __name__ == '__main__':
    conf_path, report_path = sys.argv[1:3]

    meyectl.configure_multiprocessing()

    # what load_settings() and configure_logging() do in the parent
    settings.CONF_PATH = conf_path
    logging.basicConfig(level=logging.DEBUG)

    p = multiprocessing.Process(target=report, args=(report_path,), daemon=True)
    p.start()
    p.join(30)
    if p.is_alive():
        p.kill()
        sys.exit('the child did not finish in 30 seconds')

    sys.exit(p.exitcode)
'''


@unittest.skipUnless(
    'fork' in multiprocessing.get_all_start_methods(),
    "the 'fork' start method is not available on this platform",
)
class TestMultiprocessing(unittest.TestCase):
    def test_children_inherit_settings_and_logging(self):
        with TemporaryDirectory() as tmp_dir:
            script = os.path.join(tmp_dir, 'spawn_child.py')
            with open(script, 'w') as f:
                f.write(_SCRIPT)

            conf_path = os.path.join(tmp_dir, 'conf')
            report_path = os.path.join(tmp_dir, 'report.txt')

            # make the child import the same motioneye package as this test
            env = dict(os.environ)
            package_root = os.path.dirname(os.path.dirname(motioneye.__file__))
            env['PYTHONPATH'] = os.pathsep.join(
                p for p in (package_root, env.get('PYTHONPATH')) if p
            )

            result = subprocess.run(
                [sys.executable, script, conf_path, report_path],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                os.path.exists(report_path), 'the child never reported back'
            )

            with open(report_path) as f:
                child_conf_path, child_log_level = f.read().splitlines()

        self.assertEqual(
            child_conf_path,
            conf_path,
            f"child saw CONF_PATH {child_conf_path!r}; it must inherit the parent's",
        )
        self.assertEqual(
            int(child_log_level),
            logging.DEBUG,
            "child root logger level must inherit the parent's DEBUG",
        )
