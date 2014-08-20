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

import logging
import sys
import urllib2
import urlparse

import settings

from motioneye import _configure_settings, _configure_logging


_configure_settings()
_configure_logging()


def print_usage():
    print 'Usage: webhook.py <method> <url>'


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(-1)
    
    method = sys.argv[1] 
    url = sys.argv[2]

    logging.debug('method = %s' % method)
    logging.debug('url = %s' % url)
    
    if method == 'POST':
        parts = urlparse.urlparse(url)
        data = parts.query

    else:
        data = None

    request = urllib2.Request(url, data)
    try:
        urllib2.urlopen(request, timeout=settings.REMOTE_REQUEST_TIMEOUT)
        logging.debug('webhook successfully called')
    
    except Exception as e:
        logging.error('failed to call webhook: %s' % e)
