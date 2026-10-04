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
import re
from shlex import split
from shutil import disk_usage
from typing import Optional

from motioneye import config, settings

_EVENT = ['%t', config.MOMENT]  # how older versions ended these, before the time span


def migrate_cameras() -> None:
    # camera configs of older versions, restored ones included; never raises
    try:
        camera_ids = config.get_camera_ids()

    except Exception:  # logged by get_camera_ids()
        return

    for camera_id in camera_ids:
        try:
            camera_config = dict(config.get_camera(camera_id))
            if not _move_notification_settings(camera_id, camera_config):
                continue

            if disk_usage(settings.CONF_PATH).free < 2**20:  # set_camera() truncates
                raise OSError('less than 1 MiB free')

            logging.info(f'moving notification settings of camera {camera_id}')
            config.set_camera(camera_id, camera_config)

        except Exception as e:
            config.invalidate()  # the cache must match the files
            logging.error(f'failed to migrate camera {camera_id}: {e}')


def _move_notification_settings(camera_id: int, camera_config: dict) -> bool:
    # sendmail and sendtelegram got all their settings as arguments
    line = camera_config.get('on_event_start') or ''
    parts = re.split(r'(?<!\\);', line)
    short = [p for p in parts if p.strip().endswith(config._SHORT)]  # from the UI
    moved = [name for name in _OLD_SENDERS if any(f' {name} ' in p for p in short)]
    unreadable = False
    for i, part in enumerate(parts):
        name = next((name for name in _OLD_SENDERS if f' {name} ' in part), None)
        if not name:
            continue

        try:
            e = split(part)

        except ValueError:  # e.g. unbalanced quotes, kept as it is
            unreadable = unreadable or 'meyectl' in part  # one of ours
            continue

        values = _OLD_SENDERS[name](e) if e[-3:-1] == _EVENT else None
        if not values:
            continue

        if name in moved:  # e.g. a second bot or one from the UI, kept as it is
            logging.warning(f'could not move {name} settings of camera {camera_id}')
            continue

        # a '# @key value' line cannot keep them
        for key in [k for k, v in values.items() if str(v) != str(v).strip()]:
            logging.warning(f'removed spaces around {key[1:]} of camera {camera_id}')

        command = config.notification_command(camera_config, name, values)
        parts[i] = part.replace(part.strip(), command, 1)  # as a save in the UI does
        moved.append(name)

    if unreadable:
        logging.warning(f'could not read a command of camera {camera_id}')

    if ';'.join(parts) == line:
        return False

    camera_config['on_event_start'] = ';'.join(parts)  # other parts keep their text
    return True


def _old_sendmail(e: list) -> Optional[dict]:
    # moved from motion_camera_dict_to_ui()
    if len(e) < 11:
        return None

    if e[-6].lower() in ('true', 'false'):  # older configs lacking "from" field
        e.insert(-5, '')

    keys = config.SENDMAIL_KEYS
    return {
        keys['server']: e[-11],
        keys['port']: e[-10],
        keys['account']: e[-9],
        keys['password']: e[-8].replace('\\;', ';').replace('%%', '%'),
        keys['tls']: e[-7].lower() == 'true',
        keys['from']: e[-6],
        keys['to']: e[-5],
        keys['timespan']: _time_span(e[-1]),
    }


def _old_sendtelegram(e: list) -> Optional[dict]:
    # moved from motion_camera_dict_to_ui()
    if len(e) < 6:
        return None

    keys = config.SENDTELEGRAM_KEYS
    return {
        keys['api']: e[-5],
        keys['chatid']: e[-4],
        keys['timespan']: _time_span(e[-1]),
    }


def _time_span(value: str) -> int:
    try:
        return int(value)

    except (TypeError, ValueError):
        return 0


_OLD_SENDERS = {'sendmail': _old_sendmail, 'sendtelegram': _old_sendtelegram}
