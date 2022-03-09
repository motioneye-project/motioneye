
# Copyright (c) 2020 Vlsarro
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
import functools
import logging
import re
import socket

from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream

from motioneye import settings
from motioneye.utils import build_basic_header, GetCamerasResponse, cast_future
from motioneye.utils.http import RtspUrl


__all__ = ('test_rtsp_url',)


def test_rtsp_url(data: dict) -> 'Future[GetCamerasResponse]':
    url_obj = RtspUrl.from_dict(data)
    url = str(url_obj)

    called = [False]
    send_auth = [False]
    timeout = [None]
    stream = None

    io_loop = IOLoop.instance()
    future = Future()

    def connect():
        if send_auth[0]:
            logging.debug('testing rtsp netcam at %s (this time with credentials)' % url)

        else:
            logging.debug('testing rtsp netcam at %s' % url)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.settimeout(settings.MJPG_CLIENT_TIMEOUT)
        stream = IOStream(s)
        stream.set_close_callback(on_close)
        f = stream.connect((url_obj.host, int(url_obj.port)))
        f.add_done_callback(on_connect)

        timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=settings.MJPG_CLIENT_TIMEOUT),
                                         functools.partial(on_connect, _timeout=True))

        return stream

    def on_connect(f: Future, _timeout: bool = False) -> None:
        try:
            io_loop.remove_timeout(timeout[0])
            s = f.result()
        except Exception as e:
            logging.error(f'[ON_CONNECT] Stream connection error occurred: {e}', exc_info=True)
            if _timeout:
                return handle_error('timeout connecting to rtsp netcam')
            else:
                return handle_error('failed to connect to rtsp netcam')
        else:
            logging.debug('connected to rtsp netcam')

            lines = [
                'OPTIONS %s RTSP/1.0' % url,
                'CSeq: 1',
                'User-Agent: motionEye'
            ]

            if url_obj.username and send_auth[0]:
                auth_header = 'Authorization: ' + build_basic_header(url_obj.username, url_obj.password)
                lines.append(auth_header)

            lines += [
                '',
                ''
            ]

            write_future = s.write('\r\n'.join(lines).encode('utf-8'))
            write_future.add_done_callback(seek_rtsp)

    def seek_rtsp(f: Future):
        try:
            f.result()
        except Exception as e:
            logging.error(f'[SEEK_RTSP] Error occurred: {e}', exc_info=True)
            if check_error():
                return
        else:
            r_future = cast_future(stream.read_until_regex(b'RTSP/1.0 \d+ '))
            r_future.add_done_callback(on_rtsp)
            timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=settings.MJPG_CLIENT_TIMEOUT),
                                             functools.partial(on_rtsp, r_future))

    def on_rtsp(f: Future):
        try:
            io_loop.remove_timeout(timeout[0])
            data = f.result()
        except Exception as e:
            logging.error(f'[ON_RTSP] Error occurred: {e}', exc_info=True)
            handle_error('timeout waiting for rtsp netcam response')
        else:
            if not data:
                handle_error('timeout waiting for rtsp netcam response')

            if data.endswith(b'200 '):
                seek_server()

            elif data.endswith(b'401 '):
                if not url_obj.username or send_auth[0]:
                    # either credentials not supplied, or already sent
                    handle_error('authentication failed')

                else:
                    seek_www_authenticate()

            else:
                handle_error('rtsp netcam returned erroneous response: %s' % data)

    def seek_server():
        if check_error():
            return

        future = stream.read_until_regex(b'Server: .*')

        def f(f):
            on_server(f.result())

        future.add_done_callback(f)
        
        timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=1), on_server)

    def on_server(data=None):
        io_loop.remove_timeout(timeout[0])
        if data:
            identifier = re.findall('Server: (.*)', data.decode())[0].strip()
            logging.debug('rtsp netcam identifier is "%s"' % identifier)

        else:
            identifier = None
            logging.debug('no rtsp netcam identifier')

        handle_success(identifier)

    def seek_www_authenticate():
        if check_error():
            return

        f = cast_future(stream.read_until_regex(b'WWW-Authenticate: .*'))
        f.add_done_callback(on_www_authenticate)

        timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=1), on_www_authenticate)

    def on_www_authenticate(f: Future):
        auth_timeout_msg = 'timeout waiting for rtsp netcam response'
        auth_timeout_log_msg = 'timeout waiting for rtsp auth scheme'
        try:
            io_loop.remove_timeout(timeout[0])
            data = f.result()
        except Exception as e:
            logging.error(f'[ON_WWW_AUTH] {auth_timeout_log_msg}: {e}', exc_info=True)
            handle_error(f'{auth_timeout_msg}')
        else:
            if data:
                scheme = re.findall(b'WWW-Authenticate: ([^\s]+)', data)[0].strip()
                logging.debug('rtsp netcam auth scheme: %s' % scheme)
                if scheme.lower() == 'basic':
                    send_auth[0] = True
                    connect()

                else:
                    logging.debug('rtsp auth scheme digest not supported, considering credentials ok')
                    handle_success('(unknown) ')

            else:
                logging.error(f'{auth_timeout_log_msg}')
                handle_error(f'{auth_timeout_msg}')

    def on_close():
        if called[0]:
            return

        if not check_error():
            handle_error('connection closed')

    def handle_success(identifier):
        if called[0]:
            return

        called[0] = True
        cameras = []
        if identifier:
            identifier = ' ' + identifier

        else:
            identifier = ''

        cameras.append({'id': 'tcp', 'name': '%sRTSP/TCP Camera' % identifier})
        cameras.append({'id': 'udp', 'name': '%sRTSP/UDP Camera' % identifier})

        future.set_result(GetCamerasResponse(cameras, None))

    def handle_error(e):
        if called[0]:
            return

        called[0] = True
        logging.error('rtsp client error: %s' % str(e))

        try:
            stream.close()

        except Exception:
            pass

        future.set_result(GetCamerasResponse(None, error=str(e)))

    def check_error():
        error = getattr(stream, 'error', None)
        if error and getattr(error, 'strerror', None):
            handle_error(error.strerror)
            return True

        if stream and stream.socket is None:
            handle_error('connection closed')
            stream.close()

            return True

        return False

    stream = connect()
    return future
