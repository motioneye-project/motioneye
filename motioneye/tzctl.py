
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

import hashlib
import logging
import os
import settings
import subprocess

from config import additional_config


LOCAL_TIME_FILE = settings.LOCAL_TIME_FILE  # @UndefinedVariable


def get_time_zone():
    return _get_time_zone_symlink() or _get_time_zone_md5() or 'UTC'


def _get_time_zone_symlink():
    file = settings.LOCAL_TIME_FILE
    if not file:
        return None
    
    for i in xrange(8): # recursively follow the symlinks @UnusedVariable
        try:
            file = os.readlink(file)

        except OSError:
            break
    
    if file and file.startswith('/usr/share/zoneinfo/'):
        file = file[20:]
    
    else:
        file = None

    time_zone = file or None
    if time_zone:
        logging.debug('found time zone by symlink method: %s' % time_zone)
    
    return time_zone


def _get_time_zone_md5():
    if settings.LOCAL_TIME_FILE:
        return None

    try:
        output = subprocess.check_output('find * -type f | xargs md5sum', shell=True, cwd='/usr/share/zoneinfo')

    except Exception as e:
        logging.error('getting md5 of zoneinfo files failed: %s' % e)

        return None
    
    lines = [l for l in output.split('\n') if l]
    lines = [l.split(None, 1) for l in lines]
    time_zone_by_md5 = dict(lines)

    try:
        with open(settings.LOCAL_TIME_FILE, 'r') as f:
            data = f.read()
    
    except Exception as e:
        logging.error('failed to read local time file: %s' % e)
        
        return None

    md5 = hashlib.md5(data).hexdigest()
    time_zone = time_zone_by_md5.get(md5)
    
    if time_zone:
        logging.debug('found time zone by md5 method: %s' % time_zone)
    
    return time_zone


def _set_time_zone(time_zone):
    time_zone = time_zone or 'UTC'

    zoneinfo_file = '/usr/share/zoneinfo/' + time_zone
    if not os.path.exists(zoneinfo_file):
        logging.error('%s file does not exist' % zoneinfo_file)
        
        return False

    logging.debug('linking "%s" to "%s"' % (settings.LOCAL_TIME_FILE, zoneinfo_file))

    try:
        os.remove(settings.LOCAL_TIME_FILE)
    
    except:
        pass # nevermind
    
    try:
        os.symlink(zoneinfo_file, settings.LOCAL_TIME_FILE)
        
        return True
    
    except Exception as e:
        logging.error('failed to link "%s" to "%s": %s' % (settings.LOCAL_TIME_FILE, zoneinfo_file, e))
        
        return False


@additional_config
def timeZone():
    if not LOCAL_TIME_FILE:
        return

    import pytz
    timezones = pytz.common_timezones

    return {
        'label': 'Time Zone',
        'description': 'selecting the right timezone assures a correct timestamp displayed on pictures and movies',
        'type': 'choices',
        'choices': [(t, t) for t in timezones],
        'section': 'general',
        'advanced': True,
        'reboot': True,
        'get': get_time_zone,
        'set': _set_time_zone
    }
