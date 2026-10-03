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
import json
import os
import re
import shlex
import socket
import unittest
from datetime import datetime
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock, patch
from urllib.error import URLError

from motioneye import config, meyectl, sendmail, sendtelegram, server, webhook

_CONF = '/data/motioneye/motioneye.conf'
_OPTIONS = f'-c {_CONF}'  # the server options that meyectl.find_command() adds
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
_END_URL = 'https://discord.example/api/webhooks/42/TOKEN?at=%H:%M'
_CUSTOM = "mosquitto_pub -t cam/%t -m start; echo 'a b'"

# notification fields of a camera, as GET returns them
_UI = {
    'email_notifications_enabled': True,
    'email_notifications_smtp_server': 'smtp.example',
    'email_notifications_smtp_port': '587',
    'email_notifications_smtp_account': '007',
    'email_notifications_smtp_password': 'p;w%d 1234',
    'email_notifications_smtp_tls': True,
    'email_notifications_from': '',
    'email_notifications_addresses': 'a@example,b@example',
    'email_notifications_picture_time_span': 5,
    'telegram_notifications_enabled': True,
    'telegram_notifications_api': '123456:SECRET-token',
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

# what a save of _UI stores in camera-N.conf, as "# @<name> <text>" lines
_STORED = {
    'email_notifications_smtp_server': 'smtp.example',
    'email_notifications_smtp_port': '587',
    'email_notifications_smtp_account': '007',
    'email_notifications_smtp_password': 'p;w%d 1234',
    'email_notifications_smtp_tls': 'True',
    'email_notifications_from': '',
    'email_notifications_addresses': 'a@example,b@example',
    'email_notifications_picture_time_span': '5',
    'telegram_notifications_api': '123456:SECRET-token',
    'telegram_notifications_chat_id': '-1001234567',
    'telegram_notifications_picture_time_span': '10',
    'web_hook_notifications_http_method': 'POSTj',
    'web_hook_notifications_url': _MOTION_URL,
    'web_hook_end_notifications_http_method': 'GET',
    'web_hook_end_notifications_url': _END_URL,
    'web_hook_storage_http_method': 'POSTj',
    'web_hook_storage_url': _STORAGE_URL,
}
_STORED_LINES = ('# @email_notifications', '# @telegram_notifications', '# @web_hook')

# settings that must not be on motion's lines (ps, motion's log)
_HIDDEN = (
    'smtp.example',
    '587',
    '007',
    'p;w%d',
    'a@example',
    'SECRET-token',
    '-1001234567',
    'POSTj',
    'GET',
    _HA,
    'discord.example',
)

# the arguments origin/dev wrote to motion's lines for _UI
_OLD_SENDMAIL = (
    "'smtp.example' '587' '007' 'p\\;w%%d 1234' 'True' '' 'a@example,b@example' "
    "'motion_start' '%t' '%Y-%m-%dT%H:%M:%S' '5'"
)
_OLD_SENDTELEGRAM = "'123456:SECRET-token' '-1001234567' '%t' '%Y-%m-%dT%H:%M:%S' '10'"
_OLDER_SENDMAIL = _OLD_SENDMAIL.replace("'True' '' ", "'True' ")  # 0.28 to 0.30

# how motionEye versions and setups wrote the commands: python, script, options
# and, for 0.28 to 0.30, sendmail's arguments without from
_PY2 = '/usr/lib/python2.7/dist-packages/motioneye/meyectl.pyc'
_PREFIXES = {
    '-c conf': (_PYTHON, _MEYECTL, f'-c {_CONF}'),
    '-c conf -l -d': (_PYTHON, _MEYECTL, f'-c {_CONF} -l -d'),
    '-dl': (_PYTHON, _MEYECTL, f'-c {_CONF} -dl'),
    'no -c': (_PYTHON, _MEYECTL, ''),
    'py2 meyectl.pyc': ('/usr/bin/python', _PY2, f'-c {_CONF}'),
    '0.28 console script': ('', '/usr/local/bin/meyectl', f'-c {_CONF}'),
    'stale interpreter': ('/usr/bin/python3.11', _MEYECTL, f'-c {_CONF}'),
    '10 values, no from': (_PYTHON, _MEYECTL, f'-c {_CONF}', _OLDER_SENDMAIL),
}
_MISREAD = ('no -c', '0.28 console script')  # origin/dev shows their email shifted


def _find_command(command):
    # meyectl.find_command() of a server started with "-c _CONF"
    if command == 'relayevent':
        return _RELAY

    return f'{_PYTHON} {_MEYECTL} {command} -c {_CONF}'


def _find_with(options):
    # the same server, started with more options
    def find_command(command):
        if command == 'relayevent':
            return _RELAY

        return f'{_find_command(command)} {options}'

    return find_command


def _old_lines(python=_PYTHON, script=_MEYECTL, options=_OPTIONS, mail=_OLD_SENDMAIL):
    # motion's lines as origin/dev wrote them for _UI, behind the given prefix
    def command(name):
        return ' '.join(part for part in (python, script, name, options) if part)

    email = f"{command('sendmail')} {mail}"
    telegram = f"{command('sendtelegram')} {_OLD_SENDTELEGRAM}"
    hook = f"{command('webhook')} 'POSTj' '{_MOTION_URL}'"
    end_hook = f"{command('webhook')} 'GET' '{_END_URL}'"
    storage_hook = f"{command('webhook')} 'POSTj' '{_STORAGE_URL}'"
    start = [f'{_RELAY} start %t', email, telegram, hook, _CUSTOM]
    return {
        'on_event_start': '; '.join(start),
        'on_event_end': f'{_RELAY} stop %t; {end_hook}',
        'on_movie_end': f'{_RELAY} movie_end %t %f; {storage_hook}',
        'on_picture_save': f'{_RELAY} picture_save %t %f; {storage_hook}',
    }


def _new_lines():
    # motion's lines for _UI: commands, specifiers and the URLs from their first %
    email = f"{_find_command('sendmail')} %t '{_MOMENT}'"
    telegram = f"{_find_command('sendtelegram')} %t '{_MOMENT}'"
    hook = _find_command('webhook')
    motion_tail = _MOTION_URL[len(f'{_HA}?camera_id=') :]
    storage_tail = _STORAGE_URL[len(f'{_HA}?camera_id=') :]
    notifications = f"{hook} %t notifications -- '{motion_tail}'"
    storage = f"{hook} %t storage -- '{storage_tail}'"
    start = [f'{_RELAY} start %t', email, telegram, notifications, _CUSTOM]
    return {
        'on_event_start': '; '.join(start),
        'on_event_end': f"{_RELAY} stop %t; {hook} %t end_notifications -- '%H:%M'",
        'on_movie_end': f'{_RELAY} movie_end %t %f; {storage}',
        'on_picture_save': f'{_RELAY} picture_save %t %f; {storage}',
    }


def _ha_sets_webhook(camera, kind, url):
    # Home Assistant's _set_webhook() decision for a webhook it set before
    enabled = camera.get(f'web_hook_{kind}_enabled', False)
    method = camera.get(f'web_hook_{kind}_http_method')
    current = camera.get(f'web_hook_{kind}_url')
    return not enabled or method != 'POSTj' or current != url


def _expand(text):
    # motion's expansion of its conversion specifiers: %t -> t9, %{fps} -> fps9
    return re.sub(r'%\{?(\w+)\}?', r'\g<1>9', text)


class _Case(unittest.TestCase):
    conf_dir: str

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

    def _read(self, camera_id):
        with open(self._path(camera_id)) as f:
            return f.read()


class _ConfigCase(_Case):
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
        self._patch('motioneye.utils.get_disk_usage', return_value=None)  # changes
        self._patch('motioneye.controls.diskctl.list_mounted_disks', return_value=[])

        self.camera = {'@id': 1, '@enabled': True, 'netcam_url': 'rtsp://example/'}
        self.camera.update(width=640, height=480)
        config._set_default_motion_camera(1, self.camera)
        self.camera['target_dir'] = self.conf_dir

    def _write(self, camera_id, data):
        # camera-N.conf as set_camera() writes it
        lines = config._dict_to_conf([], dict(data, **{'@id': camera_id}))
        self._write_text(camera_id, '\n'.join(lines) + '\n')

    def _save(self, **notifications):
        # motion_camera_ui_to_dict() of camera 1 with these notification fields
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(notifications)
        return config.motion_camera_ui_to_dict(ui, self.camera)

    def _old_camera(self, saved, *prefix):
        # the same camera as origin/dev saved it
        stored = {f'@{name}' for name in _STORED}
        camera = {key: value for key, value in saved.items() if key not in stored}
        camera.update(_old_lines(*prefix))
        return camera

    def _get(self, camera_id=1):
        # GET /config/N/get/, read from the file
        config._camera_config_cache.pop(camera_id, None)
        return config.motion_camera_dict_to_ui(config.get_camera(camera_id))

    def _post(self, ui, camera_id=1):
        # POST /config/N/set/, see handlers/config.py
        data = config.motion_camera_ui_to_dict(ui, config.get_camera(camera_id))
        config.set_camera(camera_id, data)


class ConfigTest(_ConfigCase):
    def test_lines_hold_only_commands_and_specifiers(self):
        expected = _new_lines()
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(_UI)
        for prev_config in (self.camera, None):  # None as in handlers/picture.py
            with self.subTest(prev_config=bool(prev_config)):
                data = config.motion_camera_ui_to_dict(dict(ui), prev_config)
                lines = {option: data[option] for option in expected}

                self.assertEqual(expected, lines)
                for line in lines.values():
                    self.assertNotIn('None', line)
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
        self._post(dict(self._get(), **hooks))
        text = self._read(1)

        got = self._get()
        self.assertEqual(hooks, {name: got[name] for name in hooks})
        self.assertFalse(_ha_sets_webhook(got, 'notifications', _MOTION_URL))
        self.assertFalse(_ha_sets_webhook(got, 'storage', _STORAGE_URL))

        self._post(got)
        self.assertEqual(text, self._read(1))
        self.assertEqual(got, self._get())

    def test_url_without_specifiers_keeps_an_empty_tail(self):
        # always 3 values, so webhook.py cannot take it for METHOD URL
        url = 'https://x.example/upload'
        storage = {
            'web_hook_storage_enabled': True,
            'web_hook_storage_http_method': 'POST',
            'web_hook_storage_url': url,
        }
        data = self._save(**storage)

        hook = f"{_find_command('webhook')} %t storage -- ''"
        movie_end = f'{_RELAY} movie_end %t %f; {hook}'
        picture_save = f'{_RELAY} picture_save %t %f; {hook}'
        lines = (data['on_movie_end'], data['on_picture_save'])
        self.assertEqual((movie_end, picture_save), lines)
        self.assertEqual(url, data['@web_hook_storage_url'])
        ui = config.motion_camera_dict_to_ui(data)
        self.assertEqual(storage, {name: ui[name] for name in storage})

        old = f"{_RELAY} movie_end %t %f; {_find_command('webhook')} 'POST' '{url}'"
        camera = {'@id': 1, 'on_movie_end': old}
        self.assertTrue(config._move_notification_settings(camera))
        self.assertEqual(movie_end, camera['on_movie_end'])

    def test_apostrophe_in_a_url_is_quoted(self):
        # the storage URL is not checked for quotes, sh must still get one value
        url = "https://x.example/up?f=%f&note=it's"
        storage = {
            'web_hook_storage_enabled': True,
            'web_hook_storage_http_method': 'POST',
            'web_hook_storage_url': url,
        }
        data = self._save(**storage)

        hook = f"{_find_command('webhook')} %t storage -- '%f&note=it'\\''s'"
        self.assertEqual(f'{_RELAY} movie_end %t %f; {hook}', data['on_movie_end'])
        self.assertEqual("%f&note=it's", shlex.split(data['on_movie_end'])[-1])
        ui = config.motion_camera_dict_to_ui(data)
        self.assertEqual(url, ui['web_hook_storage_url'])

        escaped = url.replace("'", "'\\''")  # quoted by hand on an older line
        old = f"{_RELAY} movie_end %t %f; {_find_command('webhook')} 'POST' '{escaped}'"
        camera = {'@id': 1, 'on_movie_end': old}
        self.assertTrue(config._move_notification_settings(camera))
        self.assertEqual(data['on_movie_end'], camera['on_movie_end'])
        self.assertEqual(url, camera['@web_hook_storage_url'])

    def test_disabled_notifications_keep_no_settings(self):
        self._write(1, self.camera)
        self._post(dict(self._get(), **_UI))
        lines = self._read(1).splitlines()
        stored = [line for line in lines if line.startswith(_STORED_LINES)]
        self.assertEqual(17, len(stored))

        kinds = ('email', 'telegram', 'web_hook', 'web_hook_end')
        off = {f'{kind}_notifications_enabled': False for kind in kinds}
        off['web_hook_storage_enabled'] = False
        self._post(dict(self._get(), **off))
        text = self._read(1)
        lines = text.splitlines()
        self.assertEqual([], [line for line in lines if line.startswith(_STORED_LINES)])

        got = self._get()  # no detail fields while disabled
        self.assertNotIn('email_notifications_smtp_password', got)
        self.assertNotIn('telegram_notifications_api', got)
        self.assertNotIn('web_hook_storage_url', got)
        self._post(got)
        self.assertEqual(text, self._read(1))

    def test_line_breaks_are_refused(self):
        fields = (
            'email_notifications_smtp_password',
            'telegram_notifications_api',
            'web_hook_storage_http_method',
        )
        for name in fields:
            for value in ('a\nsecret', 'a\rsecret'):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError) as raised:
                        self._save(**dict(_UI, **{name: value}))

                    message = str(raised.exception)
                    self.assertEqual(f'{name} must be a single line', message)

        ui = dict(_UI)
        ui['email_notifications_smtp_password'] = 'pw\n'  # stripped instead
        data = self._save(**ui)
        self.assertEqual('pw', data['@email_notifications_smtp_password'])

    def test_older_lines_are_still_read(self):
        camera = dict(self.camera, **_old_lines())
        camera.update({f'@{name}': 'stale' for name in _STORED})  # not consulted
        ui = config.motion_camera_dict_to_ui(camera)
        self.assertEqual(_UI, {name: ui[name] for name in _UI})

        script = _find_command('sendmail')
        with_from = _OLD_SENDMAIL.replace("'True' ''", "'True' 'me@example'")
        for arguments, sender in ((with_from, 'me@example'), (_OLDER_SENDMAIL, '')):
            with self.subTest(sender=sender):
                camera['on_event_start'] = f'{_RELAY} start %t; {script} {arguments}'
                ui = config.motion_camera_dict_to_ui(camera)
                expected = dict(_EMAIL, email_notifications_from=sender)
                self.assertEqual(expected, {name: ui[name] for name in expected})

    def test_wrapped_short_form_is_shown(self):
        short = f"{_find_command('sendmail')} %t '{_MOMENT}'"
        wrapped = f'/usr/local/sbin/motioneye-notify mail {short}'
        camera = dict(self.camera, on_event_start=f'{_RELAY} start %t; {wrapped}')
        camera.update({f'@{name}': value for name, value in _STORED.items()})
        ui = config.motion_camera_dict_to_ui(camera)

        self.assertEqual(_EMAIL, {name: ui[name] for name in _EMAIL})
        self.assertFalse(ui['telegram_notifications_enabled'])


class ConversionTest(_ConfigCase):
    def test_older_lines_are_moved(self):
        fresh = self._save(**_UI)
        saved = dict(fresh)
        self.assertFalse(config._move_notification_settings(saved))  # G5
        self.assertEqual(fresh, saved)

        for label, prefix in _PREFIXES.items():
            with self.subTest(label):
                camera = self._old_camera(fresh, *prefix)
                self.assertTrue(config._move_notification_settings(camera))
                self.assertEqual(fresh, camera)  # the same as a save in the UI

                self.assertFalse(config._move_notification_settings(camera))  # G6
                with patch('motioneye.meyectl.find_command', _find_with('-d')):
                    self.assertFalse(config._move_notification_settings(camera))

    def test_get_is_unchanged_by_the_conversion(self):  # G4
        fresh = self._save(**_UI)
        expected = config.motion_camera_dict_to_ui(fresh)
        for label, prefix in _PREFIXES.items():
            with self.subTest(label):
                camera = self._old_camera(fresh, *prefix)
                before = config.motion_camera_dict_to_ui(camera)
                config._move_notification_settings(camera)
                after = config.motion_camera_dict_to_ui(camera)

                self.assertEqual(expected, after)
                if label in _MISREAD:  # fixed: origin/dev shows the port as server
                    server = before['email_notifications_smtp_server']
                    self.assertEqual('587', server)

                else:
                    self.assertEqual(before, after)

    def test_other_commands_are_left_alone(self):
        email = f"{_find_command('sendmail')} {_OLD_SENDMAIL}"
        telegram = f"{_find_command('sendtelegram')} {_OLD_SENDTELEGRAM}"
        hook = _find_command('webhook')
        old_sendmail = '/usr/share/motioneye/sendmail.py "smtp.example" "25" "me"'
        password = "'p\\;w%%d 1234'"
        both = ('on_event_start', 'on_event_end')
        ends = ('on_event_end', 'on_movie_end', 'on_picture_save')
        others = {
            'wrapper': (both, f'/usr/local/sbin/motioneye-notify mail {email}'),
            'environment': (both, f"PYTHONPATH='/opt/my libs' {email}"),
            'camera id': (both, email.replace("'%t'", "'1'")),
            'other message': (both, email.replace('motion_start', 'motion_end')),
            'other moment': (both, email.replace(_MOMENT, '%s')),
            'other webhook': (both, "mytool webhook 'GET' 'https://x.example/'"),
            'other method': (both, f"{hook} 'PUT' 'https://x.example/'"),
            'empty URL': (both, f"{hook} 'GET' ''"),
            'quoted semicolon': (both, "echo 'c;d'"),
            'unbalanced quotes': (both, f"{email} 'x"),
            'escaped semicolon': (both, "echo 'a\\;b'"),
            'relayevent': (both, f'{_RELAY} start %t'),
            'eventrelay.py': (both, '/usr/share/motioneye/eventrelay.py start %t'),
            'sendmail.py of 0.20': (both, f'{old_sendmail} "pw" "False" "a@example"'),
            '4 values': (both, f"{hook} -- 'POSTj' '' '1' 'notifications'"),
            'sendmail not at event start': (ends, email),
            'sendtelegram not at event start': (ends, telegram),
            'password -correct': (both, email.replace(password, "'-correct'")),
            'password -dl': (both, email.replace(password, "'-dl'")),
            'password -v': (both, email.replace(password, "'-v'")),
            'shell expansion': (both, email.replace("'007'", '$(cat /x)')),
            'double quotes': (both, email.replace("'007'", '"007"')),
        }
        for label, (options, command) in others.items():
            for option in options:
                line = f'{_RELAY} start %t; {command}; echo end'
                camera = {'@id': 1, option: line}
                with self.subTest(label, option=option):
                    with patch('sys.stderr', io.StringIO()):  # argparse usage
                        moved = config._move_notification_settings(camera)

                    self.assertFalse(moved)
                    self.assertEqual({'@id': 1, option: line}, camera)

        line = f"{_RELAY} start %t;  {telegram}  ;echo 'a\\;b'; echo 'c;d'"
        camera = {'@id': 1, 'on_event_start': line}
        self.assertTrue(config._move_notification_settings(camera))
        short = f"{_find_command('sendtelegram')} %t '{_MOMENT}'"
        expected = f"{_RELAY} start %t;  {short}  ;echo 'a\\;b'; echo 'c;d'"
        self.assertEqual(expected, camera['on_event_start'])

    def _assert_refused(self, camera, name):
        # a WARNING without values, at every start; the second start changes nothing
        warning = f'WARNING:root:could not move {name} settings of camera 1'
        with self.assertLogs(level='WARNING') as logs:
            moved = config._move_notification_settings(camera)

        self.assertEqual([warning], logs.output)
        first = dict(camera)
        with self.assertLogs(level='WARNING') as logs:
            self.assertFalse(config._move_notification_settings(camera))

        self.assertEqual([warning], logs.output)
        self.assertEqual(first, camera)
        return moved

    def test_clashing_or_padded_settings_stay_on_the_line(self):
        telegram = f"{_find_command('sendtelegram')} {_OLD_SENDTELEGRAM}"
        other = telegram.replace('SECRET-token', 'OTHER-token')
        short = f"{_find_command('sendtelegram')} %t '{_MOMENT}'"
        hook = _find_command('webhook')
        token = '@telegram_notifications_api'

        with self.subTest('two bots'):
            line = f'{_RELAY} start %t; {telegram}; {other}'
            camera = {'@id': 1, 'on_event_start': line}
            self.assertTrue(self._assert_refused(camera, 'sendtelegram'))
            expected = f'{_RELAY} start %t; {short}; {other}'
            self.assertEqual(expected, camera['on_event_start'])
            self.assertEqual('123456:SECRET-token', camera[token])

        with self.subTest('a bot in use'):
            line = f'{_RELAY} start %t; {short}; {other}'
            camera = {'@id': 1, 'on_event_start': line, token: '123456:SECRET-token'}
            camera['@telegram_notifications_chat_id'] = '-1001234567'
            camera['@telegram_notifications_picture_time_span'] = '10'
            unchanged = dict(camera)
            self.assertFalse(self._assert_refused(camera, 'sendtelegram'))
            self.assertEqual(unchanged, camera)

        with self.subTest('two storage URLs'):
            movie_end = f"{_RELAY} movie_end %t %f; {hook} 'POSTj' '{_STORAGE_URL}'"
            other_url = "'POSTj' 'https://other.example/x?f=%f'"
            picture_save = f'{_RELAY} picture_save %t %f; {hook} {other_url}'
            camera = {'@id': 1, 'on_movie_end': movie_end}
            camera['on_picture_save'] = picture_save
            self.assertTrue(self._assert_refused(camera, 'storage'))
            self.assertEqual(_new_lines()['on_movie_end'], camera['on_movie_end'])
            self.assertEqual(picture_save, camera['on_picture_save'])
            self.assertEqual(_STORAGE_URL, camera['@web_hook_storage_url'])

        with self.subTest('padded password'):
            padded = _OLD_SENDMAIL.replace('p\\;w%%d 1234', ' pw ')
            line = f"{_RELAY} start %t; {_find_command('sendmail')} {padded}"
            camera = {'@id': 1, 'on_event_start': line}
            self.assertFalse(self._assert_refused(camera, 'sendmail'))
            self.assertEqual({'@id': 1, 'on_event_start': line}, camera)

    def test_startup_isolates_cameras(self):
        fresh = self._save(**_UI)
        old = self._old_camera(fresh)
        self._write(1, fresh)  # already moved
        self._write(2, old)
        self._write(3, old)  # its write fails
        self._write_text(4, 'framerate 2\n')  # incomplete, get_camera() returns None
        remote = '# @proto motioneye\n# @host 192.168.1.2\n# @remote_camera_id 1\n'
        telegram = f"{_find_command('sendtelegram')} {_OLD_SENDTELEGRAM}"
        self._write_text(5, f'{remote}on_event_start {telegram}\n')
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
            config.move_notification_settings()

        self.assertEqual([2, 3], [c.args[0] for c in writes.call_args_list])
        moving = 'INFO:root:moving notification settings of camera'
        self.assertIn(f'{moving} 2', logs.output)
        self.assertIn(f'{moving} 3', logs.output)
        errors = [line for line in logs.output if line.startswith('ERROR:')]
        failed = 'ERROR:root:failed to move settings of camera'
        self.assertEqual(f'{failed} 3: read-only file system', errors[0])
        self.assertTrue(errors[1].startswith(f'{failed} 4: '))
        self.assertEqual(2, len(errors))
        for camera_id in (1, 3, 4, 5):
            self.assertEqual(files[camera_id], self._read(camera_id))

        shown = config._camera_config_cache[3]  # the copy from before, as on disk
        for option, line in _old_lines().items():
            self.assertEqual(line, shown[option])

        config.invalidate()
        moved = config.get_camera(2)
        for option in _old_lines():
            self.assertEqual(fresh[option], moved[option])

        for name, value in _STORED.items():
            self.assertEqual(value, moved[f'@{name}'])

        config.invalidate()
        writes.reset_mock()
        files[2] = self._read(2)
        with self.assertLogs(level='INFO') as logs:
            config.move_notification_settings()

        self.assertEqual([3], [c.args[0] for c in writes.call_args_list])  # retried
        self.assertNotIn(f'{moving} 2', logs.output)
        self.assertEqual(files[2], self._read(2))

    def test_startup_needs_free_space(self):
        self._write(1, self._old_camera(self._save(**_UI)))
        text = self._read(1)
        usage = self._patch('motioneye.config.disk_usage', return_value=Mock(free=1000))
        writes = self._patch('motioneye.config.set_camera')
        with self.assertLogs(level='ERROR') as logs:
            config.move_notification_settings()

        writes.assert_not_called()
        usage.assert_called_once_with(self.conf_dir)
        error = 'ERROR:root:failed to move settings of camera 1: less than 1 MiB free'
        self.assertEqual([error], logs.output)
        self.assertEqual(text, self._read(1))
        kept = config._camera_config_cache[1]['on_event_start']
        self.assertEqual(_old_lines()['on_event_start'], kept)

    def test_failed_write_keeps_the_complete_copy(self):
        self._write(1, self._old_camera(self._save(**_UI)))

        def truncate_then_fail(camera_id, camera_config):
            self._write_text(camera_id, '')  # set_camera() truncates before writing
            raise OSError('No space left on device')

        self._patch('motioneye.config.set_camera', side_effect=truncate_then_fail)
        with self.assertLogs(level='ERROR'):
            config.move_notification_settings()

        kept = config.get_camera(1)
        for option, line in _old_lines().items():
            self.assertEqual(line, kept[option])

    def test_server_startup_converts(self):
        # make_media_folders() runs before motion is started
        self._write(1, self._old_camera(self._save(**_UI)))
        self._patch('motioneye.config.get_camera_ids', return_value=[1])
        with self.assertLogs(level='INFO') as logs:
            server.make_media_folders()

        moving = 'INFO:root:moving notification settings of camera 1'
        self.assertIn(moving, logs.output)
        text = self._read(1)
        self.assertIn('\n# @telegram_notifications_api 123456:SECRET-token\n', text)
        self.assertNotIn('SECRET-token', config.get_camera(1)['on_event_start'])

    def test_restore_converts_older_backups(self):
        fresh = self._save(**_UI)
        self._write(1, self._old_camera(fresh))
        backup = config.backup()
        self._write(1, self.camera)  # what is there before restoring

        self._patch('motioneye.settings.ENABLE_REBOOT', False)
        with self.assertLogs(level='INFO') as logs:
            self.assertEqual({'reboot': False}, config.restore(backup))

        moving = 'INFO:root:moving notification settings of camera 1'
        self.assertIn(moving, logs.output)
        text = self._read(1)
        self.assertIn('\n# @email_notifications_smtp_password p;w%d 1234\n', text)
        config.invalidate()
        restored = config.get_camera(1)
        for option in _old_lines():
            self.assertEqual(fresh[option], restored[option])


class _ScriptCase(_Case):
    # what motion runs: camera 1 with all settings stored, camera 2 without any
    def setUp(self):
        self.conf_dir = mkdtemp()
        self.addCleanup(rmtree, self.conf_dir)
        config.invalidate()  # nothing cached: a new process per event
        self.addCleanup(config.invalidate)
        lines = [f'# @{name} {value}'.rstrip() for name, value in _STORED.items()]
        self._write_text(1, '\n'.join(['netcam_url rtsp://example/', *lines, '']))
        self._write_text(2, 'netcam_url rtsp://example/\n')

        self._patch('motioneye.settings.CONF_PATH', self.conf_dir)
        self._patch('motioneye.settings.LIST_MEDIA_TIMEOUT', 120)
        self._patch('motioneye.meyectl.configure_logging')
        self._patch('motioneye.meyectl.configure_tornado')
        target = 'motioneye.motionctl.motion_camera_id_to_camera_id'
        self.camera_id = self._patch(target, return_value=1)


class SenderTest(_ScriptCase):
    def setUp(self):
        super().setUp()
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

    def test_email_short_form_reads_the_camera_config(self):
        sent = self._mail('-c', _CONF, '1', _EVENT)

        sender = f'motionEye on {socket.gethostname()} <a@example>'
        to = ['a@example', 'b@example']
        expected = ('smtp.example', 587, '007', 'p;w%d 1234', True, sender, to)
        self.assertEqual(expected, sent)
        subject, _, camera_id, moment, timespan, _ = self.make_mail.call_args.args
        self.assertEqual(sendmail.subjects['motion_start'], subject)
        self.assertEqual((1, datetime(2026, 1, 1), 5), (camera_id, moment, timespan))

    def test_email_older_forms(self):
        smtp = ['srv', '25', 'me', 'pw', 'False']
        event = ['motion_start', '1', _EVENT, '5']
        eleven = [*smtp, 'f@x', 't@x', *event]
        ten = [*smtp, 't@x', *event]
        dash = ['srv', '25', 'me', '-pw', 'False', 'f@x', 't@x', *event]
        escaped = ['srv', '25', 'me', 'p\\;w', 'False', 'f@x', 't@x', *event]
        empty = ['srv', '25', 'me', '', 'False', 'f@x', 't@x', *event]
        sent = ('srv', 25, 'me', 'pw', False, 'f@x', ['t@x'])
        default = sent[:5] + (f'motionEye on {socket.gethostname()} <t@x>', ['t@x'])
        dashed = sent[:3] + ('-pw',) + sent[4:]
        unescaped = sent[:3] + ('p;w',) + sent[4:]
        no_password = sent[:3] + ('',) + sent[4:]  # not the stored one
        forms = {
            '11 values, -c -l -d': (['-c', _CONF, '-l', '-d', *eleven], sent),
            '-dl': (['-c', _CONF, '-dl', *eleven], sent),
            '10 values, no -c': (ten, default),
            'options between': ([*eleven[:2], '-d', *eleven[2:], '-c', _CONF], sent),
            '-- first, -pw': (['-c', _CONF, '--', *dash], dashed),
            'escaped': (escaped, unescaped),
            'empty password': (['-c', _CONF, *empty], no_password),
        }
        for label, (args, expected) in forms.items():
            with self.subTest(label), patch('motioneye.config.get_camera') as get:
                self.assertEqual(expected, self._mail(*args))
                get.assert_not_called()

    def test_telegram_short_and_old_forms(self):
        sent = self._telegram('-c', _CONF, '1', _EVENT)
        self.assertEqual(('123456:SECRET-token', '-1001234567'), sent)
        _, camera_id, moment, timespan, _ = self.make_telegram.call_args.args
        self.assertEqual((1, datetime(2026, 1, 1), 10), (camera_id, moment, timespan))

        with patch('motioneye.config.get_camera') as get_camera:
            sent = self._telegram('TOKEN', '-42', '1', _EVENT, '5')  # as in #3423
            timespan = self.make_telegram.call_args.args[3]
            empty = self._telegram('', '-42', '1', _EVENT, '5')  # not the stored one

        self.assertEqual(('TOKEN', '-42'), sent)
        self.assertEqual(5, timespan)
        self.assertEqual(('', '-42'), empty)
        get_camera.assert_not_called()

    def test_missing_settings_send_nothing(self):
        for camera_id in (None, 2, 3):  # unknown motion camera, no settings, no file
            self.camera_id.return_value = camera_id
            with self.subTest(camera_id=camera_id):
                with self.assertLogs(level='ERROR') as logs:
                    self.assertIsNone(self._mail('-c', _CONF, '1', _EVENT))

                error = f'ERROR:root:camera {camera_id} has no email settings'
                self.assertEqual(error, logs.output[-1])

                with self.assertLogs(level='ERROR') as logs:
                    self.assertIsNone(self._telegram('-c', _CONF, '1', _EVENT))

                error = f'ERROR:root:camera {camera_id} has no Telegram settings'
                self.assertEqual(error, logs.output[-1])

    def test_wrong_number_of_arguments(self):
        twelve = ['srv', '25', 'me', 'pw', 'False', 'f', 't', 'motion_start', '1']
        calls = {
            'sendmail, 3': (sendmail, ['-c', _CONF, '1', _EVENT, '5']),
            'sendmail, 12': (sendmail, ['-c', _CONF, *twelve, _EVENT, '5', 'x']),
            'sendtelegram, 3': (sendtelegram, ['1', _EVENT, '5']),
            'webhook, 1': (webhook, ['-c', _CONF, 'GET']),
            'webhook, 4': (webhook, ['--', 'POSTj', '', '1', 'notifications']),
        }
        for label, (script, args) in calls.items():
            parser = meyectl.make_arg_parser(script.__name__.split('.')[-1])
            with self.subTest(label), patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    script.main(parser, args)

                self.assertEqual(2, raised.exception.code)

        self.make_mail.assert_not_called()
        self.make_telegram.assert_not_called()

    def test_errors_do_not_echo_values(self):
        smtp = ['srv', '25', 'me', '-SECRET', 'False', 'f@x', 't@x']
        args = ['-c', _CONF, *smtp, 'motion_start', '1', _EVENT, '5']
        parser = meyectl.make_arg_parser('sendmail')
        with patch('sys.stderr', io.StringIO()) as stderr:
            with self.assertRaises(SystemExit):
                sendmail.main(parser, args)

        error = 'error: unrecognized arguments: [0-9]+\n'  # how many differs by Python
        self.assertRegex(stderr.getvalue(), error)
        self.assertNotIn('SECRET', stderr.getvalue())

    def test_telegram_debug_log_has_no_token(self):
        with self.assertLogs(level='DEBUG') as logs:
            sent = self._telegram('-c', _CONF, '1', _EVENT)

        self.assertEqual('123456:SECRET-token', sent[0])
        self.assertNotIn('SECRET-token', '\n'.join(logs.output))
        self.assertIn('api=None', '\n'.join(logs.output))

        parser = meyectl.make_arg_parser('sendtelegram')
        options = sendtelegram.parse_options(parser, ['-c', _CONF, '1', _EVENT])
        self.assertNotIn('args', vars(options))


class WebHookTest(_ScriptCase):
    def setUp(self):
        super().setUp()
        self.urlopen = self._patch('motioneye.utils.urlopen')

    def _call(self, *args):
        # the request that motion's webhook command makes
        self.urlopen.reset_mock()
        webhook.main(meyectl.make_arg_parser('webhook'), list(args))
        if not self.urlopen.called:
            return None

        return self.urlopen.call_args.args[0]

    def test_stored_method_and_url_are_used(self):
        args = ['-c', _CONF, '1', 'end_notifications', '--', '12:34']
        with self.assertLogs(level='DEBUG') as logs:
            request = self._call(*args)

        url = 'https://discord.example/api/webhooks/42/TOKEN?at=12:34'
        self.assertEqual(url, request.full_url)
        self.assertEqual('GET', request.get_method())
        output = '\n'.join(logs.output)
        self.assertIn('url = https://discord.example\n', output)
        self.assertNotIn('/api/webhooks/42/TOKEN', output)

    def test_tail_after_double_dash(self):
        head = 'https://discord.example/api/webhooks/42/TOKEN?at='
        for tail in ('-0500', '--', '-c', ''):
            with self.subTest(tail=tail):
                args = ['-l', '-c', _CONF, '1', 'end_notifications', '--', tail]
                self.assertEqual(head + tail, self._call(*args).full_url)

    def test_method_url_reads_no_config(self):
        get_camera = self._patch('motioneye.config.get_camera')
        request = self._call('POSTf', 'https://x.example/p?a=1')
        self.assertEqual('https://x.example/p', request.full_url)
        self.assertEqual(b'a=1', request.data)

        request = self._call('POSTj', '-c', _CONF, 'https://x.example/p?a=1')
        self.assertEqual('https://x.example/p', request.full_url)
        self.assertEqual(b'{"a": "1"}', request.data)
        get_camera.assert_not_called()
        self.camera_id.assert_not_called()

    def test_missing_stored_webhook(self):
        for camera_id in (None, 2, 3):  # unknown motion camera, no settings, no file
            self.camera_id.return_value = camera_id
            with self.subTest(camera_id=camera_id):
                args = ['-c', _CONF, '1', 'notifications', '--', '%t']
                with self.assertLogs(level='ERROR') as logs:
                    self.assertIsNone(self._call(*args))

                error = f'ERROR:root:camera {camera_id} has no notifications webhook'
                self.assertEqual(error, logs.output[-1])

    def test_invalid_url_is_not_logged(self):
        url = 'ha.example/hook-secret?camera_id='  # no scheme: Request() refuses it
        lines = ['# @web_hook_notifications_http_method GET']
        lines.append(f'# @web_hook_notifications_url {url}%t')
        self._write_text(4, '\n'.join(lines) + '\n')
        self.camera_id.return_value = 4
        forms = {
            'stored': ['-c', _CONF, '1', 'notifications', '--', '%t'],
            'on the line': ['GET', f'{url}1'],
        }
        for label, args in forms.items():
            with self.subTest(label):
                with self.assertLogs(level='DEBUG') as logs:
                    self.assertIsNone(self._call(*args))

                self.assertIn('DEBUG:root:method = GET', logs.output)
                error = 'ERROR:root:failed to call webhook: ValueError'
                self.assertIn(error, logs.output)
                self.assertNotIn('hook-secret', '\n'.join(logs.output))

        self.urlopen.side_effect = URLError('timed out')  # its message has no URL
        with self.assertLogs(level='ERROR') as logs:
            self._call('GET', 'https://x.example/')

        error = 'ERROR:root:failed to call webhook: <urlopen error timed out>'
        self.assertEqual([error], logs.output)

    def test_no_ffmpeg_probing_per_event(self):
        probe = AssertionError('ffmpeg probed')
        self._patch('motioneye.mediafiles.find_ffmpeg', side_effect=probe)
        args = ['-c', _CONF, '1', 'storage', '--', '%t']
        request = self._call(*args)
        self.assertEqual(_HA, request.full_url)

    def test_home_assistant_body_is_unchanged(self):
        head, _, tail = _MOTION_URL.partition('%')
        tail = _expand(f'%{tail}')  # what motion passes
        new = self._call('-c', _CONF, '1', 'notifications', '--', tail)
        old = self._call('POSTj', head + tail)

        self.assertEqual(_HA, new.full_url)
        self.assertEqual(old.full_url, new.full_url)
        self.assertEqual(old.data, new.data)
        self.assertEqual(old.headers, new.headers)
        body = json.loads(new.data)
        self.assertEqual(('t9', 'hass-motioneye'), (body['camera_id'], body['src']))


if __name__ == '__main__':
    unittest.main()
