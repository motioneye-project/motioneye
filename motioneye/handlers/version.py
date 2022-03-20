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

import socket

from motioneye.handlers.base import BaseHandler
from motioneye.motionctl import find_motion
from motioneye.update import get_os_version

__all__ = ('VersionHandler',)


class VersionHandler(BaseHandler):
    def get(self):
        motion_info = find_motion()
        os_version = get_os_version()

        self.render(
            'version.html',
            os_version=' '.join(os_version),
            motion_version=motion_info[1] if motion_info else '',
            hostname=socket.gethostname(),
        )

    post = get
