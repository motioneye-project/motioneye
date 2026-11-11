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
import socket
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    @patch('motioneye.sendtelegram.IOLoop')
    def test_telegram_sends_the_text_before_the_wait_when_asked(
        self, _loop, sleep, list_media, _camera
    ):
        order = []
        sleep.side_effect = lambda seconds: order.append(('sleep', seconds))
        callback = Mock(side_effect=lambda m, files: order.append((m, files)))

        sendtelegram.make_message(
            'motion at %(camera)s', 1, _MOMENT, _TIMESPAN, callback, text_first=True
        )
        on_media_files = list_media.return_value.add_done_callback.call_args.args[0]
        on_media_files([])

        self.assertEqual(
            [('motion at cam', None), ('sleep', _TIMESPAN), ('motion at cam', [])],
            order,
        )

    @patch('motioneye.sendtelegram.IOLoop')
    def test_telegram_waits_for_the_pictures_first_by_default(
        self, _loop, sleep, list_media, _camera
    ):
        callback = Mock()
        sendtelegram.make_message('message', 1, _MOMENT, _TIMESPAN, callback)

        sleep.assert_called_once_with(_TIMESPAN)
        callback.assert_not_called()


class _FakeConnection:
    """A connection to Telegram, answering with the next of the replies: an
    OSError when connecting, _STALLED once the request was sent, or (code, body)."""

    def __init__(self, replies, made):
        self.replies = replies
        self.request_args = None
        self.stall_timeout = None
        self.closed = False
        made.append(self)

    def connect(self):
        if isinstance(self.replies[0], OSError):
            raise self.replies.pop(0)

        self.sock = SimpleNamespace(settimeout=self._set_stall_timeout)

    def _set_stall_timeout(self, timeout):
        self.stall_timeout = timeout

    def request(self, method, path, body, headers):
        body = list(body)
        self.pieces = [len(piece) for piece in body]
        self.request_args = (method, path, b''.join(body), headers)

    def getresponse(self):
        reply = self.replies.pop(0)
        if reply is _STALLED:
            raise TimeoutError('timed out')

        code, body = reply
        return SimpleNamespace(status=code, read=lambda: body)

    def close(self):
        self.closed = True


_OK = (200, b'{"ok": true, "result": {}}')
_STALLED = object()  # sent, but the reply never came
_TOKEN = '123:secret'
_PICTURES = ('0.jpg', 'Küche/1.jpg', '2.jpg')


def _too_many_requests(retry_after):
    return 429, json.dumps(
        {
            'ok': False,
            'description': f'Too Many Requests: retry after {retry_after}',
            'parameters': {'retry_after': retry_after},
        }
    ).encode()


def _form_fields(request_args):
    """The fields of a multipart/form-data request, as {name: (filename, value)}."""
    _method, _path, body, headers = request_args
    boundary = headers['Content-Type'].split('boundary=')[1].encode()
    fields = {}
    for part in body.split(b'--' + boundary)[1:-1]:
        head, value = part[2:-2].split(b'\r\n\r\n', 1)
        disposition = head.split(b'\r\n')[0].decode()
        name = disposition.split('name="')[1].split('"')[0]
        filename = None
        if 'filename=' in disposition:
            filename = disposition.split('filename="')[1].split('"')[0]

        fields[name] = (filename, value)

    return fields


class SendMessageTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pictures = []
        for name in _PICTURES:
            path = os.path.join(tmp.name, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(b'jpeg ' + name.encode())

            self.pictures.append(path)

    def _send(
        self,
        replies,
        message='message',
        files=(),
        chat_id=42,
        retry=True,
        reply_to=None,
    ):
        self.sleeps = []
        self.connections = []
        replies = list(replies)
        with (
            patch(
                'motioneye.sendtelegram.HTTPSConnection',
                side_effect=lambda host, timeout: self._connect(replies, host, timeout),
            ),
            patch('motioneye.sendtelegram.time.sleep', side_effect=self.sleeps.append),
        ):
            return sendtelegram.send_message(
                _TOKEN, chat_id, message, list(files), retry, reply_to=reply_to
            )

    def _connect(self, replies, host, timeout):
        # 10 s to connect
        self.assertEqual(('api.telegram.org', 10), (host, timeout))
        return _FakeConnection(replies, self.connections)

    def _sent(self):
        return [c for c in self.connections if c.request_args]

    def test_sends_the_message_url_encoded(self):
        self._send([_OK], message='A & B +1 Küche')

        method, path, body, headers = self.connections[0].request_args
        self.assertEqual(('POST', f'/bot{_TOKEN}/sendMessage'), (method, path))
        self.assertEqual(b'chat_id=42&text=A+%26+B+%2B1+K%C3%BCche', body)
        self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
        self.assertTrue(self.connections[0].closed)

    def test_gives_up_on_a_stalled_request_only(self):
        # 60 s without data once connected, but no limit for the whole upload
        self._send([_OK])

        self.assertEqual(60, self.connections[0].stall_timeout)

    def test_sends_a_picture_in_pieces(self):
        # a socket timeout counts for a whole sendall(), so one piece would limit
        # the whole upload to 60 s; each piece only has to go out within 60 s
        with open(self.pictures[0], 'wb') as f:
            f.write(b'\xff' * (200 * 1024))

        self._send([_OK], files=self.pictures[:1])

        connection = self.connections[0]
        _method, _path, body, headers = connection.request_args
        self.assertEqual(str(len(body)), headers['Content-Length'])
        self.assertGreater(len(connection.pieces), 3)
        self.assertLessEqual(max(connection.pieces), 64 * 1024)

    def test_raises_telegrams_description_when_rejected(self):
        reply = b'{"ok": false, "error_code": 401, "description": "Unauthorized"}'
        with self.assertRaises(RuntimeError) as cm:
            self._send([(401, reply)])

        self.assertEqual('telegram replied 401: Unauthorized', str(cm.exception))
        self.assertNotIn(_TOKEN, str(cm.exception))
        self.assertTrue(self.connections[0].closed)

    def test_raises_on_a_reply_that_is_not_json(self):
        with self.assertRaisesRegex(
            RuntimeError, '^telegram replied 502: no description$'
        ):
            self._send([(502, b'<html>Bad Gateway</html>')])

    def test_sends_the_other_pictures_when_one_is_rejected(self):
        rejected = (400, b'{"ok": false, "description": "Bad Request: PHOTO_INVALID"}')
        with (
            self.assertLogs(level='ERROR') as logs,
            self.assertRaisesRegex(RuntimeError, '^1 of 3 pictures not sent$'),
        ):
            self._send(
                [_OK, rejected, _OK], message='Küche', files=self.pictures, chat_id='42'
            )

        self.assertEqual(
            [
                {
                    'chat_id': (None, b'42'),
                    'caption': (None, 'Küche'.encode()),
                    'photo': (os.path.basename(name), b'jpeg ' + name.encode()),
                }
                for name in _PICTURES
            ],
            [_form_fields(c.request_args) for c in self.connections],
        )
        self.assertEqual(
            [f'/bot{_TOKEN}/sendPhoto'] * 3,
            [c.request_args[1] for c in self.connections],
        )
        self.assertIn(
            'failed to send "1.jpg": telegram replied 400: Bad Request', logs.output[0]
        )
        self.assertTrue(all(c.closed for c in self.connections))

    def test_raises_a_connection_error_after_one_retry(self):
        timeout = TimeoutError('timed out')
        with self.assertRaises(OSError):
            self._send([timeout, timeout])

        self.assertEqual([5], self.sleeps)
        self.assertEqual(2, len(self.connections))
        self.assertEqual([], self._sent())

    def test_retries_once_on_a_new_connection_when_nothing_was_sent(self):
        not_resolved = socket.gaierror(-2, 'Name or service not known')
        with self.assertLogs(level='WARNING') as logs:
            self._send([not_resolved, _OK])

        self.assertEqual([5], self.sleeps)
        self.assertEqual(2, len(self.connections))
        self.assertIn('telegram request failed, retrying in 5s', logs.output[0])

    def test_does_not_retry_once_something_was_sent(self):
        with self.assertRaises(TimeoutError):
            self._send([_STALLED])

        self.assertEqual([], self.sleeps)
        self.assertEqual(1, len(self.connections))
        self.assertTrue(self.connections[0].closed)

    def test_sends_the_other_pictures_on_new_connections_after_a_stall(self):
        with (
            self.assertLogs(level='ERROR') as logs,
            self.assertRaisesRegex(RuntimeError, '^1 of 3 pictures not sent$'),
        ):
            self._send([_STALLED, _OK, _OK], files=self.pictures)

        self.assertEqual([], self.sleeps)
        self.assertEqual(3, len(self._sent()))
        self.assertIn('failed to send "0.jpg": timed out', logs.output[0])
        self.assertTrue(all(c.closed for c in self.connections))

    def test_sends_the_other_pictures_after_a_failed_retry(self):
        timeout = TimeoutError('timed out')
        with (
            self.assertLogs(level='WARNING'),
            self.assertRaisesRegex(RuntimeError, '^1 of 3 pictures not sent$'),
        ):
            self._send([timeout, timeout, _OK, _OK], files=self.pictures)

        self.assertEqual([5], self.sleeps)
        self.assertEqual(2, len(self._sent()))

    def test_sends_the_other_pictures_when_a_retry_stalls(self):
        with (
            self.assertLogs(level='WARNING'),
            self.assertRaisesRegex(RuntimeError, '^1 of 3 pictures not sent$'),
        ):
            self._send([_too_many_requests(3), _STALLED, _OK, _OK], files=self.pictures)

        self.assertEqual([3], self.sleeps)
        self.assertEqual(4, len(self._sent()))

    def test_a_missing_picture_does_not_stop_the_others(self):
        files = [self.pictures[0], '/no/such.jpg', self.pictures[2]]
        with (
            self.assertLogs(level='ERROR') as logs,
            self.assertRaisesRegex(RuntimeError, '^1 of 3 pictures not sent$'),
        ):
            self._send([_OK, _OK], files=files)

        self.assertEqual(2, len(self._sent()))
        self.assertIn('failed to send "such.jpg"', logs.output[0])

    def test_waits_as_long_as_flood_control_asks(self):
        with self.assertLogs(level='WARNING'):
            self._send([_too_many_requests(3), _OK])

        self.assertEqual([3], self.sleeps)

    def test_does_not_wait_longer_than_30s(self):
        with self.assertRaisesRegex(RuntimeError, '^telegram replied 429: Too Many'):
            self._send([_too_many_requests(60)])

        self.assertEqual([], self.sleeps)

    def test_returns_the_id_of_the_text_sent(self):
        message_id = self._send([(200, b'{"ok": true, "result": {"message_id": 7}}')])

        self.assertEqual(7, message_id)
        self.assertIsNone(self._send([_OK]))  # no id in the reply

    def test_pictures_reply_to_the_text_sent_first_without_a_caption(self):
        self._send([_OK, _OK], files=self.pictures[:2], reply_to=7)

        for connection in self._sent():
            fields = _form_fields(connection.request_args)
            self.assertEqual(
                {'message_id': 7, 'allow_sending_without_reply': True},
                json.loads(fields['reply_parameters'][1]),
            )
            self.assertNotIn('caption', fields)
            self.assertIn('photo', fields)

    def test_pictures_carry_the_caption_without_a_text_sent_first(self):
        self._send([_OK], files=self.pictures[:1])

        fields = _form_fields(self._sent()[0].request_args)
        self.assertEqual((None, b'message'), fields['caption'])
        self.assertNotIn('reply_parameters', fields)

    def test_does_not_retry_when_told_not_to(self):
        with self.assertRaises(OSError):
            self._send([TimeoutError('timed out')], retry=False)

        self.assertEqual([], self.sleeps)
        self.assertEqual(1, len(self.connections))


if __name__ == '__main__':
    unittest.main()
