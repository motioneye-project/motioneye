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
from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit

from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPResponse

from motioneye import settings
from motioneye.utils import (
    GetCamerasResponse,
    build_digest_header,
    cast_future,
    parse_digest_challenge,
    pretty_http_error,
)
from motioneye.utils.http import MjpegUrl

__all__ = ('test_mjpeg_url',)


def test_mjpeg_url(
    data: dict, auth_modes: list[str], allow_jpeg: bool
) -> Future[GetCamerasResponse]:
    url_obj = MjpegUrl.from_dict(data)
    url = str(url_obj)
    log_url = url.split('?')[0]  # the query may hold a password

    called = [False]
    status_2xx = [False]
    http_11 = [False]

    future: Future = Future()

    def do_request(authorization: str | None = None) -> Future[HTTPResponse]:
        if url_obj.username:
            auth = auth_modes[0]

        else:
            auth = 'no'

        logging.debug(f'testing (m)jpg netcam at {log_url} using {auth} authentication')

        # redirects are reported, not followed: Tornado's client never answers when
        # the redirected request fails, and a digest answer is for one URL only
        auth_modes.pop(0)
        if authorization is not None:  # Tornado's client does basic only
            request = HTTPRequest(
                url,
                headers={'Authorization': authorization},
                follow_redirects=False,
                connect_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                request_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                header_callback=on_header,
            )

        else:
            request = HTTPRequest(
                url,
                auth_username=url_obj.username,
                auth_password=url_obj.password or '',
                auth_mode='basic',
                follow_redirects=False,
                connect_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                request_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                header_callback=on_header,
            )

        fetch_future = cast_future(
            AsyncHTTPClient(force_instance=True).fetch(request, raise_error=False)
        )
        fetch_future.add_done_callback(on_response)
        return fetch_future

    def on_header(header: str):
        header = header.lower()
        if header.startswith('content-type') and status_2xx[0]:
            content_type = header.split(':')[1].strip()
            called[0] = True

            if content_type in ['image/jpg', 'image/jpeg', 'image/pjpg'] and allow_jpeg:
                future.set_result(
                    GetCamerasResponse(
                        [
                            {
                                'id': 1,
                                'name': 'JPEG Network Camera',
                                'keep_alive': http_11[0],
                            }
                        ],
                        None,
                    )
                )

            elif content_type.startswith('multipart/x-mixed-replace'):
                future.set_result(
                    GetCamerasResponse(
                        [
                            {
                                'id': 1,
                                'name': 'MJPEG Network Camera',
                                'keep_alive': http_11[0],
                            }
                        ],
                        None,
                    )
                )

            else:
                future.set_result(
                    GetCamerasResponse(None, error='not a supported network camera')
                )

        else:
            # check for the status header
            m = re.match(r'^http/1.(\d) (\d+) ', header)
            if m:
                if int(m.group(2)) / 100 == 2:
                    status_2xx[0] = True

                if m.group(1) == '1':
                    http_11[0] = True

    def on_response(res_future: Future):
        try:
            response = res_future.result()
        except Exception as e:
            # network errors and timeouts raise, even after a stream was recognized;
            # some name the whole URL, whose query may hold a password
            error = Exception(str(e).replace(url, log_url))
            response = HTTPResponse(HTTPRequest(url), 599, error=error)

        if called[0]:
            return

        if response.code == 401 and auth_modes and url_obj.username:
            status_2xx[0] = False
            if auth_modes[0] != 'digest':
                do_request()
                return

            challenge = parse_digest_challenge(
                response.headers.get_list('WWW-Authenticate')
            )
            if challenge is not None:
                authorization = build_digest_header(
                    'GET', url, url_obj.username, url_obj.password or '', challenge
                )
                if authorization is not None:
                    do_request(authorization)
                    return

        called[0] = True
        if 300 <= response.code < 400:
            # without a query or credentials, which may hold a password
            location = urlsplit(response.headers.get('Location', ''))
            location = location._replace(
                netloc=location.netloc.rpartition('@')[2], query='', fragment=''
            )
            error = f'the camera redirects to {location.geturl()}'

        elif response.error:
            error = pretty_http_error(response)

        else:
            error = 'not a supported network camera'

        logging.error(f'testing (m)jpg netcam at {log_url} failed: {error}')
        future.set_result(GetCamerasResponse(None, error=error))

    do_request()

    return future
