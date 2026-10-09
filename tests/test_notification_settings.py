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

import io
import os
import socket
import unittest
from datetime import datetime
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import config, meyectl, sendmail, sendtelegram

_CONF = '/data/motioneye/motioneye.conf'
_PACKAGE = '/usr/lib/python3.14/site-packages/motioneye'
_PYTHON = '/usr/bin/python3'
_MEYECTL = f'{_PACKAGE}/meyectl.py'
_RELAY = f'{_PACKAGE}/scripts/relayevent.sh "{_CONF}"'
_MOMENT = '%Y-%m-%dT%H:%M:%S'  # motion expands it to the event time
_EVENT = '2026-01-01T00:00:00'

# Home Assistant's webhooks, see its tests/components/motioneye/test_web_hooks.py
_HA = 'http://192.168.1.10:8123/api/webhook/' + 'ab' * 32
_MOTION_DETECTED = (
    'camera_id=%t&changed_pixels=%D&despeckle_labels=%Q&event=%v&fps=%{fps}'
    '&frame_number=%q&height=%h&host=%{host}&motion_center_x=%K'
    '&motion_center_y=%L&motion_height=%J&motion_version=%{ver}&motion_width=%i'
    '&noise_level=%N&threshold=%o&width=%w&src=hass-motioneye'
    '&event_type=motion_detected'
)
_FILE_STORED = (
    'camera_id=%t&event=%v&file_path=%f&file_type=%n&fps=%{fps}&frame_number=%q'
    '&height=%h&host=%{host}&motion_version=%{ver}&noise_level=%N&threshold=%o'
    '&width=%w&src=hass-motioneye&event_type=file_stored'
)
_DEVICE = 'device_id=e3b0c44298fc1c149afbf4c8996fb924'
_MOTION_URL = f'{_HA}?{_MOTION_DETECTED}&{_DEVICE}'
_STORAGE_URL = f'{_HA}?{_FILE_STORED}&{_DEVICE}'
_END_URL = 'https://discord.example/api/webhooks/42/hook?at=%H:%M'
_CUSTOM = "mosquitto_pub -t cam/%t -m start; echo 'a b'"

# notification fields of a camera, as GET returns them
_UI = {
    'email_notifications_enabled': True,
    'email_notifications_smtp_server': 'smtp.example',
    'email_notifications_smtp_port': '587',
    'email_notifications_smtp_account': '007',
    'email_notifications_smtp_password': 'p;w%d FAKE-1234',
    'email_notifications_smtp_tls': True,
    'email_notifications_from': '',
    'email_notifications_addresses': 'a@example,b@example',
    'email_notifications_picture_time_span': 5,
    'telegram_notifications_enabled': True,
    'telegram_notifications_api': '123456:FAKE-token',
    'telegram_notifications_chat_id': '-1001234567',
    'telegram_notifications_picture_time_span': 10,
    'web_hook_notifications_enabled': True,
    'web_hook_notifications_http_method': 'POSTj',
    'web_hook_notifications_url': _MOTION_URL,
    'web_hook_end_notifications_enabled': True,
    'web_hook_end_notifications_http_method': 'GET',
    'web_hook_end_notifications_url': _END_URL,
    'web_hook_storage_enabled': True,
    'web_hook_storage_http_method': 'POSTj',
    'web_hook_storage_url': _STORAGE_URL,
    'command_notifications_enabled': True,
    'command_notifications_exec': _CUSTOM,
}
_EMAIL = {name: value for name, value in _UI.items() if name.startswith('email_')}
_TELEGRAM = {name: value for name, value in _UI.items() if name.startswith('telegr')}

# what a save of _UI stores in camera-N.conf, as "# @<name> <text>" lines
_STORED = {
    'email_notifications_smtp_server': 'smtp.example',
    'email_notifications_smtp_port': '587',
    'email_notifications_smtp_account': '007',
    'email_notifications_smtp_password': 'p;w%d FAKE-1234',
    'email_notifications_smtp_tls': 'True',
    'email_notifications_from': '',
    'email_notifications_addresses': 'a@example,b@example',
    'email_notifications_picture_time_span': '5',
    'telegram_notifications_api': '123456:FAKE-token',
    'telegram_notifications_chat_id': '-1001234567',
    'telegram_notifications_picture_time_span': '10',
}
_STORED_LINES = ('# @email_notifications', '# @telegram_notifications')

# email and Telegram settings must not be on motion's lines (ps, motion's log)
_HIDDEN = ('smtp.example', '587', '007', 'p;w%d', 'a@example', 'FAKE-', '-1001234567')


def _find_command(command):
    # meyectl.find_command() of a server started with "-c _CONF"
    if command == 'relayevent':
        return _RELAY

    return f'{_PYTHON} {_MEYECTL} {command} -c {_CONF}'


def _short(name):
    return f"{_find_command(name)} %t '{_MOMENT}'"


def _new_lines():
    # motion's lines for _UI: the senders read their settings, webhooks as on dev
    hook = _find_command('webhook')
    start = [f'{_RELAY} start %t', _short('sendmail'), _short('sendtelegram')]
    start += [f"{hook} 'POSTj' '{_MOTION_URL}'", _CUSTOM]
    storage = f"{hook} 'POSTj' '{_STORAGE_URL}'"
    return {
        'on_event_start': '; '.join(start),
        'on_event_end': f"{_RELAY} stop %t; {hook} 'GET' '{_END_URL}'",
        'on_movie_end': f'{_RELAY} movie_end %t %f; {storage}',
        'on_picture_save': f'{_RELAY} picture_save %t %f; {storage}',
    }


def _ha_sets_webhook(camera, kind, url):
    # Home Assistant's _set_webhook() decision for a webhook it set before
    enabled = camera.get(f'web_hook_{kind}_enabled', False)
    method = camera.get(f'web_hook_{kind}_http_method')
    current = camera.get(f'web_hook_{kind}_url')
    return not enabled or method != 'POSTj' or current != url


class _ConfigCase(unittest.TestCase):
    # camera 1, a local network camera, with its files in a temporary CONF_PATH
    def setUp(self):
        self.conf_dir = mkdtemp()
        self.addCleanup(rmtree, self.conf_dir)
        config.invalidate()
        self.addCleanup(config.invalidate)

        main_config = {}
        config._set_default_motion(main_config)
        self._patch('builtins._', str, create=True)
        self._patch('motioneye.meyectl.find_command', _find_command)
        self._patch('motioneye.config.get_main', return_value=main_config)
        self._patch('motioneye.config.set_main')
        self._patch('motioneye.settings.CONF_PATH', self.conf_dir)
        no_ffmpeg = (None, None, None)
        self._patch('motioneye.mediafiles.find_ffmpeg', return_value=no_ffmpeg)
        self._patch('motioneye.motionctl.is_motion_pre42', return_value=False)
        self._patch('motioneye.motionctl.is_motion_post43', return_value=False)
        self._patch('motioneye.utils.get_disk_usage', return_value=None)  # not stable
        self._patch('motioneye.controls.diskctl.list_mounted_disks', return_value=[])

        self.camera = {'@id': 1, '@enabled': True, 'netcam_url': 'rtsp://example/'}
        self.camera.update(width=640, height=480)
        config._set_default_motion_camera(1, self.camera)
        self.camera['target_dir'] = self.conf_dir

    def _patch(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _path(self, camera_id):
        return os.path.join(self.conf_dir, f'camera-{camera_id}.conf')

    def _write_text(self, camera_id, text):
        with open(self._path(camera_id), 'w') as f:
            f.write(text)

        os.chmod(self._path(camera_id), 0o600)

    def _write(self, camera_id, data):
        # camera-N.conf as set_camera() writes it
        lines = config._dict_to_conf([], dict(data, **{'@id': camera_id}))
        self._write_text(camera_id, '\n'.join(lines) + '\n')

    def _read(self, camera_id):
        with open(self._path(camera_id)) as f:
            return f.read()

    def _save(self, **notifications):
        # motion_camera_ui_to_dict() of camera 1 with these notification fields
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(notifications)
        return config.motion_camera_ui_to_dict(ui, self.camera)

    def _get(self, camera_id=1):
        # GET /config/N/get/, read from the file
        config._camera_config_cache.pop(camera_id, None)
        return config.motion_camera_dict_to_ui(config.get_camera(camera_id))

    def _post(self, ui, camera_id=1):
        # POST /config/N/set/, see handlers/config.py
        data = config.motion_camera_ui_to_dict(ui, config.get_camera(camera_id))
        config.set_camera(camera_id, data)


class ConfigTest(_ConfigCase):
    def test_lines_hold_no_email_or_telegram_settings(self):
        expected = _new_lines()
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(_UI)
        for prev_config in (self.camera, None):  # None as in handlers/picture.py
            with self.subTest(prev_config=bool(prev_config)):
                data = config.motion_camera_ui_to_dict(dict(ui), prev_config)
                lines = {option: data[option] for option in expected}

                self.assertEqual(expected, lines)
                for line in lines.values():
                    for value in _HIDDEN:
                        self.assertNotIn(value, line)

    def test_settings_round_trip_through_the_camera_file(self):
        numbers = {  # must stay text
            'email_notifications_smtp_server': 'on',
            'email_notifications_smtp_port': '1234',
            'email_notifications_smtp_account': '007',
            'telegram_notifications_api': '1e5',
        }
        ui = dict(_UI, **numbers)
        self._write(1, self._save(**ui))

        text = '\n' + self._read(1)
        for name, value in dict(_STORED, **numbers).items():
            self.assertIn(f'\n# @{name} {value}\n', text)

        got = self._get()
        self.assertEqual(ui, {name: got[name] for name in ui})

    def test_cache_equals_the_file(self):
        self._write(1, self.camera)
        ui = dict(self._get(), **_UI)
        ui['email_notifications_smtp_password'] = '  pw  '
        self._post(ui)

        cached = config.motion_camera_dict_to_ui(config.get_camera(1))
        self.assertEqual('pw', cached['email_notifications_smtp_password'])
        self.assertIn('\n# @email_notifications_smtp_password pw\n', self._read(1))

        config.invalidate()
        self.assertEqual(cached, self._get())

    def test_home_assistant_get_post_is_a_fixed_point(self):
        hooks = {  # what Home Assistant sets
            'web_hook_notifications_enabled': True,
            'web_hook_notifications_http_method': 'POSTj',
            'web_hook_notifications_url': _MOTION_URL,
            'web_hook_storage_enabled': True,
            'web_hook_storage_http_method': 'POSTj',
            'web_hook_storage_url': _STORAGE_URL,
        }
        self._write(1, self.camera)
        self._post(dict(self._get(), **_EMAIL, **_TELEGRAM, **hooks))
        text = self._read(1)

        got = self._get()
        self.assertEqual(hooks, {name: got[name] for name in hooks})
        self.assertFalse(_ha_sets_webhook(got, 'notifications', _MOTION_URL))
        self.assertFalse(_ha_sets_webhook(got, 'storage', _STORAGE_URL))

        self._post(got)
        self.assertEqual(text, self._read(1))
        self.assertEqual(got, self._get())

    def test_disabled_notifications_keep_no_settings(self):
        self._write(1, self.camera)
        self._post(dict(self._get(), **_UI))
        lines = self._read(1).splitlines()
        stored = [line for line in lines if line.startswith(_STORED_LINES)]
        self.assertEqual(11, len(stored))

        off = {'email_notifications_enabled': False}
        off['telegram_notifications_enabled'] = False
        self._post(dict(self._get(), **off))
        text = self._read(1)
        lines = text.splitlines()
        self.assertEqual([], [line for line in lines if line.startswith(_STORED_LINES)])

        got = self._get()  # no detail fields while disabled
        self.assertNotIn('email_notifications_smtp_password', got)
        self.assertNotIn('telegram_notifications_api', got)
        self._post(got)
        self.assertEqual(text, self._read(1))

    def test_line_breaks_are_refused(self):
        fields = ('email_notifications_smtp_password', 'telegram_notifications_api')
        for name in fields:
            for value in ('a\nFAKE-secret', 'a\rFAKE-secret'):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError) as raised:
                        self._save(**dict(_UI, **{name: value}))

                    message = str(raised.exception)
                    self.assertEqual(f'{name} must be a single line', message)

        ui = dict(_UI)
        ui['email_notifications_smtp_password'] = 'pw\n'  # stripped instead
        data = self._save(**ui)
        self.assertEqual('pw', data['@email_notifications_smtp_password'])

    def test_short_form_is_shown(self):
        camera = dict(self.camera)
        camera.update({f'@{name}': value for name, value in _STORED.items()})
        wrapper = '/usr/local/sbin/motioneye-notify'
        forms = {
            'plain': (_short('sendmail'), _short('sendtelegram')),
            'wrapped': (
                f"{wrapper} mail {_short('sendmail')}",
                f"{wrapper} telegram {_short('sendtelegram')}",
            ),
            '-l -d': (
                f"{_find_command('sendmail')} -l -d %t '{_MOMENT}'",
                f"{_find_command('sendtelegram')} -l -d %t '{_MOMENT}'",
            ),
        }
        for label, (email, telegram) in forms.items():
            with self.subTest(label):
                line = f'{_RELAY} start %t; {email}; {telegram}'
                ui = config.motion_camera_dict_to_ui(dict(camera, on_event_start=line))
                expected = dict(_EMAIL, **_TELEGRAM)
                self.assertEqual(expected, {name: ui[name] for name in expected})
                self.assertFalse(ui['command_notifications_enabled'])

    def test_other_sender_parts_are_custom_commands(self):
        old = (
            f"{_find_command('sendmail')} 'smtp.example' '587' '007' 'FAKE-pw' "
            "'True' '' 'a@example' 'motion_start' '%t' '%Y-%m-%dT%H:%M:%S' '5'"
        )
        custom = "printf 'Subject: x' | sendmail -f me@example a@example"
        for command in (old, custom):
            with self.subTest(command=command):
                line = f'{_RELAY} start %t; {command}'
                camera = dict(self.camera, on_event_start=line)
                ui = config.motion_camera_dict_to_ui(camera)
                self.assertFalse(ui['email_notifications_enabled'])
                self.assertTrue(ui['command_notifications_enabled'])
                self.assertEqual(command, ui['command_notifications_exec'])


class SenderTest(_ConfigCase):
    # what motion runs: camera 1 with all settings stored, camera 2 without any
    def setUp(self):
        super().setUp()
        config.invalidate()  # nothing cached: a new process per event
        lines = [f'# @{name} {value}'.rstrip() for name, value in _STORED.items()]
        self._write_text(1, '\n'.join(['netcam_url rtsp://example/', *lines, '']))
        self._write_text(2, 'netcam_url rtsp://example/\n')

        self._patch('motioneye.settings.LIST_MEDIA_TIMEOUT', 120)
        self._patch('motioneye.meyectl.configure_logging')
        self._patch('motioneye.meyectl.configure_tornado')
        target = 'motioneye.motionctl.motion_camera_id_to_camera_id'
        self.camera_id = self._patch(target, return_value=1)
        self.make_mail = self._patch('motioneye.sendmail.make_message')
        self.send_mail = self._patch('motioneye.sendmail.send_mail')
        self.make_telegram = self._patch('motioneye.sendtelegram.make_message')
        self.send_telegram = self._patch('motioneye.sendtelegram.send_message')

    def _mail(self, *args):
        # what send_mail() gets when motion runs sendmail with these arguments
        self.make_mail.reset_mock()
        self.send_mail.reset_mock()
        sendmail.main(meyectl.make_arg_parser('sendmail'), list(args))
        if not self.make_mail.called:
            return None

        on_message = self.make_mail.call_args.args[-1]
        on_message('subject', 'message', [])
        return self.send_mail.call_args.args[:7]

    def _telegram(self, *args):
        # the token and chat id that sendtelegram sends with
        self.make_telegram.reset_mock()
        self.send_telegram.reset_mock()
        sendtelegram.main(meyectl.make_arg_parser('sendtelegram'), list(args))
        if not self.make_telegram.called:
            return None

        on_message = self.make_telegram.call_args.args[-1]
        on_message('message', [])
        return self.send_telegram.call_args.args[:2]

    def test_email_reads_the_camera_config(self):
        sent = self._mail('-c', _CONF, '1', _EVENT)

        sender = f'motionEye on {socket.gethostname()} <a@example>'
        to = ['a@example', 'b@example']
        expected = ('smtp.example', 587, '007', 'p;w%d FAKE-1234', True, sender, to)
        self.assertEqual(expected, sent)
        subject, _, camera_id, moment, timespan, _ = self.make_mail.call_args.args
        self.assertEqual(sendmail.subjects['motion_start'], subject)
        self.assertEqual((1, datetime(2026, 1, 1), 5), (camera_id, moment, timespan))

    def test_telegram_reads_the_camera_config(self):
        sent = self._telegram('-c', _CONF, '-l', '1', _EVENT)
        self.assertEqual(('123456:FAKE-token', '-1001234567'), sent)
        _, camera_id, moment, timespan, _ = self.make_telegram.call_args.args
        self.assertEqual((1, datetime(2026, 1, 1), 10), (camera_id, moment, timespan))

    def test_missing_settings_send_nothing(self):
        for camera_id in (None, 2):  # unknown motion camera, no settings
            self.camera_id.return_value = camera_id
            with self.subTest(camera_id=camera_id):
                with self.assertLogs(level='ERROR') as logs:
                    self.assertIsNone(self._mail('-c', _CONF, '1', _EVENT))

                error = 'ERROR:root:motion camera 1 has no email settings'
                self.assertEqual(error, logs.output[-1])

                with self.assertLogs(level='ERROR') as logs:
                    self.assertIsNone(self._telegram('-c', _CONF, '1', _EVENT))

                error = 'ERROR:root:motion camera 1 has no Telegram settings'
                self.assertEqual(error, logs.output[-1])

    def test_old_forms_are_refused(self):
        smtp = ['smtp.example', '587', '007', 'FAKE-pw', 'True']
        event = ['motion_start', '1', _EVENT, '5']
        calls = {
            'sendmail, 11': (sendmail, [*smtp, 'me@example', 'a@example', *event]),
            'sendmail, 10': (sendmail, [*smtp, 'a@example', *event]),
            'sendmail, -FAKE-pw': (sendmail, [*smtp[:3], '-FAKE-pw', 'True', *event]),
            'sendtelegram, 5': (sendtelegram, ['FAKE-token', '-42', '1', _EVENT, '5']),
            'sendtelegram, 3': (sendtelegram, ['1', _EVENT, 'FAKE-x']),
        }
        for label, (script, args) in calls.items():
            parser = meyectl.make_arg_parser(script.__name__.split('.')[-1])
            with self.subTest(label), patch('sys.stderr', io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    script.main(parser, ['-c', _CONF, *args])

                self.assertEqual(2, raised.exception.code)
                self.assertIn('unexpected arguments', stderr.getvalue())
                self.assertNotIn('FAKE-', stderr.getvalue())
                self.assertNotIn('-42', stderr.getvalue())  # nor the chat id

        parser = meyectl.make_arg_parser('sendtelegram')
        with patch('sys.stderr', io.StringIO()) as stderr:  # noqa: SIM117
            with self.assertRaises(SystemExit) as raised:
                sendtelegram.main(parser, ['-c', _CONF, '1', 'FAKE-moment'])

        self.assertEqual(2, raised.exception.code)
        self.assertIn('moment must be in ISO-8601 format', stderr.getvalue())
        self.assertNotIn('FAKE-', stderr.getvalue())
        self.make_mail.assert_not_called()
        self.make_telegram.assert_not_called()

    def test_telegram_debug_log_has_no_token(self):
        with self.assertLogs(level='DEBUG') as logs:
            sent = self._telegram('-c', _CONF, '1', _EVENT)

        self.assertEqual('123456:FAKE-token', sent[0])
        self.assertNotIn('FAKE-token', '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
