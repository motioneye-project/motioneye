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


def _removed_warning(name):
    return (
        f'WARNING:root:{name} was removed and is ignored: HTTPS certificates are '
        'always verified now; turn the check off per remote camera, upload '
        'service or webhook (Verify certificate) instead'
    )


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
                self.assertIn(f'unknown log level: "{name}"', '\n'.join(logs.output))


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
        # a world-readable file adds an "insecure mode" warning that depends on the umask
        os.chmod(conf_file, 0o600)

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

    def test_validate_certs_is_gone_and_only_warns(self):
        with self.assertLogs(level='WARNING') as logs:
            self._load_settings('validate_certs false\n')

        self.assertEqual([_removed_warning('validate_certs')], logs.output)
        self.assertFalse(hasattr(settings, 'VALIDATE_CERTS'))

    def test_validate_certs_with_a_dash_warns_the_same_way(self):
        with self.assertLogs(level='WARNING') as logs:
            self._load_settings('validate-certs true\n')

        self.assertEqual([_removed_warning('validate-certs')], logs.output)

    def test_an_unknown_option_is_only_reported(self):
        with self.assertLogs(level='WARNING') as logs:
            self._load_settings('no_such_option 1\n')

        warning = 'WARNING:root:unknown configuration option: no_such_option'
        self.assertEqual([warning], logs.output)


class _FakeSysLogHandler(logging.Handler):
    ident = ''

    def __init__(self, address):
        super().__init__()
        self.address = address
        self.messages = []

    def emit(self, record):
        self.messages.append(self.ident + self.format(record))


class ConfigureLoggingSyslogTest(unittest.TestCase):
    # configure_logging() replaces the root logger's handlers, restore them
    def setUp(self):
        root = logging.getLogger()
        self.saved_handlers = root.handlers[:]
        self.saved_level = root.level
        self.log_dir = mkdtemp()
        self.addCleanup(rmtree, self.log_dir)

    def tearDown(self):
        self._reset_logging()

    def _reset_logging(self):
        root = logging.getLogger()
        for h in root.handlers[:]:
            if h not in self.saved_handlers:
                root.removeHandler(h)
                h.close()

        for h in self.saved_handlers:
            if h not in root.handlers:
                root.addHandler(h)

        root.setLevel(self.saved_level)

    def _configure(self, cmd, log_to_file=False, dev_log=True, syslog_handler=None):
        self._reset_logging()
        handlers = []

        def fake_syslog_handler(address):
            handlers.append(_FakeSysLogHandler(address))
            return handlers[-1]

        exists = os.path.exists
        with (
            patch.multiple(settings, LOG_TO_FILE=log_to_file, LOG_PATH=self.log_dir),
            patch(
                'motioneye.meyectl.SysLogHandler', syslog_handler or fake_syslog_handler
            ),
            patch(
                'motioneye.meyectl.os.path.exists',
                side_effect=lambda p: dev_log if p == '/dev/log' else exists(p),
            ),
        ):
            meyectl.configure_logging(cmd)

        return handlers

    def test_event_commands_also_log_to_syslog(self):
        for cmd in ('sendmail', 'telegram', 'webhook'):
            with self.subTest(cmd=cmd):
                handlers = self._configure(cmd)
                logging.error('failed to send')

                self.assertEqual(['/dev/log'], [h.address for h in handlers])
                self.assertEqual(
                    [f'meyectl[{os.getpid()}]: [{cmd}] ERROR: failed to send'],
                    handlers[0].messages,
                )

    def test_no_syslog_where_the_output_is_not_muted(self):
        for cmd, log_to_file, dev_log in (
            ('motioneye', False, True),
            ('shell', False, True),
            ('sendmail', True, True),
            ('sendmail', False, False),
        ):
            with self.subTest(cmd=cmd, log_to_file=log_to_file, dev_log=dev_log):
                self.assertEqual([], self._configure(cmd, log_to_file, dev_log))

    def test_a_syslog_failure_does_not_stop_the_command(self):
        def broken_syslog_handler(address):
            raise FileNotFoundError(2, 'No such file or directory', address)

        # neither raises nor exits, as before Python 3.11 when nothing listens
        self._configure('sendmail', syslog_handler=broken_syslog_handler)


if __name__ == '__main__':
    unittest.main()
