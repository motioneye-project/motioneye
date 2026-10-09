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

import unittest
from unittest.mock import Mock, patch

from motioneye import config, migration, server
from motioneye.handlers.config import ConfigHandler
from tests.test_notification_settings import (
    _CONF,
    _EMAIL,
    _MEYECTL,
    _MOMENT,
    _PYTHON,
    _RELAY,
    _STORED,
    _TELEGRAM,
    _UI,
    _ConfigCase,
    _find_command,
    _short,
)

# the arguments older versions wrote to motion's lines for _UI
_OLD_SENDMAIL = (
    "'smtp.example' '587' '007' 'p\\;w%%d FAKE-1234' 'True' '' 'a@example,b@example' "
    "'motion_start' '%t' '%Y-%m-%dT%H:%M:%S' '5'"
)
_FROM_LESS = _OLD_SENDMAIL.replace("'True' '' ", "'True' ")  # 0.27 to 0.30
_OLD_SENDTELEGRAM = "'123456:FAKE-token' '-1001234567' '%t' '%Y-%m-%dT%H:%M:%S' '10'"

# how motionEye versions and setups started the senders, {0} is the command
_WRAPPER = '/usr/local/sbin/motioneye-notify moteye-{0}'
_PY2 = '/usr/bin/python /usr/lib/python2.7/dist-packages/motioneye/meyectl.pyc'
_LAYOUTS = {
    'systemd': f'{_PYTHON} {_MEYECTL} {{0}} -c {_CONF}',
    'sysv': f'{_PYTHON} {_MEYECTL} {{0}} -c {_CONF} -l',
    'no -c': f'{_PYTHON} {_MEYECTL} {{0}}',
    '0.27 console script': f'/usr/local/bin/meyectl {{0}} -c {_CONF}',
    'wrapper': f'{_WRAPPER} {_PYTHON} {_MEYECTL} {{0}} -c {_CONF}',
    'motionEyeOS': f'{_PY2} {{0}} -c /data/etc/motioneye.conf -l',
}


def _old_start(line, layout='systemd', mail=_OLD_SENDMAIL):
    # on_event_start of a UI save, with the senders as older versions wrote them
    email = f"{_LAYOUTS[layout].format('sendmail')} {mail}"
    telegram = f"{_LAYOUTS[layout].format('sendtelegram')} {_OLD_SENDTELEGRAM}"
    line = line.replace(_short('sendmail'), email)
    return line.replace(_short('sendtelegram'), telegram)


def _old_sender(name='sendmail'):
    arguments = _OLD_SENDTELEGRAM if name == 'sendtelegram' else _OLD_SENDMAIL
    return f'{_find_command(name)} {arguments}'


class MigrationTest(_ConfigCase):
    def setUp(self):
        super().setUp()
        self.fresh = self._save(**_UI)  # what a save in the UI stores

    def _old_camera(self, layout='systemd', mail=_OLD_SENDMAIL):
        # the same camera as older versions saved it
        stored = {f'@{name}' for name in _STORED}
        camera = {key: value for key, value in self.fresh.items() if key not in stored}
        camera['on_event_start'] = _old_start(camera['on_event_start'], layout, mail)
        return camera

    def _move(self, camera):
        return migration._move_notification_settings(1, camera)

    def test_old_lines_are_converted(self):
        for layout in _LAYOUTS:
            for mail in (_OLD_SENDMAIL, _FROM_LESS):
                with self.subTest(layout, from_less=mail is _FROM_LESS):
                    camera = self._old_camera(layout, mail)
                    self.assertTrue(self._move(camera))
                    self.assertEqual(self.fresh, camera)  # the same as a UI save

        password = self.fresh['@email_notifications_smtp_password']
        self.assertEqual('p;w%d FAKE-1234', password)

    def test_sender_is_kept(self):
        mail = _OLD_SENDMAIL.replace("'True' ''", "'True' 'me@example'")
        for layout in ('no -c', '0.27 console script', 'sysv'):
            with self.subTest(layout):
                camera = self._old_camera(layout, mail)
                self.assertTrue(self._move(camera))
                server = camera['@email_notifications_smtp_server']
                self.assertEqual('smtp.example', server)
                self.assertEqual('me@example', camera['@email_notifications_from'])

    def test_conversion_is_idempotent(self):
        camera = self._old_camera('wrapper')
        self.assertTrue(self._move(camera))
        converted = dict(camera)
        self.assertFalse(self._move(camera))
        self.assertEqual(converted, camera)

        wrapped = f"/usr/local/sbin/motioneye-notify mail {_short('sendmail')}"
        debug = f"{_find_command('sendtelegram')} -l -d %t '{_MOMENT}'"
        line = f'{_RELAY} start %t; {wrapped}; {debug}'
        camera = dict(self.fresh, on_event_start=line)
        self.assertFalse(self._move(camera))
        self.assertEqual(dict(self.fresh, on_event_start=line), camera)

    def test_other_parts_keep_their_exact_text(self):
        hook = f"{_find_command('webhook')} 'GET' 'https://x.example/?a=%t'"
        others = [
            "find /tmp -exec rm {} \\;",
            "echo 'a;b'",
            'case $1 in a) x;; esac',
            hook,
        ]
        rest = ';'.join(others)
        line = f"{_RELAY} start %t;  {_old_sender('sendtelegram')}  ;{rest}"
        camera = {'@id': 1, 'on_event_start': line}
        self.assertTrue(self._move(camera))
        expected = f"{_RELAY} start %t;  {_short('sendtelegram')}  ;{rest}"
        self.assertEqual(expected, camera['on_event_start'])

    def test_custom_commands_are_left_alone(self):
        email = _old_sender()
        customs = (
            "printf 'Subject: x' | sendmail -f a@example b@example",
            'cat /tmp/m | /usr/sbin/sendmail -f me@x -F me -t a b c d e f g h',
            email.replace("'%t'", "'1'"),  # a fixed camera id
            email.replace(_MOMENT, '%s'),  # another moment format
            _old_sender('sendtelegram').replace(_MOMENT, '%Y%m%d'),
        )
        for custom in customs:
            with self.subTest(custom=custom):
                line = f'{_RELAY} start %t; {custom}'
                camera = {'@id': 1, 'on_event_start': line}
                self.assertFalse(self._move(camera))
                self.assertEqual({'@id': 1, 'on_event_start': line}, camera)

    def test_only_the_first_old_part_is_converted(self):
        first = _old_sender('sendtelegram')
        second = first.replace('FAKE-token', 'FAKE-other')
        camera = {'@id': 1, 'on_event_start': f'{_RELAY} start %t; {first}; {second}'}
        with self.assertLogs(level='WARNING') as logs:
            self.assertTrue(self._move(camera))

        warning = 'WARNING:root:could not move sendtelegram settings of camera 1'
        self.assertEqual([warning], logs.output)
        expected = f"{_RELAY} start %t; {_short('sendtelegram')}; {second}"
        self.assertEqual(expected, camera['on_event_start'])
        self.assertEqual('123456:FAKE-token', camera['@telegram_notifications_api'])

    def test_line_wins_over_stale_settings(self):
        camera = self._old_camera()
        camera['@email_notifications_smtp_password'] = 'FAKE-stale'
        camera['@telegram_notifications_api'] = 'FAKE-stale'
        self.assertTrue(self._move(camera))
        self.assertEqual(self.fresh, camera)

    def test_unparsable_part_is_skipped(self):
        custom = "printf 'Subject: a;b' | sendmail -t a@example"  # split at the ;
        broken = _old_sender().replace('p\\;w%%d', "FAKE-p'w")  # unbalanced quotes
        telegram = _old_sender('sendtelegram')
        line = f'{_RELAY} start %t; {custom}; {broken}; {telegram}'
        camera = {'@id': 1, 'on_event_start': line}
        with self.assertLogs(level='WARNING') as logs:
            self.assertTrue(self._move(camera))

        warning = 'WARNING:root:could not read on_event_start command of camera 1'
        self.assertEqual([warning], logs.output)  # once per camera
        short = _short('sendtelegram')
        expected = f'{_RELAY} start %t; {custom}; {broken}; {short}'
        self.assertEqual(expected, camera['on_event_start'])

        camera = {'@id': 1, 'on_event_start': f'{_RELAY} start %t; {custom}; {short}'}
        with self.assertLogs(level='WARNING') as logs:
            self.assertFalse(self._move(camera))

        self.assertEqual([warning], logs.output)  # a quoted ; is split there too

    def test_old_part_next_to_a_short_form_is_kept(self):
        # e.g. added by hand, the settings from the UI stay
        old = _old_sender().replace('a@example,b@example', 'other@example')
        line = f"{self.fresh['on_event_start']}; {old}"
        camera = dict(self.fresh, on_event_start=line)
        with self.assertLogs(level='WARNING') as logs:
            self.assertFalse(self._move(camera))

        warning = 'WARNING:root:could not move sendmail settings of camera 1'
        self.assertEqual([warning], logs.output)
        self.assertEqual(dict(self.fresh, on_event_start=line), camera)

    def test_spaces_around_values_are_reported(self):
        mail = _OLD_SENDMAIL.replace('p\\;w%%d FAKE-1234', ' FAKE-pw ')
        camera = self._old_camera(mail=mail)
        with self.assertLogs(level='WARNING') as logs:
            self.assertTrue(self._move(camera))

        key = 'email_notifications_smtp_password'
        warning = f'WARNING:root:removed spaces around {key} of camera 1'
        self.assertEqual([warning], logs.output)
        self.assertEqual('FAKE-pw', camera[f'@{key}'])

    def test_ui_shows_the_same_settings(self):
        # as motion_camera_dict_to_ui() of older versions showed the old lines
        camera = self._old_camera()
        self._move(camera)
        ui = config.motion_camera_dict_to_ui(camera)
        expected = dict(_EMAIL, **_TELEGRAM)
        self.assertEqual(expected, {name: ui[name] for name in expected})
        self.assertIs(True, ui['email_notifications_smtp_tls'])
        self.assertEqual(10, ui['telegram_notifications_picture_time_span'])


class StartupTest(_ConfigCase):
    def setUp(self):
        super().setUp()
        self.fresh = self._save(**_UI)
        stored = {f'@{name}' for name in _STORED}
        self.old = {k: v for k, v in self.fresh.items() if k not in stored}
        self.old['on_event_start'] = _old_start(self.fresh['on_event_start'])

    def test_startup_never_fails(self):
        broken = _old_sender().replace('p\\;w%%d', "FAKE-p'w")  # unbalanced quotes
        self._write(1, self.old)
        self._write(2, dict(self.old, on_event_start=f'{_RELAY} start %t; {broken}'))
        self._write(3, self.old)  # its write fails
        self._write(4, self.old)
        self._write_text(5, '# @proto motioneye\n# @host 192.168.1.2\n')
        files = {camera_id: self._read(camera_id) for camera_id in range(1, 6)}
        set_camera = config.set_camera

        def fail_for_3(camera_id, camera_config):
            if camera_id != 3:
                return set_camera(camera_id, camera_config)

            config._camera_config_cache[camera_id] = camera_config  # cached first
            raise OSError('read-only file system')

        self._patch('motioneye.config.get_camera_ids', return_value=[1, 2, 3, 4, 5])
        writes = self._patch('motioneye.config.set_camera', side_effect=fail_for_3)
        with self.assertLogs(level='INFO') as logs:
            migration.migrate_cameras()

        self.assertEqual([1, 3, 4], [c.args[0] for c in writes.call_args_list])
        output = '\n'.join(logs.output)
        self.assertNotIn('FAKE-', output)
        warning = 'WARNING:root:could not read on_event_start command of camera 2'
        self.assertIn(warning, output)
        error = 'ERROR:root:failed to migrate camera 3: read-only file system'
        self.assertIn(error, logs.output)
        for camera_id in (2, 3, 5):
            self.assertEqual(files[camera_id], self._read(camera_id))

        kept = config.get_camera(3)['on_event_start']  # as in the file
        self.assertEqual(self.old['on_event_start'], kept)
        config.invalidate()
        for camera_id in (1, 4):
            moved = config.get_camera(camera_id)
            self.assertEqual(self.fresh['on_event_start'], moved['on_event_start'])
            for name, value in _STORED.items():
                self.assertEqual(value, moved[f'@{name}'])

        writes.reset_mock()
        migration.migrate_cameras()  # the next start
        self.assertEqual([3], [c.args[0] for c in writes.call_args_list])

        error = OSError('no such directory')
        self._patch('motioneye.config.get_camera_ids', side_effect=error)
        migration.migrate_cameras()

    def test_startup_needs_free_space(self):
        self._write(1, self.old)
        text = self._read(1)
        self._patch('motioneye.config.get_camera_ids', return_value=[1])
        full = Mock(free=1000)
        usage = self._patch('motioneye.migration.disk_usage', return_value=full)
        writes = self._patch('motioneye.config.set_camera')
        with self.assertLogs(level='ERROR') as logs:
            migration.migrate_cameras()

        writes.assert_not_called()
        usage.assert_called_once_with(self.conf_dir)
        error = 'ERROR:root:failed to migrate camera 1: less than 1 MiB free'
        self.assertEqual([error], logs.output)
        self.assertEqual(text, self._read(1))
        kept = config.get_camera(1)['on_event_start']
        self.assertEqual(self.old['on_event_start'], kept)

    def test_startup_migrates_after_logging_is_configured(self):
        calls = Mock()
        options = Mock(background=False, log_to_file=False)
        self._patch('motioneye.server.parse_options', return_value=options)
        self._patch('motioneye.meyectl.configure_logging', calls.configure_logging)
        self._patch('motioneye.meyectl.configure_tornado')
        self._patch('motioneye.server.configure_signals')
        self._patch('motioneye.utils.authstate.build_password_hash_state')
        self._patch('motioneye.utils.authstate.set_password_hash_state')
        self._patch('motioneye.utils.authstate.validate_password_hash_state')
        self._patch('motioneye.migration.migrate_cameras', calls.migrate_cameras)
        self._patch('motioneye.server.test_requirements', calls.test_requirements)
        self._patch('motioneye.server.make_media_folders', calls.make_media_folders)
        calls.start_motion.side_effect = StopIteration  # stop before motion starts
        self._patch('motioneye.server.start_motion', calls.start_motion)
        with self.assertRaises(StopIteration):
            server.main(Mock(), [], 'start')

        names = [name for name, _, _ in calls.mock_calls]
        expected = ['configure_logging', 'test_requirements', 'make_media_folders']
        self.assertEqual(expected + ['migrate_cameras', 'start_motion'], names)

    def test_restore_converts_older_backups(self):
        self._write(1, self.old)
        backup = config.backup()
        self._write(1, self.camera)  # what is there before restoring
        handler = Mock(current_user='admin')
        handler.get_argument.return_value = None
        handler.request.files = {'files': [{'body': backup}]}

        self._patch('motioneye.settings.ENABLE_REBOOT', False)
        with self.assertLogs(level='INFO') as logs:
            ConfigHandler.restore(handler)

        handler.finish_json.assert_called_once_with({'ok': True, 'reboot': False})
        moving = 'INFO:root:moving notification settings of camera 1'
        self.assertIn(moving, logs.output)
        text = self._read(1)
        self.assertIn('\n# @email_notifications_smtp_password p;w%d FAKE-1234\n', text)
        config.invalidate()
        restored = config.get_camera(1)['on_event_start']
        self.assertEqual(self.fresh['on_event_start'], restored)

    def test_restore_converts_only_without_reboot(self):
        # caches are not invalidated then, migrate_cameras() would save old configs
        migrate = self._patch('motioneye.migration.migrate_cameras')
        handler = Mock(current_user='admin')
        handler.get_argument.return_value = None
        handler.request.files = {'files': [{'body': b''}]}
        for result in ({'reboot': True}, None):
            with self.subTest(result=result):  # noqa: SIM117
                with patch('motioneye.config.restore', return_value=result):
                    ConfigHandler.restore(handler)

        migrate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
