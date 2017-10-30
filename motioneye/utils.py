
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

import base64
import datetime
import functools
import hashlib
import logging
import os
import re
import socket
import sys
import time
import urllib
import urllib2
import urlparse

from PIL import Image, ImageDraw

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.iostream import IOStream
from tornado.ioloop import IOLoop

import settings


_SIGNATURE_REGEX = re.compile('[^a-zA-Z0-9/?_.=&{}\[\]":, -]')
_SPECIAL_COOKIE_NAMES = {'expires', 'domain', 'path', 'secure', 'httponly'}

MASK_WIDTH = 32

DEV_NULL = open('/dev/null', 'w')


COMMON_RESOLUTIONS = [
    (320, 200),
    (320, 240),
    (640, 480),
    (800, 480),
    (800, 600),
    (1024, 576),
    (1024, 600),
    (1024, 768),
    (1280, 720),
    (1280, 768),
    (1280, 800),
    (1280, 960),
    (1280, 1024),
    (1440, 900),
    (1440, 960),
    (1440, 1024),
    (1600, 1200),
    (1920, 1080)
]


def _(x):
    return x  # this could later be replaced by a proper translate function


def pretty_date_time(date_time, tzinfo=None, short=False):
    if date_time is None:
        return '(' + _('never') + ')'

    if isinstance(date_time, int):
        return pretty_date_time(datetime.datetime.fromtimestamp(date_time))

    if short:
        text = u'{day} {month}, {hm}'.format(
            day=date_time.day,
            month=date_time.strftime('%b'),
            hm=date_time.strftime('%H:%M')
        )
    
    else:
        text = u'{day} {month} {year}, {hm}'.format(
            day=date_time.day,
            month=date_time.strftime('%B'),
            year=date_time.year,
            hm=date_time.strftime('%H:%M')
        )
    
    if tzinfo:
        offset = tzinfo.utcoffset(datetime.datetime.utcnow()).seconds
        tz = 'GMT'
        if offset >= 0:
            tz += '+'

        else:
            tz += '-'
            offset = -offset

        tz += '%.2d' % (offset / 3600) + ':%.2d' % ((offset % 3600) / 60)

        text += ' (' + tz + ')'

    return text


def pretty_date(date):
    if date is None:
        return '(' + _('never') + ')'

    if isinstance(date, int):
        return pretty_date(datetime.datetime.fromtimestamp(date))

    return u'{day} {month} {year}'.format(
        day=date.day,
        month=_(date.strftime('%B')),
        year=date.year
    )


def pretty_time(time):
    if time is None:
        return ''

    if isinstance(time, datetime.timedelta):
        hour = time.seconds / 3600
        minute = (time.seconds % 3600) / 60
        time = datetime.time(hour, minute)

    return '{hm}'.format(
        hm=time.strftime('%H:%M')
    )


def pretty_duration(duration):
    if duration is None:
        duration = 0

    if isinstance(duration, datetime.timedelta):
        duration = duration.seconds + duration.days * 86400

    if duration < 0:
        negative = True
        duration = -duration

    else:
        negative = False

    days = int(duration / 86400)
    duration %= 86400
    hours = int(duration / 3600)
    duration %= 3600
    minutes = int(duration / 60)
    duration %= 60
    seconds = duration

    # treat special cases
    special_result = None
    if days != 0 and hours == 0 and minutes == 0 and seconds == 0:
        if days == 1:
            special_result = str(days) + ' ' + _('day')

        elif days == 7:
            special_result = '1 ' + _('week')

        elif days in [30, 31, 32]:
            special_result = '1 ' + _('month')

        elif days in [365, 366]:
            special_result = '1 ' + _('year')

        else:
            special_result = str(days) + ' ' + _('days')

    elif days == 0 and hours != 0 and minutes == 0 and seconds == 0:
        if hours == 1:
            special_result = str(hours) + ' ' + _('hour')

        else:
            special_result = str(hours) + ' ' + _('hours')

    elif days == 0 and hours == 0 and minutes != 0 and seconds == 0:
        if minutes == 1:
            special_result = str(minutes) + ' ' + _('minute')

        else:
            special_result = str(minutes) + ' ' + _('minutes')

    elif days == 0 and hours == 0 and minutes == 0 and seconds != 0:
        if seconds == 1:
            special_result = str(seconds) + ' ' + _('second')

        else:
            special_result = str(seconds) + ' ' + _('seconds')

    elif days == 0 and hours == 0 and minutes == 0 and seconds == 0:
        special_result = str(0) + ' ' + _('seconds')

    if special_result:
        if negative:
            special_result = _('minus') + ' ' + special_result

        return special_result

    if days:
        fmt = "{d}d{h}h{m}m"

    elif hours:
        fmt = "{h}h{m}m"

    elif minutes:
        fmt = "{m}m"
        if seconds:
            fmt += "{s}s"

    else:
        fmt = "{s}s"

    if negative:
        fmt = '-' + fmt

    return fmt.format(d=days, h=hours, m=minutes, s=seconds)


def pretty_size(size):
    if size < 1024:  # less than 1kB
        size, unit = size, 'B'
    
    elif size < 1024 * 1024:  # less than 1MB
        size, unit = size / 1024.0, 'kB'
        
    elif size < 1024 * 1024 * 1024:  # less than 1GB
        size, unit = size / 1024.0 / 1024, 'MB'
    
    else:  # greater than or equal to 1GB
        size, unit = size / 1024.0 / 1024 / 1024, 'GB'
    
    return '%.1f %s' % (size, unit)


def pretty_http_error(response):
    if response.code == 401 or response.error == 'Authentication Error':
        return 'authentication failed'

    if not response.error:
        return 'ok'
    
    msg = unicode(response.error)
    if msg.startswith('HTTP '):
        msg = msg.split(':', 1)[-1].strip()

    if msg.startswith('[Errno '):
        msg = msg.split(']', 1)[-1].strip()
    
    if 'timeout' in msg.lower() or 'timed out' in msg.lower():
        msg = 'request timed out' 

    return msg


def make_str(s):
    if isinstance(s, str):
        return s

    try:
        return str(s)

    except:
        try:
            return unicode(s, encoding='utf8').encode('utf8')
    
        except:
            return unicode(s).encode('utf8')


def make_unicode(s):
    if isinstance(s, unicode):
        return s

    try:
        return unicode(s, encoding='utf8')
    
    except:
        try:
            return unicode(s)
        
        except:
            return str(s).decode('utf8')


def split_semicolon(s):
    parts = s.split(';')
    merged_parts = []
    for p in parts:
        if merged_parts and merged_parts[-1][-1] == '\\':
            merged_parts[-1] = merged_parts[-1][:-1] + ';' + p
            
        else:
            merged_parts.append(p)
    
    if not merged_parts:
        return []

    return [p.strip() for p in merged_parts]


def get_disk_usage(path):
    logging.debug('getting disk usage for path %(path)s...' % {
            'path': path})

    try:    
        result = os.statvfs(path)
    
    except OSError as e:
        logging.error('failed to execute statvfs: %(msg)s' % {'msg': unicode(e)})
        
        return None

    block_size = result.f_frsize
    free_blocks = result.f_bfree
    total_blocks = result.f_blocks
    
    free_size = free_blocks * block_size
    total_size = total_blocks * block_size
    used_size = total_size - free_size
    
    return used_size, total_size


def is_local_motion_camera(config):
    """Tells if a camera is managed by the local motion instance."""
    return bool(config.get('videodevice') or config.get('netcam_url') or config.get('mmalcam_name'))


def is_remote_camera(config):
    """Tells if a camera is managed by a remote motionEye server."""
    return config.get('@proto') == 'motioneye'


def is_v4l2_camera(config):
    """Tells if a camera is a v4l2 device managed by the local motion instance."""
    return bool(config.get('videodevice'))


def is_mmal_camera(config):
    '''Tells if a camera is mmal device managed by the local motion instance.'''
    return bool(config.get('mmalcam_name'))


def is_net_camera(config):
    """Tells if a camera is a network camera managed by the local motion instance."""
    return bool(config.get('netcam_url'))


def is_simple_mjpeg_camera(config):
    """Tells if a camera is a simple MJPEG camera not managed by any motion instance."""
    return bool(config.get('@proto') == 'mjpeg')


def test_mjpeg_url(data, auth_modes, allow_jpeg, callback):
    data = dict(data)
    data.setdefault('scheme', 'http')
    data.setdefault('host', '127.0.0.1')
    data.setdefault('port', '80')
    data.setdefault('path', '')
    data.setdefault('username', None)
    data.setdefault('password', None)

    url = '%(scheme)s://%(host)s%(port)s%(path)s' % {
            'scheme': data['scheme'],
            'host': data['host'],
            'port': ':' + str(data['port']) if data['port'] else '',
            'path': data['path'] or ''}
    
    called = [False]
    status_2xx = [False]
    http_11 = [False]

    def do_request(on_response):
        if data['username']:
            auth = auth_modes[0]
            
        else:
            auth = 'no'

        logging.debug('testing (m)jpg netcam at %s using %s authentication' % (url, auth))

        request = HTTPRequest(url, auth_username=username, auth_password=password, auth_mode=auth_modes.pop(0),
                              connect_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                              request_timeout=settings.REMOTE_REQUEST_TIMEOUT,
                              header_callback=on_header, validate_cert=settings.VALIDATE_CERTS)

        http_client = AsyncHTTPClient(force_instance=True)
        http_client.fetch(request, on_response)

    def on_header(header):
        header = header.lower()
        if header.startswith('content-type') and status_2xx[0]:
            content_type = header.split(':')[1].strip()
            called[0] = True

            if content_type in ['image/jpg', 'image/jpeg', 'image/pjpg'] and allow_jpeg:
                callback([{'id': 1, 'name': 'JPEG Network Camera', 'keep_alive': http_11[0]}])
            
            elif content_type.startswith('multipart/x-mixed-replace'):
                callback([{'id': 1, 'name': 'MJPEG Network Camera', 'keep_alive': http_11[0]}])
            
            else:
                callback(error='not a supported network camera')

        else:
            # check for the status header
            m = re.match('^http/1.(\d) (\d+) ', header)
            if m:
                if int(m.group(2)) / 100 == 2:
                    status_2xx[0] = True
                
                if m.group(1) == '1':
                    http_11[0] = True

    def on_response(response):
        if not called[0]:
            if response.code == 401 and auth_modes and data['username']:
                status_2xx[0] = False
                do_request(on_response)
                
            else:
                called[0] = True
                callback(error=pretty_http_error(response) if response.error else 'not a supported network camera')
    
    username = data['username'] or None
    password = data['password'] or None
    
    do_request(on_response)


def test_rtsp_url(data, callback):
    import motionctl
    
    scheme = data.get('scheme', 'rtsp')
    host = data.get('host', '127.0.0.1')
    port = data.get('port') or '554'
    path = data.get('path') or ''
    username = data.get('username')
    password = data.get('password')

    url = '%(scheme)s://%(host)s%(port)s%(path)s' % {
            'scheme': scheme,
            'host': host,
            'port': (':' + port) if port else '',
            'path': path}
    
    called = [False]
    send_auth = [False]
    timeout = [None]
    stream = None
    
    io_loop = IOLoop.instance()

    def connect():
        if send_auth[0]:
            logging.debug('testing rtsp netcam at %s (this time with credentials)' % url)
            
        else:
            logging.debug('testing rtsp netcam at %s' % url)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.settimeout(settings.MJPG_CLIENT_TIMEOUT)
        stream = IOStream(s)
        stream.set_close_callback(on_close)
        stream.connect((host, int(port)), on_connect)

        timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=settings.MJPG_CLIENT_TIMEOUT),
                                         functools.partial(on_connect, _timeout=True))
        
        return stream
    
    def on_connect(_timeout=False):
        io_loop.remove_timeout(timeout[0])
        
        if _timeout:
            return handle_error('timeout connecting to rtsp netcam')

        if not stream:
            return handle_error('failed to connect to rtsp netcam') 

        logging.debug('connected to rtsp netcam')
        
        lines = [
            'OPTIONS %s RTSP/1.0' % url.encode('utf8'),
            'CSeq: 1',
            'User-Agent: motionEye'
        ]
        
        if username and send_auth[0]:
            auth_header = 'Authorization: ' + build_basic_header(username, password)
            lines.append(auth_header)

        lines += [
            '',
            ''
        ]

        stream.write('\r\n'.join(lines))

        seek_rtsp()
        
    def seek_rtsp():
        if check_error():
            return

        stream.read_until_regex('RTSP/1.0 \d+ ', on_rtsp)
        timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=settings.MJPG_CLIENT_TIMEOUT), on_rtsp)

    def on_rtsp(data=None):
        io_loop.remove_timeout(timeout[0])

        if data:
            if data.endswith('200 '):
                seek_server()

            elif data.endswith('401 '):
                if not username or send_auth[0]:
                    # either credentials not supplied, or already sent
                    handle_error('authentication failed')

                else:
                    seek_www_authenticate()

            else:
                handle_error('rtsp netcam returned erroneous response: %s' % data)

        else:
            handle_error('timeout waiting for rtsp netcam response')

    def seek_server():
        if check_error():
            return

        stream.read_until_regex('Server: .*', on_server)
        timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=1), on_server)

    def on_server(data=None):
        io_loop.remove_timeout(timeout[0])

        if data:
            identifier = re.findall('Server: (.*)', data)[0].strip()
            logging.debug('rtsp netcam identifier is "%s"' % identifier)
        
        else:
            identifier = None
            logging.debug('no rtsp netcam identifier')

        handle_success(identifier)

    def seek_www_authenticate():
        if check_error():
            return

        stream.read_until_regex('WWW-Authenticate: .*', on_www_authenticate)
        timeout[0] = io_loop.add_timeout(datetime.timedelta(seconds=1), on_www_authenticate)

    def on_www_authenticate(data=None):
        io_loop.remove_timeout(timeout[0])

        if data:
            scheme = re.findall('WWW-Authenticate: ([^\s]+)', data)[0].strip()
            logging.debug('rtsp netcam auth scheme: %s' % scheme)
            if scheme.lower() == 'basic':
                send_auth[0] = True
                connect()
                
            else:
                logging.debug('rtsp auth scheme digest not supported, considering credentials ok')
                handle_success('(unknown) ')

        else:
            logging.error('timeout waiting for rtsp auth scheme')
            handle_error('timeout waiting for rtsp netcam response')

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
        rtsp_support = motionctl.get_rtsp_support()
        if identifier:
            identifier = ' ' + identifier
            
        else:
            identifier = ''

        if 'tcp' in rtsp_support:
            cameras.append({'id': 'tcp', 'name': '%sRTSP/TCP Camera' % identifier})

        if 'udp' in rtsp_support:
            cameras.append({'id': 'udp', 'name': '%sRTSP/UDP Camera' % identifier})
        
        callback(cameras)

    def handle_error(e):
        if called[0]:
            return
        
        called[0] = True
        logging.error('rtsp client error: %s' % unicode(e))

        try:
            stream.close()
        
        except:
            pass
        
        callback(error=unicode(e))

    def check_error():
        error = getattr(stream, 'error', None)
        if error and getattr(error, 'errno', None) != 0:
            handle_error(error.strerror)
            return True

        if stream and stream.socket is None:
            handle_error('connection closed')
            stream.close()

            return True
        
        return False

    stream = connect()


def compute_signature(method, path, body, key):
    parts = list(urlparse.urlsplit(path))
    query = [q for q in urlparse.parse_qsl(parts[3], keep_blank_values=True) if (q[0] != '_signature')]
    query.sort(key=lambda q: q[0])
    # "safe" characters here are set to match the encodeURIComponent JavaScript counterpart
    query = [(n, urllib.quote(v, safe="!'()*~")) for (n, v) in query]
    query = '&'.join([(q[0] + '=' + q[1]) for q in query])
    parts[0] = parts[1] = ''
    parts[3] = query
    path = urlparse.urlunsplit(parts)
    path = _SIGNATURE_REGEX.sub('-', path)
    key = _SIGNATURE_REGEX.sub('-', key)

    if body and body.startswith('---'):
        body = None  # file attachment

    body = body and _SIGNATURE_REGEX.sub('-', body.decode('utf8'))

    return hashlib.sha1('%s:%s:%s:%s' % (method, path, body or '', key)).hexdigest().lower()


def parse_cookies(cookies_headers):
    parsed = {}
    
    for cookie in cookies_headers:
        cookie = cookie.split(';')
        for c in cookie:
            (name, value) = c.split('=', 1)
            name = name.strip()
            value = value.strip()

            if name.lower() in _SPECIAL_COOKIE_NAMES:
                continue
            
            parsed[name] = value

    return parsed


def build_basic_header(username, password):
    return 'Basic ' + base64.encodestring('%s:%s' % (username, password)).replace('\n', '')


def parse_basic_header(header):
    parts = header.split(' ', 1)
    if len(parts) < 2:
        return None

    if parts[0].lower() != 'basic':
        return None

    encoded = parts[1]

    try:
        decoded = base64.decodestring(encoded)

    except:
        return None

    parts = decoded.split(':', 1)
    if len(parts) < 2:
        return None

    return {
        'username': parts[0],
        'password': parts[1]
    }


def build_digest_header(method, url, username, password, state):
    realm = state['realm']
    nonce = state['nonce']
    last_nonce = state.get('last_nonce', '')
    nonce_count = state.get('nonce_count', 0)
    qop = state.get('qop')
    algorithm = state.get('algorithm')
    opaque = state.get('opaque')

    if algorithm is None:
        _algorithm = 'MD5'

    else:
        _algorithm = algorithm.upper()

    if _algorithm == 'MD5' or _algorithm == 'MD5-SESS':
        def md5_utf8(x):
            if isinstance(x, str):
                x = x.encode('utf-8')
            return hashlib.md5(x).hexdigest()
        hash_utf8 = md5_utf8

    else:  # _algorithm == 'SHA'
        def sha_utf8(x):
            if isinstance(x, str):
                x = x.encode('utf-8')
            return hashlib.sha1(x).hexdigest()
        hash_utf8 = sha_utf8

    KD = lambda s, d: hash_utf8("%s:%s" % (s, d))

    if hash_utf8 is None:
        return None

    entdig = None
    p_parsed = urlparse.urlparse(url)
    path = p_parsed.path
    if p_parsed.query:
        path += '?' + p_parsed.query

    A1 = '%s:%s:%s' % (username, realm, password)
    A2 = '%s:%s' % (method, path)

    HA1 = hash_utf8(A1)
    HA2 = hash_utf8(A2)

    if nonce == last_nonce:
        nonce_count += 1

    else:
        nonce_count = 1
    
    ncvalue = '%08x' % nonce_count
    s = str(nonce_count).encode('utf-8')
    s += nonce.encode('utf-8')
    s += time.ctime().encode('utf-8')
    s += os.urandom(8)

    cnonce = (hashlib.sha1(s).hexdigest()[:16])
    if _algorithm == 'MD5-SESS':
        HA1 = hash_utf8('%s:%s:%s' % (HA1, nonce, cnonce))

    if qop is None:
        respdig = KD(HA1, "%s:%s" % (nonce, HA2))
    
    elif qop == 'auth' or 'auth' in qop.split(','):
        noncebit = "%s:%s:%s:%s:%s" % (
            nonce, ncvalue, cnonce, 'auth', HA2
            )
        respdig = KD(HA1, noncebit)
    
    else:
        return None

    last_nonce = nonce

    base = 'username="%s", realm="%s", nonce="%s", uri="%s", ' \
           'response="%s"' % (username, realm, nonce, path, respdig)
    if opaque:
        base += ', opaque="%s"' % opaque
    if algorithm:
        base += ', algorithm="%s"' % algorithm
    if entdig:
        base += ', digest="%s"' % entdig
    if qop:
        base += ', qop="auth", nc=%s, cnonce="%s"' % (ncvalue, cnonce)
    
    state['last_nonce'] = last_nonce
    state['nonce_count'] = nonce_count

    return 'Digest %s' % base


def urlopen(*args, **kwargs):
    if sys.version_info >= (2, 7, 9) and not settings.VALIDATE_CERTS:
        # ssl certs are not verified by default
        # in versions prior to 2.7.9

        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    
        kwargs.setdefault('context', ctx)

    return urllib2.urlopen(*args, **kwargs)


def build_editable_mask_file(camera_id, mask_lines, capture_width=None, capture_height=None):
    if not mask_lines:
        return ''
    
    width = mask_lines[0]
    height = mask_lines[1]
    mask_lines = mask_lines[2:]
    
    logging.debug('building editable mask for camera with id %s (%sx%s)' %
                  (camera_id, width, height))

    # horizontal rectangles
    nx = MASK_WIDTH  # number of rectangles
    if width % nx:
        nx -= 1
        rx = width % nx  # remainder

    else:
        rx = 0
    
    rw = width / nx  # rectangle width

    # vertical rectangles
    ny = mask_height = height * MASK_WIDTH / width  # number of rectangles
    if height % ny:
        ny -= 1
        ry = height % ny  # remainder
    
    else:
        ry = 0

    # if mask not present, generate an empty mask    
    if not mask_lines:
        mask_lines = [0] * mask_height

    # scale the mask vertically in case the aspect ratio has changed
    # since the last time the mask has been generated
    if ny == len(mask_lines):
        line_index_func = lambda y: y
        
    else:
        line_index_func = lambda y: (len(mask_lines) - 1) * y / ny

    rh = height / ny  # rectangle height

    # draw the actual mask image content
    im = Image.new('L', (width, height), 255)  # all white
    dr = ImageDraw.Draw(im)
    
    for y in xrange(ny):
        line = mask_lines[line_index_func(y)]
        for x in xrange(nx):
            if line & (1 << (MASK_WIDTH - 1 - x)):
                dr.rectangle((x * rw, y * rh, (x + 1) * rw - 1, (y + 1) * rh - 1), fill=0)

        if rx and line & 1:
            dr.rectangle((nx * rw, y * rh, nx * rw + rx - 1, (y + 1) * rh - 1), fill=0)

    if ry:
        line = mask_lines[line_index_func(ny)]
        for x in xrange(nx):
            if line & (1 << (MASK_WIDTH - 1 - x)):
                dr.rectangle((x * rw, ny * rh, (x + 1) * rw - 1, ny * rh + ry - 1), fill=0)

        if rx and line & 1:
            dr.rectangle((nx * rw, ny * rh, nx * rw + rx - 1, ny * rh + ry - 1), fill=0)

    file_name = os.path.join(settings.CONF_PATH, 'mask_%s.pgm' % camera_id)
    
    # resize the image if necessary
    if capture_width and capture_height and im.size != (capture_width, capture_height):
        logging.debug('editable mask needs resizing from %sx%s to %sx%s' %
                      (im.size[0], im.size[1], capture_width, capture_height))

        im = im.resize((capture_width, capture_height))

    im.save(file_name, 'ppm')

    return file_name


def parse_editable_mask_file(camera_id, capture_width=None, capture_height=None):
    # capture_width and capture_height arguments represent the current size
    # of the camera image, as it might be different from that of the associated mask;
    # they can be null (e.g. netcams)

    file_name = os.path.join(settings.CONF_PATH, 'mask_%s.pgm' % camera_id)

    logging.debug('parsing editable mask for camera with id %s: %s' % (camera_id, file_name))

    # read the image file
    try:
        im = Image.open(file_name)

    except Exception as e:
        logging.error('failed to read mask file %s: %s' % (file_name, e))

        # empty mask        
        return [0] * (MASK_WIDTH * 10)

    if capture_width and capture_height:
        # resize the image if necessary
        if im.size != (capture_width, capture_height):
            logging.debug('editable mask needs resizing from %sx%s to %sx%s' %
                          (im.size[0], im.size[1], capture_width, capture_height))

            im = im.resize((capture_width, capture_height))
            
        width, height = capture_width, capture_height

    else:
        logging.debug('using mask size from file: %sx%s' % (im.size[0], im.size[1]))

        width, height = im.size

    pixels = list(im.getdata())

    # horizontal rectangles
    nx = MASK_WIDTH  # number of rectangles
    if width % nx:
        nx -= 1
        rx = width % nx  # remainder

    else:
        rx = 0
    
    rw = width / nx  # rectangle width

    # vertical rectangles
    ny = height * MASK_WIDTH / width  # number of rectangles
    if height % ny:
        ny -= 1
        ry = height % ny  # remainder
    
    else:
        ry = 0

    rh = height / ny  # rectangle height

    # parse the image contents and build the mask lines
    mask_lines = [width, height]
    for y in xrange(ny):
        bits = []
        for x in xrange(nx):
            px = int((x + 0.5) * rw)
            py = int((y + 0.5) * rh)
            pixel = pixels[py * width + px]
            bits.append(not bool(pixel))

        if rx:
            px = int(nx * rw + rx / 2)
            py = int((y + 0.5) * rh)
            pixel = pixels[py * width + px]
            bits.append(not bool(pixel))

        # build the binary packed mask line
        line = 0
        for i, bit in enumerate(bits):
            if bit:
                line |= 1 << (MASK_WIDTH - 1 - i)
                
        mask_lines.append(line)

    if ry:
        bits = []
        for x in xrange(nx):
            px = int((x + 0.5) * rw)
            py = int(ny * rh + ry / 2)
            pixel = pixels[py * width + px]
            bits.append(not bool(pixel))

        if rx:
            px = int(nx * rw + rx / 2)
            py = int(ny * rh + ry / 2)
            pixel = pixels[py * width + px]
            bits.append(not bool(pixel))

        # build the binary packed mask line
        line = 0
        for i, bit in enumerate(bits):
            if bit:
                line |= 1 << (MASK_WIDTH - 1 - i)

        mask_lines.append(line)
    
    return mask_lines
