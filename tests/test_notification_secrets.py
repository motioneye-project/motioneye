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
import unittest
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import config, meyectl, sendmail, sendtelegram, settings

_TOKEN = '123456:telegram-token'
_PASSWORD = '1234'  # must not be converted to a number
_MOMENT = '2026-01-01T00:00:00'
_NOTIFICATIONS = {
    'email_notifications_enabled': True,
    'email_notifications_smtp_server': 'smtp.example',
    'email_notifications_smtp_port': '25',
    'email_notifications_smtp_account': 'me',
    'email_notifications_smtp_password': _PASSWORD,
    'email_notifications_smtp_tls': False,
    'email_notifications_from': '',
    'email_notifications_addresses': 'a@example',
    'telegram_notifications_enabled': True,
    'telegram_notifications_api': _TOKEN,
    'telegram_notifications_chat_id': '42',
}


def _find_command(command):
    return f'/usr/bin/python3 meyectl.py {command} -c /etc/motioneye/motioneye.conf'


@patch('builtins._', str, create=True)
@patch('motioneye.meyectl.find_command', _find_command)
class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.conf_dir = mkdtemp()
        self.addCleanup(rmtree, self.conf_dir)

        self.camera = {'@id': 1, '@enabled': True, 'netcam_url': 'rtsp://example/'}
        self.camera.update(width=640, height=480)
        config._set_default_motion_camera(1, self.camera)
        self.camera['target_dir'] = self.conf_dir

        main_config: dict = {}
        config._set_default_motion(main_config)
        patcher = patch('motioneye.config.get_main', return_value=main_config)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _save(self, **notifications):
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(notifications)
        return config.motion_camera_ui_to_dict(ui, self.camera)

    def test_secrets_are_not_on_the_command_line(self):
        on_event_start = self._save(**_NOTIFICATIONS)['on_event_start']

        self.assertIn(' sendmail ', on_event_start)
        self.assertIn(' sendtelegram ', on_event_start)
        self.assertNotIn(_TOKEN, on_event_start)
        self.assertNotIn(f"'{_PASSWORD}'", on_event_start)

    def test_secrets_round_trip_through_the_camera_file(self):
        lines = config._dict_to_conf([], self._save(**_NOTIFICATIONS))
        path = os.path.join(self.conf_dir, 'camera-1.conf')
        with open(path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        os.chmod(path, 0o600)

        self.addCleanup(config._camera_config_cache.pop, 1, None)
        with patch.object(settings, 'CONF_PATH', self.conf_dir):
            ui = config.motion_camera_dict_to_ui(config.get_camera(1))

        self.assertEqual(_PASSWORD, ui['email_notifications_smtp_password'])
        self.assertEqual(_TOKEN, ui['telegram_notifications_api'])

    def test_existing_command_line_secrets_are_still_read(self):
        self.camera['on_event_start'] = (
            f"{_find_command('sendmail')} 'smtp.example' '25' 'me' 'old\\;pw%%' "
            "'false' '' 'a@example' 'motion_start' '%t' '%Y-%m-%dT%H:%M:%S' '5'; "
            f"{_find_command('sendtelegram')} 'old-token' '42' '%t' "
            "'%Y-%m-%dT%H:%M:%S' '5'"
        )
        ui = config.motion_camera_dict_to_ui(self.camera)

        self.assertEqual('old;pw%', ui['email_notifications_smtp_password'])
        self.assertEqual('old-token', ui['telegram_notifications_api'])

    def test_disabling_clears_the_stored_secret(self):
        self.camera['@telegram_notifications_api'] = _TOKEN
        data = self._save(telegram_notifications_enabled=False)

        self.assertEqual('', data['@telegram_notifications_api'])


@patch('motioneye.settings.LIST_MEDIA_TIMEOUT', 120)
@patch('motioneye.meyectl.configure_logging')
@patch('motioneye.motionctl.motion_camera_id_to_camera_id', return_value=1)
@patch(
    'motioneye.config.get_camera',
    return_value={
        '@email_notifications_smtp_password': _PASSWORD,
        '@telegram_notifications_api': _TOKEN,
    },
)
class SenderTest(unittest.TestCase):
    @patch('motioneye.sendmail.send_mail')
    @patch('motioneye.sendmail.make_message')
    def test_email_uses_the_stored_password(self, make_message, send_mail, *_):
        smtp = ['smtp.example', '25', 'me', '', 'false', 'a@example', 'b@example']
        args = ['-c', 'motioneye.conf', *smtp, 'motion_start', '1', _MOMENT, '5']
        sendmail.main(meyectl.make_arg_parser('sendmail'), args)

        on_message = make_message.call_args.args[-1]
        on_message('subject', 'message', [])
        self.assertEqual(_PASSWORD, send_mail.call_args.args[3])

    @patch('motioneye.sendtelegram.send_message')
    @patch('motioneye.sendtelegram.make_message')
    def test_telegram_uses_the_stored_token(self, make_message, send_message, *_):
        args = ['-c', 'motioneye.conf', '', '42', '1', _MOMENT, '5']
        sendtelegram.main(meyectl.make_arg_parser('sendtelegram'), args)

        on_message = make_message.call_args.args[-1]
        on_message('message', [])
        self.assertEqual(_TOKEN, send_message.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
