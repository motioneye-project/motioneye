
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

from motioneye.utils import GetCamerasResponse
from motioneye.utils.http import RtmpUrl


__all__ = ('test_rtmp_url',)


def test_rtmp_url(data: dict) -> GetCamerasResponse:
    url_obj = RtmpUrl.from_dict(data)

    # Since RTMP is a binary TCP stream its a little more work to do a proper test
    # For now lets just check if a TCP socket is open on the target IP:PORT
    # TODO: Actually do the TCP SYN/ACK check...

    cameras = [{'id': 'tcp', 'name': 'RTMP/TCP Camera'}]
    return GetCamerasResponse(cameras, None)
