
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

import utils


def list_devices():
    # currently MMAL support is designed specifically for the RPi;
    # therefore we can rely on the vcgencmd to report MMAL cameras

    logging.debug('listing MMAL devices')

    try:
        binary = subprocess.check_output(['which', 'vcgencmd'], stderr=utils.DEV_NULL).strip()

    except subprocess.CalledProcessError:  # not found
        return []

    try:
        support = subprocess.check_output([binary, 'get_camera']).strip()

    except subprocess.CalledProcessError:  # not found
        return []

    d = dict(p.split('=', 1) for p in support.split())
    if d.get('detected') == d.get('supported') == '1':
        logging.debug('MMAL camera detected')
        return [('vc.ril.camera', 'VideoCore Camera')]

    return []
