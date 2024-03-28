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
import os

from tornado.web import HTTPError

from motioneye import settings, utils
from motioneye.handlers.base import BaseHandler

__all__ = ('LogHandler',)


class LogHandler(BaseHandler):
    LOGS = {
        'motion': (os.path.join(settings.LOG_PATH, 'motion.log'), 'motion.log'),
    }

    @BaseHandler.auth(admin=True)
    def get(self, name):
        log = self.LOGS.get(name)
        if log is None:
            raise HTTPError(404, 'no such log')

        (path, filename) = log

        self.set_header('Content-Type', 'text/plain')
        self.set_header('Content-Disposition', 'attachment; filename=' + filename + ';')

        if path.startswith('/'):  # an actual path
            logging.debug(f'serving log file "{filename}" from "{path}"')

            with open(path) as f:
                self.finish(f.read())

        else:  # a command to execute
            logging.debug(f'serving log file "{filename}" from command "{path}"')

            try:
                output = utils.call_subprocess(path.split())

            except Exception as e:
                output = 'failed to execute command: %s' % e

            self.finish(output)
