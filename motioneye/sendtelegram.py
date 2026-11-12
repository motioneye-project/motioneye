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
from __future__ import annotations

import json
import logging
import os
import re
import signal
import socket
import time
from collections.abc import Callable
from datetime import datetime
from http.client import HTTPException, HTTPSConnection
from secrets import token_hex
from urllib.parse import urlencode

from tornado.ioloop import IOLoop

from motioneye import config, mediafiles, meyectl, motionctl, settings, utils

_HOST = 'api.telegram.org'
_CONNECT_TIMEOUT = 10
# Telegram sometimes never answers a request it got: give up after this long
# without data, rather than limiting the whole upload
_STALL_TIMEOUT = 60
# a socket timeout counts for the whole of a sendall(), so the body is sent in
# pieces, each of which only has to go out within the stall timeout
_UPLOAD_PIECE = 64 * 1024


class TelegramError(RuntimeError):
    def __init__(self, code, description, retry_after):
        super().__init__(f'telegram replied {code}: {description}')
        self.retry_after = retry_after


class _NotConnected(OSError):
    """Nothing of the request was sent, so it can be sent again."""


def _post_once(path: str, body: bytes, content_type: str) -> dict:
    # a new connection per request: none is reused after a stalled one
    conn = HTTPSConnection(_HOST, timeout=_CONNECT_TIMEOUT)
    try:
        try:
            conn.connect()

        except OSError as e:
            raise _NotConnected(f'could not connect to {_HOST}: {e}') from e

        conn.sock.settimeout(_STALL_TIMEOUT)
        pieces = (
            body[i : i + _UPLOAD_PIECE] for i in range(0, len(body), _UPLOAD_PIECE)
        )
        headers = {'Content-Type': content_type, 'Content-Length': str(len(body))}
        conn.request('POST', path, pieces, headers)
        response = conn.getresponse()
        code = response.status
        reply = response.read()

    finally:
        conn.close()

    try:
        result = json.loads(reply)

    except ValueError:
        result = {}

    if code != 200 or result.get('ok') is not True:
        raise TelegramError(
            code,
            result.get('description') or 'no description',
            (result.get('parameters') or {}).get('retry_after')
            if code == 429
            else None,
        )

    return result


def _post(path: str, body: bytes, content_type: str, retry: bool) -> dict:
    try:
        return _post_once(path, body, content_type)

    except _NotConnected as e:
        # once something was sent, Telegram may have it even if the reply is lost
        # or late, so only a request that never went out is sent again
        if not retry:
            raise

        delay = 5
        logging.warning(f'telegram request failed, retrying in {delay}s: {e}')

    except TelegramError as e:
        if not retry or not isinstance(e.retry_after, int):
            raise

        if not 0 <= e.retry_after <= 30:
            raise

        delay = e.retry_after
        logging.warning(f'{e}, retrying in {delay}s')

    time.sleep(delay)
    return _post_once(path, body, content_type)


def _photo_form(
    chat_id, caption: str, filename: str, reply_to: int | None = None
) -> tuple[bytes, str]:
    boundary = token_hex(16)
    name = os.path.basename(filename).replace('"', '')
    with open(filename, 'rb') as f:
        photo = f.read()

    fields = {'chat_id': str(chat_id)}
    if caption:
        fields['caption'] = caption
    if reply_to is not None:
        # a reply to the text sent first; still sent if that text is gone
        fields['reply_parameters'] = json.dumps(
            {'message_id': reply_to, 'allow_sending_without_reply': True}
        )

    lines = []
    for field, value in fields.items():
        lines += [
            f'--{boundary}',
            f'Content-Disposition: form-data; name="{field}"',
            '',
            value,
        ]
    lines += [
        f'--{boundary}',
        f'Content-Disposition: form-data; name="photo"; filename="{name}"',
        'Content-Type: application/octet-stream',
        '',
    ]
    head = '\r\n'.join(lines).encode() + b'\r\n'
    body = head + photo + f'\r\n--{boundary}--\r\n'.encode()

    return body, f'multipart/form-data; boundary={boundary}'


def send_message(
    api_key, chat_id, message, files, retry=True, *, reply_to: int | None = None
) -> int | None:
    """Send the message as text when there are no files, else the files as photos.

    With reply_to, the photos are replies to that message, which carried the text
    already, so they have no caption. Returns the id of a text message sent."""
    if not files:
        logging.info('no files')
        body = urlencode({'chat_id': chat_id, 'text': message}).encode()
        result = _post(
            f'/bot{api_key}/sendMessage',
            body,
            'application/x-www-form-urlencoded',
            retry,
        )
        message_id = (result.get('result') or {}).get('message_id')
        return message_id if isinstance(message_id, int) else None

    logging.info('files present')
    caption = '' if reply_to is not None else message
    failed = 0
    for f in files:
        try:
            body, content_type = _photo_form(chat_id, caption, f, reply_to)
            _post(f'/bot{api_key}/sendPhoto', body, content_type, retry)

        except (RuntimeError, OSError, HTTPException) as e:
            logging.error(f'failed to send "{os.path.basename(f)}": {e}')
            failed += 1

    if failed > 0:
        raise RuntimeError(f'{failed} of {len(files)} pictures not sent')

    logging.debug('sending telegram')
    return None


def make_message(
    message: str,
    camera_id: int,
    moment: datetime,
    timespan: int,
    callback: Callable,
    text_first: bool = False,
) -> None:
    """Call back with the message and the pictures of the event, once the time
    span for them has passed. With text_first, call back with the message and
    None right away, so the text goes out before the wait for the pictures."""
    camera_config = config.get_camera(camera_id)

    # we must start the IO loop for the media list subprocess polling
    io_loop = IOLoop.current()

    format_dict = {
        'camera': camera_config['camera_name'],
        'hostname': socket.gethostname(),
        'moment': moment.strftime('%Y-%m-%d %H:%M:%S'),
        'timezone': datetime.now().astimezone().tzname() or 'local time',
    }
    logging.debug('creating telegram message')
    m = message % format_dict

    def on_media_files(media_files):
        io_loop.stop()

        timestamp = time.mktime(moment.timetuple())
        files: list | None = (
            media_files.result() if hasattr(media_files, 'result') else media_files
        )
        if files is None:
            # mediafiles has logged why; the hint only helps after a timeout
            if time.monotonic() - listing_started >= settings.LIST_MEDIA_TIMEOUT:
                logging.warning(
                    f'picture listing timed out after {settings.LIST_MEDIA_TIMEOUT}s; '
                    'sending notification without pictures; consider raising '
                    'list_media_timeout_telegram'
                )

            else:
                logging.warning(
                    'picture listing failed; sending notification without pictures'
                )

            files = []

        if files:
            logging.debug('got media files')
            files = [m for m in files if abs(m['timestamp'] - timestamp) < timespan]
            files.sort(key=lambda m: m['timestamp'])
            files = [
                os.path.join(camera_config['target_dir'], re.sub('^/', '', m['path']))
                for m in files
            ]
            logging.debug(f'selected {len(files)} pictures')

        callback(m, files)

    if not timespan:
        on_media_files([])

        return

    if text_first:
        callback(m, None)

    logging.debug(f'waiting {timespan}s for pictures to be taken')
    time.sleep(timespan)  # give motion some time to create motion pictures

    prefix = None
    picture_filename: str = camera_config.get('picture_filename', '')
    snapshot_filename: str = camera_config.get('snapshot_filename', '')

    if (
        (picture_filename or snapshot_filename)
        and not picture_filename
        or picture_filename.startswith('%Y-%m-%d/')
        and not snapshot_filename
        or snapshot_filename.startswith('%Y-%m-%d/')
    ):
        prefix = moment.strftime('%Y-%m-%d')
        logging.debug(f'narrowing down still images path lookup to {prefix}')

    # only pictures within +/- timespan are used, see on_media_files()
    event_timestamp: float = time.mktime(moment.timetuple())
    listing_started = time.monotonic()
    fut = utils.cast_future(
        mediafiles.list_media(
            camera_config,
            media_type='picture',
            prefix=prefix,
            min_timestamp=event_timestamp - timespan,
            max_timestamp=event_timestamp + timespan,
        )
    )
    fut.add_done_callback(on_media_files)
    io_loop.start()

    return


def parse_options(parser, args):
    # the settings are in the camera config
    parser.description = 'Send Telegram using bot api'
    parser.add_argument('motion_camera_id', help='the id of the motion camera')
    parser.add_argument('moment', help='the moment in ISO-8601 format')
    options, extra = parser.parse_known_args(args)
    if extra:  # without their values, they may be secrets
        parser.error(
            f'{len(extra)} unexpected arguments, '
            'motionEye converts its own older commands when it starts'
        )

    try:  # not a type=, older commands have the chat id here
        options.moment = datetime.fromisoformat(options.moment)

    except ValueError:
        parser.error('moment must be in ISO-8601 format')

    return options


def main(parser, args):
    # the motion daemon overrides SIGCHLD,
    # so we must restore it here,
    # or otherwise media listing won't work
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    options = parse_options(parser, args)
    meyectl.configure_logging('telegram')
    logging.debug(options)
    message = 'Motion has been detected by camera "%(camera)s/%(hostname)s" at %(moment)s (%(timezone)s).'

    camera_id = motionctl.motion_camera_id_to_camera_id(options.motion_camera_id)
    stored = config.get_notification_settings(camera_id, config.SENDTELEGRAM_KEYS)
    if not stored:
        logging.error(
            f'motion camera {options.motion_camera_id} has no Telegram settings'
        )
        return

    vars(options).update(stored)

    # do not wait too long for media list,
    # telegram notifications are critical
    try:
        options.timespan = int(options.timespan)
    except (TypeError, ValueError):
        options.timespan = 0

    settings.LIST_MEDIA_TIMEOUT = settings.LIST_MEDIA_TIMEOUT_TELEGRAM
    text_first = str(getattr(options, 'text_first', '')).lower() == 'true'
    text_id: list[int | None] = []  # the id of the text sent first, if any

    def on_message(message, files):
        try:
            if files is None:  # the text, before the wait for the pictures
                logging.info(f'sending telegram : {message}')
                text_id.append(send_message(options.api, options.chatid, message, []))
                logging.info('telegram text sent')
                return

            if text_id and not files:
                logging.info('no pictures to add to the text sent')
                return

            logging.info(f'sending telegram : {message}')
            send_message(
                options.api,
                options.chatid,
                message,
                files or [],
                reply_to=text_id[0] if text_id else None,
            )
            logging.info('telegram sent')

        except Exception:
            logging.exception('failed to send telegram')

        logging.debug('bye!')

    make_message(
        message,
        camera_id,
        options.moment,
        options.timespan,
        on_message,
        text_first=text_first,
    )
