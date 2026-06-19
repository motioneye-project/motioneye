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

import json
import logging
from typing import Dict, Union

from motioneye import prefs
from motioneye.handlers.base import BaseHandler

__all__ = ('PrefsHandler',)


class PrefsHandler(BaseHandler):
    @BaseHandler.auth()
    def get(self, key: Union[str, None] = None) -> None:
        self.finish_json(prefs.get(self.current_user, key))

    @BaseHandler.auth()
    def post(self, key: Union[str, None] = None) -> None:
        try:
            PrefsValue = Union[int, float, bool]
            value: Union[Dict[str, PrefsValue], PrefsValue] = json.loads(
                self.request.body
            )

        except Exception as e:
            logging.error(f'could not decode json: {e}')

            raise

        prefs.set(self.current_user, value, key)
