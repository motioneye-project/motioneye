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
import subprocess
import sys
import unittest
from shutil import rmtree
from tempfile import mkdtemp
from types import SimpleNamespace
from unittest.mock import patch

import motioneye

# The checks run in their own interpreter, so that the signal handlers do not
# leak into the rest of the run. Each prints how long the IO loop ran, last.
_SETUP = '''
import gettext
import multiprocessing
import os
import signal
import threading
import time

from tornado.ioloop import IOLoop, PeriodicCallback

from motioneye import meyectl, server

# bye_handler() logs with _(), it would raise before stopping the loop
gettext.install('motioneye')
meyectl.configure_multiprocessing()

io_loop = IOLoop.current()
server.configure_signals()


def timer(name):
    print(name, 'ran')
    io_loop.stop()
'''

# SIGTERM must stop the IO loop right away, not at its next timer: that timer is
# often the motion checker, which would restart motion during the shutdown.
_STOP = '''
io_loop.call_later(5, timer, 'the next timer')

# sent from another thread while the loop waits for that timer
threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGTERM)).start()

start = time.monotonic()
io_loop.start()
print(time.monotonic() - start)
'''

# The same when the signal is handled by another thread.
_OTHER_THREAD = '''
io_loop.call_later(5, timer, 'the next timer')


def send():
    signal.pthread_kill(threading.get_ident(), signal.SIGTERM)


threading.Timer(0.5, send).start()

start = time.monotonic()
io_loop.start()
print(time.monotonic() - start)
'''

# The motion checker must not run after SIGTERM, even when it fell due while
# the loop was busy: bye_handler() stops it before the loop gets to it.
_CHECKER = '''
server._motion_checker = PeriodicCallback(lambda: print('the checker ran'), 100)
server._motion_checker.start()


def busy():
    # like a synchronous motion restart, during which the checker falls due
    # and SIGTERM arrives
    time.sleep(0.5)
    os.kill(os.getpid(), signal.SIGTERM)


io_loop.add_callback(busy)

start = time.monotonic()
io_loop.start()
print(time.monotonic() - start)
'''

# A SIGTERM sent to a forked process, like a zip process that timed out, must not
# stop the IO loop of the server: before Python 3.12, forked processes inherit
# the signal wakeup fd.
_CHILD = '''
child = multiprocessing.Process(target=time.sleep, args=(2,))
child.start()
io_loop.call_later(0.3, os.kill, child.pid, signal.SIGTERM)
io_loop.call_later(2, io_loop.stop)

start = time.monotonic()
io_loop.start()
elapsed = time.monotonic() - start
child.join(5)
print(elapsed)
'''


def _run(script: str) -> subprocess.CompletedProcess:
    # make the child import the same motioneye package as this test
    env = dict(os.environ)
    package_root = os.path.dirname(os.path.dirname(motioneye.__file__))
    env['PYTHONPATH'] = os.pathsep.join(
        p for p in (package_root, env.get('PYTHONPATH')) if p
    )

    return subprocess.run(
        [sys.executable, '-c', _SETUP + script],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )


class TestServerSignals(unittest.TestCase):
    def _assert_clean(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_sigterm_stops_the_loop_right_away(self):
        result = _run(_STOP)

        self._assert_clean(result)
        self.assertNotIn('the next timer ran', result.stdout, result.stderr)
        self.assertLess(float(result.stdout.split()[-1]), 3)

    def test_sigterm_to_another_thread_stops_the_loop_right_away(self):
        result = _run(_OTHER_THREAD)

        self._assert_clean(result)
        self.assertNotIn('the next timer ran', result.stdout, result.stderr)
        self.assertLess(float(result.stdout.split()[-1]), 3)

    def test_the_motion_checker_does_not_run_after_sigterm(self):
        result = _run(_CHECKER)

        self._assert_clean(result)
        self.assertNotIn('the checker ran', result.stdout, result.stderr)
        self.assertLess(float(result.stdout.split()[-1]), 3)

    def test_sigterm_to_a_forked_process_keeps_the_loop_running(self):
        result = _run(_CHILD)

        self._assert_clean(result)
        self.assertGreater(float(result.stdout.split()[-1]), 1.9, result.stderr)


class RunPathTest(unittest.TestCase):
    """Only the background mode writes a pid file, so only it needs run_path."""

    def setUp(self):
        from motioneye import settings

        tmp_dir = mkdtemp()
        self.addCleanup(rmtree, tmp_dir)
        for patcher in (
            patch.multiple(
                settings,
                CONF_PATH=tmp_dir,
                MEDIA_PATH=tmp_dir,
                RUN_PATH=os.path.join(tmp_dir, 'missing'),
                LOG_TO_FILE=False,
                SMB_SHARES=False,
            ),
            patch('motioneye.meyectl.configure_logging'),
            patch('motioneye.meyectl.configure_tornado'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _main(self, background):
        from motioneye import server

        options = SimpleNamespace(background=background)
        with (
            patch.object(server, 'parse_options', return_value=options),
            patch.object(server, 'Daemon') as daemon,
            patch.object(server, 'run') as run,
        ):
            server.main(None, [], 'start')

        return daemon, run

    def test_the_requirements_do_not_include_run_path(self):
        from motioneye import server

        server.test_requirements()

    def test_the_server_starts_in_foreground_without_run_path(self):
        daemon, run = self._main(background=False)

        run.assert_called_once_with()
        daemon.assert_not_called()

    def test_the_background_mode_needs_a_writable_run_path(self):
        with self.assertRaises(SystemExit), self.assertLogs(level='CRITICAL') as logs:
            self._main(background=True)

        self.assertIn('pid directory', '\n'.join(logs.output))
