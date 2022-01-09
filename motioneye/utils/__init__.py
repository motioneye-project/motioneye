
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

import base64
import hashlib
import logging
import os
import re
import subprocess
import sys
import time
import typing
import urllib.request
import urllib.error
import urllib.parse
import numpy

from dataclasses import dataclass
from collections import namedtuple
from PIL import Image, ImageDraw
from tornado.ioloop import IOLoop
from tornado.concurrent import Future

from motioneye import settings


_SIGNATURE_REGEX = re.compile(r'[^a-zA-Z0-9/?_.=&{}\[\]":, -]')
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

GetCamerasResponse = namedtuple('GetCamerasResponse', ('cameras', 'error'))
GetConfigResponse = namedtuple('GetConfigResponse', ('remote_ui_config', 'error'))
GetMotionDetectionResult = namedtuple('GetMotionDetectionResult', ('enabled', 'error'))


@dataclass
class GetCurrentPictureResponse:
    motion_detected: bool = False
    capture_fps: typing.Any = None
    monitor_info: typing.Any = None
    picture: typing.Any = None
    error: typing.Any = None


@dataclass
class ListMediaResponse:
    media_list: list = None
    error: str = None


@dataclass
class CommonExternalResponse:
    result: typing.Any = None
    error: typing.Any = None


def cast_future(obj: typing.Awaitable[typing.Any]) -> Future:
    return typing.cast(Future, obj)


def spawn_callback_timeout_wrapper(callback: typing.Callable, *args: typing.Any, **kwargs: typing.Any) -> None:
    IOLoop.current().spawn_callback(callback, *args, **kwargs)


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

    msg = str(response.error)
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
            return str(s, encoding='utf8').encode('utf8')

        except:
            return str(s).encode('utf8')


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
        logging.error('failed to execute statvfs: %(msg)s' % {'msg': str(e)})

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
    """Tells if a camera is mmal device managed by the local motion instance."""
    return bool(config.get('mmalcam_name'))


def is_net_camera(config):
    """Tells if a camera is a network camera managed by the local motion instance."""
    return bool(config.get('netcam_url'))


def is_simple_mjpeg_camera(config):
    """Tells if a camera is a simple MJPEG camera not managed by any motion instance."""
    return bool(config.get('@proto') == 'mjpeg')


def compute_signature(method, path, body: bytes, key):
    parts = list(urllib.parse.urlsplit(path))
    query = [q for q in urllib.parse.parse_qsl(parts[3], keep_blank_values=True) if (q[0] != '_signature')]
    query.sort(key=lambda q: q[0])
    # "safe" characters here are set to match the encodeURIComponent JavaScript counterpart
    query = [(n, urllib.parse.quote(v, safe="!'()*~")) for (n, v) in query]
    query = '&'.join([(q[0] + '=' + q[1]) for q in query])
    parts[0] = parts[1] = ''
    parts[3] = query
    path = urllib.parse.urlunsplit(parts)
    path = _SIGNATURE_REGEX.sub('-', path)
    key = _SIGNATURE_REGEX.sub('-', key)

    body_str = body.decode('utf-8')
    if body_str and body_str.startswith('---'):
        body_str = None  # file attachment

    body_str = body_str and _SIGNATURE_REGEX.sub('-', body_str)

    return hashlib.sha1(('%s:%s:%s:%s' % (method, path, body_str or '', key)).encode('utf-8')).hexdigest().lower()


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
    return 'Basic ' + base64.encodebytes('%s:%s' % (username, password)).replace('\n', '')


def parse_basic_header(header):
    parts = header.split(' ', 1)
    if len(parts) < 2:
        return None

    if parts[0].lower() != 'basic':
        return None

    encoded = parts[1]

    try:
        decoded = base64.decodebytes(encoded)

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
    p_parsed = urllib.parse.urlparse(url)
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
        noncebit = "%s:%s:%s:%s:%s" % (nonce, ncvalue, cnonce, 'auth', HA2)
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
        base += ', qop=auth, nc=%s, cnonce="%s"' % (ncvalue, cnonce)

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

    return urllib.request.urlopen(*args, **kwargs)


def build_editable_mask_file(camera_id, mask_class, mask_lines, capture_width=None, capture_height=None):
    if not mask_lines:
        return ''

    width = mask_lines[0]
    height = mask_lines[1]
    mask_lines = mask_lines[2:]

    logging.debug('building editable %s mask for camera with id %s (%sx%s)' %
                  (mask_class, camera_id, width, height))

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

    for y in numpy.arange(ny):
        line = mask_lines[int(line_index_func(y))]
        for x in numpy.arange(nx):
            if line & (1 << (MASK_WIDTH - 1 - x)):
                dr.rectangle((x * rw, y * rh, (x + 1) * rw - 1, (y + 1) * rh - 1), fill=0)

        if rx and line & 1:
            dr.rectangle((nx * rw, y * rh, nx * rw + rx - 1, (y + 1) * rh - 1), fill=0)

    if ry:
        line = mask_lines[int(line_index_func(ny))]
        for x in numpy.arange(nx):
            if line & (1 << (MASK_WIDTH - 1 - x)):
                dr.rectangle((x * rw, ny * rh, (x + 1) * rw - 1, ny * rh + ry - 1), fill=0)

        if rx and line & 1:
            dr.rectangle((nx * rw, ny * rh, nx * rw + rx - 1, ny * rh + ry - 1), fill=0)

#    file_name = os.path.join(settings.CONF_PATH, 'mask_%s.pgm' % camera_id)
    file_name = build_mask_file_name(camera_id, mask_class)

    # resize the image if necessary
    if capture_width and capture_height and im.size != (capture_width, capture_height):
        logging.debug('editable mask needs resizing from %sx%s to %sx%s' %
                      (im.size[0], im.size[1], capture_width, capture_height))

        im = im.resize((capture_width, capture_height))

    im.save(file_name, 'ppm')

    return file_name

def build_mask_file_name(camera_id, mask_class):
    file_name = 'mask_%s.pgm' % (camera_id) if mask_class == 'motion' else 'mask_%s_%s.pgm' % (camera_id, mask_class)
    full_path = os.path.join(settings.CONF_PATH, file_name)

    return full_path

def parse_editable_mask_file(camera_id, mask_class, capture_width=None, capture_height=None):
    # capture_width and capture_height arguments represent the current size
    # of the camera image, as it might be different from that of the associated mask;
    # they can be null (e.g. netcams)

    file_name = os.path.join(settings.CONF_PATH, 'mask_%s.pgm' % camera_id)

    logging.debug('parsing editable mask %s for camera with id %s: %s' % (mask_class, camera_id, file_name))

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
    for y in numpy.arange(ny):
        bits = []
        for x in numpy.arange(nx):
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
        for x in numpy.arange(nx):
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


def call_subprocess(args, stdin=None, input=None, stdout=subprocess.PIPE, stderr=DEV_NULL, capture_output=False,
                    shell=False, cwd=None, timeout=None, check=True, encoding='utf-8', errors=None,
                    text=None, env=None, universal_newlines=None) -> str:
    """subprocess.run wrapper to return output as a decoded string"""
    return subprocess.run(
        args, stdin=stdin, input=input, stdout=stdout, stderr=stderr, capture_output=capture_output, shell=shell,
        cwd=cwd, timeout=timeout, check=check, encoding=encoding, errors=errors, text=text, env=env,
        universal_newlines=universal_newlines
    ).stdout.strip()
