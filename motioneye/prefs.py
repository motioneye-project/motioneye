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
import os.path
from typing import Dict, Union, cast

from motioneye import settings

PrefsValue = Union[int, float, bool]
PrefsDict = Dict[str, PrefsValue]

_PREFS_FILE_NAME: str = 'prefs.json'
_DEFAULT_PREFS: PrefsDict = {
    'layout_columns': 3,
    'fit_frames_vertically': True,
    'layout_rows': 1,
    'framerate_factor': 1,
    'resolution_factor': 1,
}

_prefs: Dict[str, PrefsDict] = {}


def _load() -> None:
    global _prefs

    file_path: str = os.path.join(settings.CONF_PATH, _PREFS_FILE_NAME)

    if os.path.exists(file_path):
        logging.debug(f'loading preferences from "{file_path}"...')

        try:
            f = open(file_path)

        except Exception as e:
            logging.error(f'could not open preferences file "{file_path}": {e}')

            return

        try:
            _prefs = json.load(f)

        except Exception as e:
            logging.error(f'could not read preferences from file "{file_path}": {e}')

        finally:
            f.close()

    else:
        logging.debug(
            f'preferences file "{file_path}" does not exist, using default preferences'
        )


def _save() -> None:
    file_path: str = os.path.join(settings.CONF_PATH, _PREFS_FILE_NAME)

    logging.debug(f'saving preferences to "{file_path}"...')

    try:
        f = open(file_path, 'w')

    except Exception as e:
        logging.error(f'could not open preferences file "{file_path}": {e}')

        return

    try:
        json.dump(_prefs, f, sort_keys=True, indent=4)

    except Exception as e:
        logging.error(f'could not save preferences to file "{file_path}": {e}')

    finally:
        f.close()


def get(
    username: str, key: Union[str, None] = None
) -> Union[PrefsDict, PrefsValue, None]:
    if not _prefs:
        _load()

    if key:
        return _prefs.get(username, {}).get(key, _DEFAULT_PREFS.get(key))

    else:
        return {**_DEFAULT_PREFS, **_prefs.get(username, {})}


def set(
    username: str, value: Union[PrefsDict, PrefsValue], key: Union[str, None] = None
) -> None:
    if not _prefs:
        _load()

    if key:
        _prefs.setdefault(username, {})[key] = cast(PrefsValue, value)

    else:
        _prefs[username] = cast(PrefsDict, value)

    _save()
