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

"""Tests verifying where motion logs to, and how its process is tracked."""

import os
import sys
import unittest
from contextlib import ExitStack
from shutil import rmtree
from subprocess import DEVNULL, Popen, TimeoutExpired
from tempfile import mkdtemp
from unittest.mock import Mock, patch

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

            stack.enter_context(patch.object(motionctl, '_process', None))
            popen = stack.enter_context(patch.object(motionctl, 'Popen'))
            popen.return_value.poll.return_value = None
            popen.return_value.pid = 1234
            motionctl.start()
            self.process = motionctl._process

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

    def test_the_process_is_kept_without_a_pid_file(self):
        self._start(log_to_file=False)

        self.assertIsNotNone(self.process)
        self.assertEqual([], os.listdir(self.tmp_dir))


class MotionProcessTest(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.object(motionctl, '_process', None),
            patch('motioneye.mjpgclient.close_all'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _child(self):
        process = Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def test_nothing_runs_before_motion_was_started(self):
        self.assertFalse(motionctl.running())

    def test_a_running_process_is_stopped_with_term(self):
        motionctl._process = self._child()
        self.assertTrue(motionctl.running())

        motionctl.stop()

        self.assertFalse(motionctl.running())
        self.assertEqual(-15, motionctl._process.returncode)

    def test_a_process_that_ignores_term_is_killed(self):
        process = Mock(**{'poll.return_value': None})
        process.wait.side_effect = [TimeoutExpired('motion', 5), 0]
        motionctl._process = process

        motionctl.stop()

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()

    def test_a_process_that_does_not_exit_is_reported(self):
        process = Mock(**{'poll.return_value': None})
        process.wait.side_effect = TimeoutExpired('motion', 5)
        motionctl._process = process

        with (
            patch.object(motionctl.settings, 'ENABLE_REBOOT', False),
            self.assertRaisesRegex(RuntimeError, 'could not terminate'),
        ):
            motionctl.stop()

    def test_a_stale_pid_file_is_ignored(self):
        # an unrelated process, whose PID a motion.pid file of an older motionEye holds
        other = self._child()
        run_dir = mkdtemp()
        self.addCleanup(rmtree, run_dir)
        with open(os.path.join(run_dir, 'motion.pid'), 'w') as f:
            f.write(f'{other.pid}\n')

        with patch.object(motionctl.settings, 'RUN_PATH', run_dir):
            self.assertFalse(motionctl.running())
            motionctl.stop()

        self.assertIsNone(other.poll())


if __name__ == '__main__':
    unittest.main()
