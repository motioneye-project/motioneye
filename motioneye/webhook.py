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

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from motioneye import settings


def parse_options(parser, args):
    parser.add_argument('method', help='the HTTP method to use')
    parser.add_argument('url', help='the URL, or only its end when kind is given')
    parser.add_argument('camera_id', nargs='?', help='the motionEye camera id')
    parser.add_argument('kind', nargs='?', help='the webhook whose stored URL to use')

    return parser.parse_args(args)


def main(parser, args):
    from motioneye import config, meyectl, utils

    options = parse_options(parser, args)

    meyectl.configure_logging('webhook', options.log_to_file)
    meyectl.configure_tornado()

    logging.debug('hello!')
    logging.debug('method = %s' % options.method)

    if options.kind:  # the URL up to its first % is in the camera config
        camera_id = int(options.camera_id)
        stored = config.get_camera(camera_id).get(f'@web_hook_{options.kind}_url', '')
        if not stored:
            logging.error(f'camera {camera_id} has no {options.kind} webhook URL')
            return

        options.url = stored.partition('%')[0] + options.url

    # some endpoints reject requests without a User-Agent with HTTP 403
    headers = {'User-Agent': 'motionEye'}
    parts = urllib.parse.urlparse(options.url)
    logging.debug(f'url = {parts.scheme}://{parts.hostname}')  # the rest may be secret
    url = options.url
    data = None

    if options.method == 'POST':
        headers['Content-Type'] = 'text/plain'
        data = b''

    elif options.method == 'POSTf':  # form url-encoded
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = parts.query.encode()
        url = options.url.split('?')[0]

    elif options.method == 'POSTj':  # json
        headers['Content-Type'] = 'application/json'
        data = urllib.parse.parse_qs(parts.query)
        data = {k: v[0] for (k, v) in list(data.items())}
        data = json.dumps(data).encode()
        url = options.url.split('?')[0]

    else:  # GET
        pass

    try:
        request = urllib.request.Request(url, data, headers=headers)
        utils.urlopen(request, timeout=settings.REMOTE_REQUEST_TIMEOUT)
        logging.debug('webhook successfully called')

    except urllib.error.URLError as e:  # its message has no URL
        logging.error('failed to call webhook: %s' % e)

    except Exception as e:  # e.g. an invalid URL, which its message would repeat
        logging.error(f'failed to call webhook: {type(e).__name__}')

    logging.debug('bye!')
