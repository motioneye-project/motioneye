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

import datetime
import time
import unittest
from unittest.mock import patch

from motioneye import sendmail, sendtelegram

_CAMERA = {
    'camera_name': 'cam',
    'target_dir': '/var/lib/motioneye',
    'picture_filename': '%Y-%m-%d/%H-%M-%S',
    'snapshot_filename': '%Y-%m-%d/%H-%M-%S',
}
_MOMENT = datetime.datetime(2026, 1, 1, 12, 0, 0)
_TIMESPAN = 5


@patch('motioneye.config.get_camera', return_value=_CAMERA)
@patch('motioneye.mediafiles.list_media')
@patch('time.sleep')
class PictureTimespanTest(unittest.TestCase):
    def _assert_timespan(self, list_media):
        event = time.mktime(_MOMENT.timetuple())
        kwargs = list_media.call_args.kwargs
        self.assertEqual(event - _TIMESPAN, kwargs.get('min_timestamp'))
        self.assertEqual(event + _TIMESPAN, kwargs.get('max_timestamp'))

    @patch('motioneye.sendmail.IOLoop')
    def test_email_lists_only_pictures_within_timespan(
        self, _loop, _sleep, list_media, _camera
    ):
        sendmail.make_message('subject', 'message', 1, _MOMENT, _TIMESPAN, None)
        self._assert_timespan(list_media)

    @patch('motioneye.sendtelegram.IOLoop')
    def test_telegram_lists_only_pictures_within_timespan(
        self, _loop, _sleep, list_media, _camera
    ):
        sendtelegram.make_message('message', 1, _MOMENT, _TIMESPAN, None)
        self._assert_timespan(list_media)


class TelegramPhotoOrderTest(unittest.TestCase):
    @patch('motioneye.sendtelegram.pycurl.Curl')
    def test_photos_are_sent_oldest_first(self, curl):
        newest_first = ['/pics/3.jpg', '/pics/2.jpg', '/pics/1.jpg']
        sendtelegram.send_message('token', 'chat', 'message', newest_first)

        c = curl.return_value
        posts = [a.args[1] for a in c.setopt.call_args_list if a.args[0] is c.HTTPPOST]
        sent = [dict(post)['photo'][1] for post in posts]
        self.assertEqual(['/pics/1.jpg', '/pics/2.jpg', '/pics/3.jpg'], sent)


if __name__ == '__main__':
    unittest.main()
