
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
import functools
import logging

from tornado.ioloop import IOLoop

import config
import motionctl
import utils


def start():
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=1), _check_ws)


def _during_working_schedule(now, working_schedule):
    parts = working_schedule.split('|')
    if len(parts) < 7:
        return False # invalid ws

    ws_day = parts[now.weekday()]
    parts = ws_day.split('-')
    if len(parts) != 2:
        return False # invalid ws
    
    _from, to = parts
    if not _from or not to:
        return False # ws disabled for this day
    
    _from = _from.split(':')
    to = to.split(':')
    if len(_from) != 2 or len(to) != 2:
        return False # invalid ws
    
    try:
        from_h = int(_from[0])
        from_m = int(_from[1])
        to_h = int(to[0])
        to_m = int(to[1])
    
    except ValueError:
        return False # invalid ws
    
    if now.hour < from_h or now.hour > to_h:
        return False

    if now.hour == from_h and now.minute < from_m:
        return False

    if now.hour == to_h and now.minute > to_m:
        return False
    
    return True


def _check_ws():
    # schedule the next call
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=10), _check_ws)

    if not motionctl.running():
        return
    
    def on_motion_detection_status(camera_id, must_be_enabled, working_schedule_type, enabled=None, error=None):
        if error: # could not detect current status
            return logging.warn('skipping motion detection status update for camera with id %(id)s' % {'id': camera_id})
            
        if enabled and not must_be_enabled:
            logging.debug('must disable motion detection for camera with id %(id)s (%(what)s working schedule)' % {
                    'id': camera_id,
                    'what': working_schedule_type})
            
            motionctl.set_motion_detection(camera_id, False)

        elif not enabled and must_be_enabled:
            logging.debug('must enable motion detection for camera with id %(id)s (%(what)s working schedule)' % {
                    'id': camera_id,
                    'what': working_schedule_type})
            
            motionctl.set_motion_detection(camera_id, True)
    
    now = datetime.datetime.now()
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if not utils.local_motion_camera(camera_config):
            continue
        
        working_schedule = camera_config.get('@working_schedule')
        motion_detection = camera_config.get('@motion_detection')
        working_schedule_type = camera_config.get('@working_schedule_type') or 'outside'
        
        if not working_schedule: # working schedule disabled, motion detection left untouched
            continue
        
        if not motion_detection: # motion detection explicitly disabled
            continue
        
        now_during = _during_working_schedule(now, working_schedule)
        must_be_enabled = (now_during and working_schedule_type == 'during') or (not now_during and working_schedule_type == 'outside')
        
        motionctl.get_motion_detection(camera_id, functools.partial(
                on_motion_detection_status, camera_id, must_be_enabled, working_schedule_type))
