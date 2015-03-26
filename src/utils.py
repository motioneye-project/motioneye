
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
import hashlib
import logging
import os
import re
import time
import urllib
import urlparse

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

import settings


try:
    from collections import OrderedDict  # @UnusedImport

except:
    from ordereddict import OrderedDict  # @UnusedImport @Reimport


def pretty_date_time(date_time, tzinfo=None, short=False):
    if date_time is None:
        return '('+  _('never') + ')'

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
        return '('+  _('never') + ')'

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
        format = "{d}d{h}h{m}m"

    elif hours:
        format = "{h}h{m}m"

    elif minutes:
        format = "{m}m"
        if seconds:
            format += "{s}s"

    else:
        format = "{s}s"

    if negative:
        format = '-' + format

    return format.format(d=days, h=hours, m=minutes, s=seconds)


def pretty_size(size):
    if size < 1024: # less than 1kB
        size, unit = size, 'B'
    
    elif size < 1024 * 1024: # less than 1MB
        size, unit = size / 1024.0, 'kB'
        
    elif size < 1024 * 1024 * 1024: # less than 1GB
        size, unit = size / 1024.0 / 1024, 'MB'
    
    else: # greater than or equal to 1GB
        size, unit = size / 1024.0 / 1024 / 1024, 'GB'
    
    return '%.1f %s' % (size, unit)


def pretty_http_error(http_error):
    msg = unicode(http_error)
    if msg.startswith('HTTP '):
        msg = msg.split(':', 1)[-1].strip()

    if msg.startswith('[Errno '):
        msg = msg.split(']', 1)[-1].strip()

    return msg


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
    
    return (used_size, total_size)


def local_camera(config):
    return bool(config.get('videodevice') or config.get('netcam_url'))


def remote_camera(config):
    return config.get('@proto') == 'motioneye'


def v4l2_camera(config):
    return bool(config.get('videodevice'))


def net_camera(config):
    return bool(config.get('netcam_url'))


def test_netcam_url(data, callback):
    data = dict(data)
    data.setdefault('proto', 'http')
    data.setdefault('host', '127.0.0.1')
    data.setdefault('port', '80')
    data.setdefault('uri', '')
    data.setdefault('username', None)
    data.setdefault('password', None)

    url = '%(proto)s://%(host)s%(port)s%(uri)s' % {
            'proto': data['proto'],
            'host': data['host'],
            'port': ':' + str(data['port']) if data['port'] else '',
            'uri': data['uri'] or ''}
    
    logging.debug('testing netcam at %s' % url)
    
    http_client = AsyncHTTPClient()
    
    called = [False]
    not_2xx = [False]
    
    def on_header(header):
        if not_2xx[0]:
            return # ignore headers unless the status is 2xx

        header = header.lower()
        if header.startswith('content-type'):
            content_type = header.split(':')[1].strip()
            if content_type in ['image/jpg', 'image/jpeg', 'image/pjpg']:
                callback([{'id': 1, 'name': 'JPEG Network Camera'}])
            
            elif content_type.startswith('multipart/x-mixed-replace'):
                callback([{'id': 1, 'name': 'MJPEG Network Camera'}])
            
            else:
                callback(error='not a network camera')
            
            called[0] = True

        else:
            m = re.match('^http/1.\d (\d+) ', header)
            if m and int(m.group(1)) / 100 != 2:
                not_2xx[0] = True

    def on_response(response):
        if not called[0]:
            called[0] = True
            callback(error=pretty_http_error(response.error) if response.error else 'not a network camera')
    
    username = data['username'] or None
    password = data['password'] or None
    
    request = HTTPRequest(url, auth_username=username, auth_password=password,
            connect_timeout=settings.REMOTE_REQUEST_TIMEOUT, request_timeout=settings.REMOTE_REQUEST_TIMEOUT,
            header_callback=on_header)
    
    http_client.fetch(request, on_response)


def compute_signature(method, uri, body, key):
    parts = list(urlparse.urlsplit(uri))
    query = [q for q in urlparse.parse_qsl(parts[3], keep_blank_values=True) if (q[0] != '_signature')]
    query.sort(key=lambda q: q[0])
    # "safe" characters here are set to match the encodeURIComponent JavaScript counterpart
    query = [(n, urllib.quote(v, safe="!'()*~")) for (n, v) in query]
    query = '&'.join([(q[0] + '=' + q[1]) for q in query])
    parts[0] = parts[1] = ''
    parts[3] = query
    uri = urlparse.urlunsplit(parts)
    
    if body and body.startswith('---'):
        body = None # file attachment

    return hashlib.sha1('%s:%s:%s:%s' % (method, uri, body or '', key)).hexdigest().lower()


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

    elif _algorithm == 'SHA':
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

    return 'Digest %s' % (base)
