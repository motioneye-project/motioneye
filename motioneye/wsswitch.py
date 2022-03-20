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
import logging

from tornado.ioloop import IOLoop

from motioneye import config, motionctl, utils


def _start_check_ws() -> None:
    IOLoop.current().spawn_callback(_check_ws)


def start() -> None:
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=1), _start_check_ws)


def _during_working_schedule(now, working_schedule) -> bool:
    parts = working_schedule.split('|')
    if len(parts) < 7:
        return False  # invalid ws

    ws_day = parts[now.weekday()]
    parts = ws_day.split('-')
    if len(parts) != 2:
        return False  # invalid ws

    _from, to = parts
    if not _from or not to:
        return False  # ws disabled for this day

    _from = _from.split(':')
    to = to.split(':')
    if len(_from) != 2 or len(to) != 2:
        return False  # invalid ws

    try:
        from_h = int(_from[0])
        from_m = int(_from[1])
        to_h = int(to[0])
        to_m = int(to[1])

    except ValueError:
        return False  # invalid ws

    if now.hour < from_h or now.hour > to_h:
        return False

    if now.hour == from_h and now.minute < from_m:
        return False

    if now.hour == to_h and now.minute > to_m:
        return False

    return True


async def _switch_motion_detection_status(
    camera_id,
    must_be_enabled,
    working_schedule_type,
    motion_detection_resp: utils.GetMotionDetectionResult,
) -> None:
    if motion_detection_resp.error:  # could not detect current status
        return logging.warning(
            'skipping motion detection status update for camera with id {id}: {error}'.format(
                id=camera_id, error=motion_detection_resp.error
            )
        )

    if motion_detection_resp.enabled and not must_be_enabled:
        logging.debug(
            'must disable motion detection for camera with id {id} ({what} working schedule)'.format(
                id=camera_id, what=working_schedule_type
            )
        )

        await motionctl.set_motion_detection(camera_id, False)

    elif not motion_detection_resp.enabled and must_be_enabled:
        logging.debug(
            'must enable motion detection for camera with id {id} ({what} working schedule)'.format(
                id=camera_id, what=working_schedule_type
            )
        )

        await motionctl.set_motion_detection(camera_id, True)


async def _check_ws() -> None:
    # schedule the next call
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=10), _start_check_ws)

    if not motionctl.running():
        return

    now = datetime.datetime.now()
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            continue

        working_schedule = camera_config.get('@working_schedule')
        motion_detection = camera_config.get('@motion_detection')
        working_schedule_type = camera_config.get('@working_schedule_type') or 'outside'

        if (
            not working_schedule
        ):  # working schedule disabled, motion detection left untouched
            continue

        if not motion_detection:  # motion detection explicitly disabled
            continue

        now_during = _during_working_schedule(now, working_schedule)
        must_be_enabled = (now_during and working_schedule_type == 'during') or (
            not now_during and working_schedule_type == 'outside'
        )

        motion_detection_resp = await motionctl.get_motion_detection(camera_id)
        await _switch_motion_detection_status(
            camera_id, must_be_enabled, working_schedule_type, motion_detection_resp
        )
