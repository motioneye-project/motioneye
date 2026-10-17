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
import json
import os
import time
import unittest
from unittest.mock import Mock, patch

import pycurl

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

    @patch('motioneye.sendtelegram.IOLoop')
    def test_telegram_sends_pictures_oldest_first(
        self, _loop, _sleep, list_media, _camera
    ):
        callback = Mock()
        sendtelegram.make_message('message', 1, _MOMENT, _TIMESPAN, callback)

        on_media_files = list_media.return_value.add_done_callback.call_args.args[0]
        event = time.mktime(_MOMENT.timetuple())
        on_media_files(
            [{'path': f'/{s}.jpg', 'timestamp': event + s} for s in (2, 0, 1)]
        )
        paths = [f'/var/lib/motioneye/{s}.jpg' for s in (0, 1, 2)]
        self.assertEqual(paths, callback.call_args.args[1])


class _FakeCurl:
    def __init__(self, replies):
        self.replies = list(replies)
        self.options = {}
        self.posts = []
        self.closed = False

    def __getattr__(self, name):
        return getattr(pycurl, name)

    def setopt(self, option, value):
        self.options[option] = value

    def perform(self):
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply

        self.posts.append(self.options.get(pycurl.HTTPPOST))
        self.code, body = reply
        if pycurl.WRITEDATA in self.options:
            self.options[pycurl.WRITEDATA].write(body)

    def getinfo(self, info):
        return self.code

    def close(self):
        self.closed = True


_OK = (200, b'{"ok": true, "result": {}}')
_TOKEN = '123:secret'
_PICTURES = ['/0.jpg', '/Küche/1.jpg', '/2.jpg']


def _too_many_requests(retry_after):
    return 429, json.dumps(
        {
            'ok': False,
            'description': f'Too Many Requests: retry after {retry_after}',
            'parameters': {'retry_after': retry_after},
        }
    ).encode()


class SendMessageTest(unittest.TestCase):
    def _send(self, curl, message='message', files=(), chat_id=42, retry=True):
        self.sleeps = []
        with (
            patch('pycurl.Curl', return_value=curl),
            patch('motioneye.sendtelegram.time.sleep', side_effect=self.sleeps.append),
        ):
            sendtelegram.send_message(_TOKEN, chat_id, message, list(files), retry)

    def test_sends_the_message_url_encoded(self):
        curl = _FakeCurl([_OK])
        self._send(curl, message='A & B +1 Küche')

        self.assertEqual(
            'chat_id=42&text=A+%26+B+%2B1+K%C3%BCche', curl.options[pycurl.POSTFIELDS]
        )
        self.assertTrue(curl.closed)

    def test_gives_up_on_a_stalled_request_only(self):
        curl = _FakeCurl([_OK])
        self._send(curl)

        self.assertEqual(10, curl.options[pycurl.CONNECTTIMEOUT])
        self.assertEqual(1, curl.options[pycurl.LOW_SPEED_LIMIT])
        self.assertEqual(60, curl.options[pycurl.LOW_SPEED_TIME])
        self.assertNotIn(pycurl.TIMEOUT, curl.options)
        self.assertTrue(curl.closed)

    def test_raises_telegrams_description_when_rejected(self):
        curl = _FakeCurl(
            [(401, b'{"ok": false, "error_code": 401, "description": "Unauthorized"}')]
        )
        with self.assertRaises(RuntimeError) as cm:
            self._send(curl)

        self.assertEqual('telegram replied 401: Unauthorized', str(cm.exception))
        self.assertNotIn(_TOKEN, str(cm.exception))
        self.assertTrue(curl.closed)

    def test_raises_on_a_reply_that_is_not_json(self):
        curl = _FakeCurl([(502, b'<html>Bad Gateway</html>')])
        with self.assertRaisesRegex(
            RuntimeError, '^telegram replied 502: no description$'
        ):
            self._send(curl)

        self.assertTrue(curl.closed)

    def test_sends_the_other_pictures_when_one_is_rejected(self):
        curl = _FakeCurl(
            [
                _OK,
                (400, b'{"ok": false, "description": "Bad Request: PHOTO_INVALID"}'),
                _OK,
            ]
        )
        with (
            self.assertLogs(level='ERROR') as logs,
            self.assertRaisesRegex(RuntimeError, '^1 of 3 pictures not sent$'),
        ):
            self._send(curl, message='Küche', files=_PICTURES, chat_id='42')

        self.assertEqual(
            [
                [
                    ('chat_id', '42'),
                    ('caption', 'Küche'.encode()),
                    ('photo', (pycurl.FORM_FILE, os.fsencode(p))),
                ]
                for p in _PICTURES
            ],
            curl.posts,
        )
        self.assertIn(
            'failed to send "1.jpg": telegram replied 400: Bad Request', logs.output[0]
        )
        self.assertTrue(curl.closed)

    def test_stops_at_a_curl_error_after_one_retry(self):
        for files in ((), _PICTURES):
            with self.subTest(pictures=len(files)):
                timeout = pycurl.error(28, 'Operation timed out')
                curl = _FakeCurl([timeout, timeout])
                with self.assertRaises(pycurl.error):
                    self._send(curl, files=files, chat_id='42')

                self.assertEqual([5], self.sleeps)
                self.assertTrue(curl.closed)

    def test_retries_once_after_a_curl_error(self):
        curl = _FakeCurl([pycurl.error(92, 'HTTP/2 stream was not closed'), _OK])
        with self.assertLogs(level='WARNING') as logs:
            self._send(curl)

        self.assertEqual([5], self.sleeps)
        self.assertIn('telegram request failed, retrying in 5s', logs.output[0])

    def test_waits_as_long_as_flood_control_asks(self):
        curl = _FakeCurl([_too_many_requests(3), _OK])
        with self.assertLogs(level='WARNING'):
            self._send(curl)

        self.assertEqual([3], self.sleeps)

    def test_does_not_wait_longer_than_30s(self):
        curl = _FakeCurl([_too_many_requests(60)])
        with self.assertRaisesRegex(RuntimeError, '^telegram replied 429: Too Many'):
            self._send(curl)

        self.assertEqual([], self.sleeps)

    def test_does_not_retry_when_told_not_to(self):
        curl = _FakeCurl([pycurl.error(28, 'Operation timed out')])
        with self.assertRaises(pycurl.error):
            self._send(curl, retry=False)

        self.assertEqual([], self.sleeps)
        self.assertTrue(curl.closed)


if __name__ == '__main__':
    unittest.main()
