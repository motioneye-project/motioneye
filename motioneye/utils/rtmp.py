
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


__all__ = ('test_rtmp_url',)


def test_rtmp_url(data, callback):
    scheme = data.get('scheme', 'rtmp')
    host = data.get('host', '127.0.0.1')
    port = data.get('port') or '1935'
    path = data.get('path') or ''
    username = data.get('username')
    password = data.get('password')

    url = '%(scheme)s://%(host)s%(port)s%(path)s' % {
        'scheme': scheme,
        'host': host,
        'port': (':' + port) if port else '',
        'path': path}

    # Since RTMP is a binary TCP stream its a little more work to do a proper test
    # For now lets just check if a TCP socket is open on the target IP:PORT
    # TODO: Actually do the TCP SYN/ACK check...

    cameras = [{'id': 'tcp', 'name': 'RTMP/TCP Camera'}]
    callback(cameras)
