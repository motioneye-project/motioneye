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
import stat
import sys
import unittest
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import meyectl, settings

# load_settings() changes these, restore them after each test
_PATHS = ('CONF_PATH', 'RUN_PATH', 'LOG_PATH', 'MEDIA_PATH')


def _removed_warning(name, path):
    return (
        f'WARNING:root:{name} in {path} was removed and is ignored: HTTPS '
        'certificates are always verified now; remove that line, and turn the '
        'check off per remote camera, upload service or webhook (Verify '
        'certificate) where needed'
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

        path = os.path.join(self.conf_dir, 'motioneye.conf')
        self.assertEqual([_removed_warning('validate_certs', path)], logs.output)
        self.assertFalse(hasattr(settings, 'VALIDATE_CERTS'))

    def test_validate_certs_with_a_dash_warns_the_same_way(self):
        with self.assertLogs(level='WARNING') as logs:
            self._load_settings('validate-certs true\n')

        path = os.path.join(self.conf_dir, 'motioneye.conf')
        self.assertEqual([_removed_warning('validate-certs', path)], logs.output)

    def test_an_unknown_option_is_only_reported(self):
        with self.assertLogs(level='WARNING') as logs:
            self._load_settings('no_such_option 1\n')

        warning = 'WARNING:root:unknown configuration option: no_such_option'
        self.assertEqual([warning], logs.output)


class ConfigFileModeTest(unittest.TestCase):
    # the settings may hold credentials (motion_control_authentication)
    _SETTINGS = LoadSettingsLogToFileTest._SETTINGS + ('MOTION_CONTROL_AUTHENTICATION',)

    def setUp(self):
        self.conf_dir = mkdtemp()
        self.conf_file = os.path.join(self.conf_dir, 'motioneye.conf')
        with open(self.conf_file, 'w') as f:
            f.write('motion_control_authentication user:pass\n')

        self.saved = {name: getattr(settings, name) for name in self._SETTINGS}

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(settings, name, value)

        rmtree(self.conf_dir)

    def _load_settings(self):
        with patch.object(
            sys, 'argv', ['meyectl', 'startserver', '-c', self.conf_file]
        ):
            meyectl.load_settings()

        return stat.S_IMODE(os.stat(self.conf_file).st_mode)

    def test_access_for_others_is_removed(self):
        os.chmod(self.conf_file, 0o644)
        with self.assertLogs(level='WARNING') as logs:
            self.assertEqual(0o600, self._load_settings())

        self.assertIn('insecure mode 0644, applying 0600', '\n'.join(logs.output))
        self.assertEqual('user:pass', settings.MOTION_CONTROL_AUTHENTICATION)

    def test_failing_chmod_does_not_prevent_starting(self):
        os.chmod(self.conf_file, 0o644)
        with (
            patch('motioneye.meyectl.os.chmod', side_effect=PermissionError('denied')),
            self.assertLogs(level='WARNING') as logs,
        ):
            self.assertEqual(0o644, self._load_settings())

        self.assertIn('could not harden mode', '\n'.join(logs.output))
        self.assertEqual('user:pass', settings.MOTION_CONTROL_AUTHENTICATION)


class HardenConfigFileModeTest(unittest.TestCase):
    # motionEye runs as motion (UID/GID 1000)
    def _harden(self, mode, uid, gid):
        st = os.stat_result((stat.S_IFREG | mode, 0, 0, 1, uid, gid, 0, 0, 0, 0))
        with (
            patch('motioneye.meyectl.os.stat', return_value=st),
            patch('motioneye.meyectl.os.geteuid', return_value=1000),
            patch('motioneye.meyectl.os.getegid', return_value=1000),
            patch('motioneye.meyectl.os.chmod') as chmod,
            patch('motioneye.meyectl.logging.warning') as warning,
        ):
            meyectl._harden_config_file_mode('/etc/motioneye/motioneye.conf')

        return chmod, ' '.join(str(c.args[0]) for c in warning.call_args_list)

    def test_secure_modes_are_kept_silently(self):
        for mode, uid, gid in (
            (0o640, 0, 1000),  # root:motion, as applied by motioneye_init
            (0o600, 1000, 1000),  # motion:motion
            (0o600, 1000, 0),
            (0o440, 0, 1000),
            (0o400, 1000, 1000),
            (0o400, 1000, 0),
        ):
            with self.subTest(mode=f'{mode:04o}', uid=uid, gid=gid):
                chmod, warnings = self._harden(mode, uid, gid)
                chmod.assert_not_called()
                self.assertEqual('', warnings)

    def test_access_for_others_is_removed(self):
        chmod, warnings = self._harden(0o644, 1000, 1000)
        chmod.assert_called_once_with('/etc/motioneye/motioneye.conf', 0o600)
        self.assertIn('applying 0600', warnings)

    def test_access_for_another_group_is_removed(self):
        chmod, warnings = self._harden(0o640, 1000, 2000)
        chmod.assert_called_once_with('/etc/motioneye/motioneye.conf', 0o600)
        self.assertIn('applying 0600', warnings)

    def test_root_owned_file_is_left_to_the_admin(self):
        chmod, warnings = self._harden(0o644, 0, 1000)
        chmod.assert_not_called()
        self.assertIn('insecure mode 0644, please apply 0640 with root:1000', warnings)

    def test_root_owned_file_with_another_group_is_left_to_the_admin(self):
        chmod, warnings = self._harden(0o640, 0, 2000)
        chmod.assert_not_called()
        self.assertIn('insecure mode 0640, please apply 0640 with root:1000', warnings)

    def test_file_owned_by_another_user_is_reported(self):
        chmod, warnings = self._harden(0o600, 2000, 1000)
        chmod.assert_not_called()
        self.assertIn('owned by another user (UID 2000)', warnings)
        self.assertIn('owner:group to root:1000 and mode to 0640', warnings)


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
