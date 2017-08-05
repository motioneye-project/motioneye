
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
import subprocess
import time
import urllib

import config


DEFAULT_INTERVAL = 1  # seconds

_monitor_info_cache_by_camera_id = {}
_last_call_time_by_camera_id = {}
_interval_by_camera_id = {}


def get_monitor_info(camera_id):
    now = time.time()
    command = config.get_monitor_command(camera_id)
    if command is None:
        return ''

    monitor_info = _monitor_info_cache_by_camera_id.get(camera_id)
    last_call_time = _last_call_time_by_camera_id.get(camera_id, 0)
    interval = _interval_by_camera_id.get(camera_id, DEFAULT_INTERVAL)
    if monitor_info is None or now - last_call_time > interval:
        monitor_info, interval = _exec_monitor_command(command)
        monitor_info = urllib.quote(monitor_info, safe='')
        _interval_by_camera_id[camera_id] = interval
        _monitor_info_cache_by_camera_id[camera_id] = monitor_info
        _last_call_time_by_camera_id[camera_id] = now

    return monitor_info 


def _exec_monitor_command(command):
    process = subprocess.Popen([command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()

    try:
        interval = int(err)
    
    except:
        interval = DEFAULT_INTERVAL
    
    out = out.strip()
    logging.debug('monitoring command "%s" returned "%s"' % (command, out))

    return out, interval
