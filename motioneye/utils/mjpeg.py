
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

import logging
import re

from typing import List

from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPResponse

from motioneye import settings
from motioneye.utils import pretty_http_error, GetCamerasResponse, cast_future
from motioneye.utils.http import MjpegUrl


__all__ = ('test_mjpeg_url',)


def test_mjpeg_url(data: dict, auth_modes: List[str], allow_jpeg: bool) -> 'Future[GetCamerasResponse]':
    url_obj = MjpegUrl.from_dict(data)
    url = str(url_obj)

    called = [False]
    status_2xx = [False]
    http_11 = [False]

    future = Future()

    def do_request() -> 'Future[HTTPResponse]':
        if url_obj.username:
            auth = auth_modes[0]

        else:
            auth = 'no'

        logging.debug('testing (m)jpg netcam at %s using %s authentication' % (url, auth))

        request = HTTPRequest(url, auth_username=url_obj.username, auth_password=url_obj.password or '',
                              auth_mode=auth_modes.pop(0),
                              connect_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                              request_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                              header_callback=on_header, validate_cert=settings.VALIDATE_CERTS)

        fetch_future = cast_future(AsyncHTTPClient(force_instance=True).fetch(request))
        fetch_future.add_done_callback(on_response)
        return fetch_future

    def on_header(header: str):
        header = header.lower()
        if header.startswith('content-type') and status_2xx[0]:
            content_type = header.split(':')[1].strip()
            called[0] = True

            if content_type in ['image/jpg', 'image/jpeg', 'image/pjpg'] and allow_jpeg:
                future.set_result(GetCamerasResponse([{
                    'id': 1,
                    'name': 'JPEG Network Camera',
                    'keep_alive': http_11[0]
                }], None))

            elif content_type.startswith('multipart/x-mixed-replace'):
                future.set_result(GetCamerasResponse([{
                    'id': 1,
                    'name': 'MJPEG Network Camera',
                    'keep_alive': http_11[0]
                }], None))

            else:
                future.set_result(GetCamerasResponse(None, error='not a supported network camera'))

        else:
            # check for the status header
            m = re.match('^http/1.(\d) (\d+) ', header)
            if m:
                if int(m.group(2)) / 100 == 2:
                    status_2xx[0] = True

                if m.group(1) == '1':
                    http_11[0] = True

    def on_response(response: HTTPResponse):
        if not called[0]:
            if response.code == 401 and auth_modes and url_obj.username:
                status_2xx[0] = False
                do_request()

            else:
                called[0] = True
                error = pretty_http_error(response) if response.error else 'not a supported network camera'
                future.set_result(GetCamerasResponse(None, error=error))

    do_request()

    return future
