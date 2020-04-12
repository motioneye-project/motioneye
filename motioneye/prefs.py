
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

from motioneye import settings


_PREFS_FILE_NAME = 'prefs.json'
_DEFAULT_PREFS = {
    'layout_columns': 3,
    'fit_frames_vertically': True,
    'layout_rows': 1,
    'framerate_factor': 1,
    'resolution_factor': 1
}

_prefs = None


def _load():
    global _prefs
    
    _prefs = {}

    file_path = os.path.join(settings.CONF_PATH, _PREFS_FILE_NAME)
    
    if os.path.exists(file_path):
        logging.debug('loading preferences from "%s"...' % file_path)
    
        try:
            f = open(file_path, 'r')
        
        except Exception as e:
            logging.error('could not open preferences file "%s": %s' % (file_path, e))
            
            return
        
        try:
            _prefs = json.load(f)

        except Exception as e:
            logging.error('could not read preferences from file "%s": %s' % (file_path, e))

        finally:
            f.close()
            
    else:
        logging.debug('preferences file "%s" does not exist, using default preferences' % file_path)


def _save():
    file_path = os.path.join(settings.CONF_PATH, _PREFS_FILE_NAME)
    
    logging.debug('saving preferences to "%s"...' % file_path)

    try:
        f = open(file_path, 'w')

    except Exception as e:
        logging.error('could not open preferences file "%s": %s' % (file_path, e))
        
        return

    try:
        json.dump(_prefs, f, sort_keys=True, indent=4)

    except Exception as e:
        logging.error('could not save preferences to file "%s": %s' % (file_path, e))

    finally:
        f.close()


def get(username, key=None):
    if _prefs is None:
        _load()

    if key:
        prefs = _prefs.get(username, {}).get(key, _DEFAULT_PREFS.get(key))
    
    else:
        prefs = dict(_DEFAULT_PREFS)
        prefs.update(_prefs.get(username, {}))
        
    return prefs


def set(username, key, value):
    if _prefs is None:
        _load()

    if key:
        _prefs.setdefault(username, {})[key] = value
        
    else:
        _prefs[username] = value

    _save()
