#!/usr/bin/env python

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

import base64
import logging
import os.path
import sys
import urllib2

sys.path.append(os.path.join(os.path.dirname(sys.argv[0]),'src'))

import config
import settings

from motioneye import _configure_settings, _configure_logging


_configure_settings()
_configure_logging()


def print_usage():
    print 'Usage: eventrelay.py <event> <camera_id>'


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(-1)
    
    event = sys.argv[1] 
    camera_id = sys.argv[2]

    logging.debug('event = %s' % event)
    logging.debug('camera_id = %s' % camera_id)

    url = 'http://127.0.0.1:%(port)s/config/%(camera_id)s/_relay_event/?event=%(event)s' % {
            'port': settings.PORT,
            'camera_id': camera_id,
            'event': event}

    main_config = config.get_main()
    
    username = main_config.get('@admin_username', '')
    password = main_config.get('@admin_password', '')
    
    request = urllib2.Request(url, '')
    request.add_header('Authorization', 'Basic %s' % base64.encodestring('%s:%s' % (username, password)).replace('\n', ''))
    
    try:
        urllib2.urlopen(request, timeout=settings.REMOTE_REQUEST_TIMEOUT)
        logging.debug('event successfully relayed')
    
    except Exception as e:
        logging.error('failed to relay event: %s' % e)
