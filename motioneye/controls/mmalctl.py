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

from logging import debug
from subprocess import CalledProcessError

from motioneye import utils


def list_devices():
    # currently MMAL support is designed specifically for the RPi;
    # therefore we can rely on the vcgencmd to report MMAL cameras

    debug('detecting MMAL camera')

    try:
        binary = utils.call_subprocess(['which', 'vcgencmd'])

    except CalledProcessError:  # not found
        debug('unable to detect MMAL camera: vcgencmd has not been found')
        return []

    try:
        support = utils.call_subprocess([binary, 'get_camera'])

    except CalledProcessError:  # not found
        debug('unable to detect MMAL camera: "vcgencmd get_camera" failed')
        return []

    if support.startswith('supported=1 detected=1'):
        debug('MMAL camera detected')
        return [('vc.ril.camera', 'VideoCore Camera')]

    return []
