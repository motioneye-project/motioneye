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
from unittest.mock import patch

from motioneye import meyectl, sendtelegram

_TOKEN = '123456:telegram-bot-token'
_ARGS = [_TOKEN, 'chat', '1', '2026-01-01T00:00:00', '5']


class SendTelegramTest(unittest.TestCase):
    @patch('motioneye.settings.LIST_MEDIA_TIMEOUT', 120)
    @patch('motioneye.sendtelegram.make_message')
    @patch('motioneye.motionctl.motion_camera_id_to_camera_id', return_value=1)
    @patch('motioneye.meyectl.configure_logging')
    def test_api_key_is_not_logged(self, *mocks):
        with self.assertLogs(level='DEBUG') as logs:
            sendtelegram.main(meyectl.make_arg_parser('sendtelegram'), _ARGS)

        self.assertNotIn(_TOKEN, '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
