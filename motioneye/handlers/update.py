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
from functools import cmp_to_key

from motioneye.handlers.base import BaseHandler
from motioneye.update import (
    compare_versions,
    get_all_versions,
    get_os_version,
    perform_update,
)

__all__ = ('UpdateHandler',)


class UpdateHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    def get(self):
        logging.debug('listing versions')

        versions = get_all_versions()
        current_version = get_os_version()[
            1
        ]  # os version is returned as (name, version) tuple
        recent_versions = [
            v for v in versions if compare_versions(v, current_version) > 0
        ]
        recent_versions.sort(key=cmp_to_key(compare_versions))
        update_version = recent_versions[-1] if recent_versions else None

        self.finish_json(
            {'update_version': update_version, 'current_version': current_version}
        )

    @BaseHandler.auth(admin=True)
    def post(self):
        version = self.get_argument('version')

        logging.debug(f'performing update to version {version}')

        result = perform_update(version)

        self.finish_json(result)
