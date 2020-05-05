
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

from tornado.ioloop import IOLoop

from motioneye.controls.powerctl import PowerControl
from motioneye.handlers.base import BaseHandler


__all__ = ('PowerHandler',)


class PowerHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def post(self, op):
        if op == 'shutdown':
            self.shut_down()

        elif op == 'reboot':
            self.reboot()

    def shut_down(self):
        io_loop = IOLoop.instance()
        io_loop.add_timeout(datetime.timedelta(seconds=2), PowerControl.shut_down)

    def reboot(self):
        io_loop = IOLoop.instance()
        io_loop.add_timeout(datetime.timedelta(seconds=2), PowerControl.reboot)
