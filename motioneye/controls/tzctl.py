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
import os
from hashlib import md5

from motioneye.config import additional_config
from motioneye.settings import LOCAL_TIME_FILE


def get_time_zone() -> str | None:
    return _get_time_zone_symlink() or _get_time_zone_md5() or 'UTC'


def _get_time_zone_symlink() -> str | None:
    if not LOCAL_TIME_FILE:
        return None

    f: str = os.path.realpath(LOCAL_TIME_FILE)
    if not f.startswith('/usr/share/zoneinfo/'):
        return None

    time_zone: str = f[20:]
    logging.debug(f'found time zone by symlink method: {time_zone}')
    return time_zone


def _get_time_zone_md5() -> str | None:
    if not LOCAL_TIME_FILE:
        return None

    try:
        with open(LOCAL_TIME_FILE, 'rb') as f:
            local_md5: str = md5(f.read()).hexdigest()  # nosec: B324

    except Exception as e:
        logging.error(f'failed to read local time file: {e}')
        return None

    zoneinfo_dir: str = '/usr/share/zoneinfo'
    try:
        for root, dirs, files in os.walk(zoneinfo_dir):
            # Match "find *": exclude hidden entries at the top level.
            if root == zoneinfo_dir:
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files = [f for f in files if not f.startswith('.')]

            for name in files:
                path = os.path.join(root, name)

                # Match "find -type f": exclude symlinks.
                if os.path.islink(path) or not os.path.isfile(path):
                    continue

                with open(path, 'rb') as f:
                    if md5(f.read()).hexdigest() == local_md5:  # nosec: B324
                        time_zone = os.path.relpath(path, zoneinfo_dir)
                        logging.debug(f'found time zone by md5 method: {time_zone}')
                        return time_zone

    except Exception as e:
        logging.error(f'getting md5 of zoneinfo files failed: {e}')
        return None

    return None


def _set_time_zone(time_zone: str | None) -> bool:
    if not LOCAL_TIME_FILE:
        return False

    time_zone = time_zone or 'UTC'

    zoneinfo_file: str = '/usr/share/zoneinfo/' + time_zone
    if not os.path.exists(zoneinfo_file):
        logging.error(f'{zoneinfo_file} file does not exist')
        return False

    logging.debug(f'linking "{LOCAL_TIME_FILE}" to "{zoneinfo_file}"')

    try:
        os.remove(LOCAL_TIME_FILE)

    except FileNotFoundError:
        pass  # nevermind

    except OSError as e:
        logging.error(
            f'failed to remove "{LOCAL_TIME_FILE}" before creating symlink: {e}'
        )
        return False

    try:
        os.symlink(zoneinfo_file, LOCAL_TIME_FILE)
        return True

    except Exception as e:
        logging.error(f'failed to link "{LOCAL_TIME_FILE}" to "{zoneinfo_file}": {e}')
        return False


@additional_config
def timeZone() -> dict | None:
    if not LOCAL_TIME_FILE:
        return None

    import pytz

    timezones = pytz.common_timezones

    return {
        'label': 'Time Zone',
        'description': 'selecting the right timezone assures a correct timestamp displayed on pictures and movies',
        'type': 'choices',
        'choices': [(t, t) for t in timezones],
        'section': 'general',
        'reboot': True,
        'get': get_time_zone,
        'set': _set_time_zone,
    }
