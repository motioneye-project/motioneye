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
from os.path import exists, join
from typing import ClassVar

from tornado.web import HTTPError

from motioneye.handlers.base import BaseHandler
from motioneye.settings import LOG_PATH, LOG_TO_FILE
from motioneye.utils import call_subprocess

__all__ = ('LogHandler',)


class LogHandler(BaseHandler):
    LOGS: ClassVar[dict[str, tuple[str, str]]] = {
        'motion': (join(LOG_PATH, 'motion.log'), 'motion.log'),
    }

    @BaseHandler.auth(admin=True)
    def get(self, name: str) -> None:
        log: tuple[str, str] | None = self.LOGS.get(name)
        if log is None:
            raise HTTPError(404, f'log file name "{name}" is undefined')

        path, filename = log
        if path.startswith('/') and not exists(path):
            if LOG_TO_FILE:
                raise HTTPError(404, f'{name} log path "{path}" not found')

            raise HTTPError(404, 'file logging is disabled on this motionEye server')

        self.set_header('Content-Type', 'text/plain')
        self.set_header('Content-Disposition', f'attachment; filename={filename};')

        if path.startswith('/'):  # an actual path
            logging.debug(f'serving log file "{filename}" from "{path}"')

            with open(path) as f:
                self.finish(f.read())

        else:  # a command to execute
            logging.debug(f'serving log file "{filename}" from command "{path}"')

            try:
                output = call_subprocess(path.split())

            except Exception as e:
                output = f'failed to execute command: {e}'

            self.finish(output)
