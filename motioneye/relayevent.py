
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

import errno
import json
import logging
import os.path
import sys
import urllib

sys.path.append(os.path.join(os.path.dirname(sys.argv[0]),'src'))

import settings
import utils


def get_admin_credentials():
    # this shortcut function is a bit faster than using the config module functions
    config_file_path = os.path.join(settings.CONF_PATH, 'motion.conf')
    
    logging.debug('reading main config from file %(path)s...' % {'path': config_file_path}) 

    lines = None
    try:
        file = open(config_file_path, 'r')
    
    except IOError as e:
        if e.errno == errno.ENOENT:  # file does not exist
            logging.info('main config file %(path)s does not exist, using default values' % {'path': config_file_path})
            
            lines = []
        
        else:
            logging.error('could not open main config file %(path)s: %(msg)s' % {
                    'path': config_file_path, 'msg': unicode(e)})
            
            raise

    if lines is None:
        try:
            lines = [l[:-1] for l in file.readlines()]
        
        except Exception as e:
            logging.error('could not read main config file %(path)s: %(msg)s' % {
                    'path': config_file_path, 'msg': unicode(e)})
            
            raise
        
        finally:
            file.close()
    
    admin_username = 'admin'
    admin_password = ''
    for line in lines:
        line = line.strip()
        if not line.startswith('#'):
            continue
        
        line = line[1:].strip()
        if line.startswith('@admin_username'):
            parts = line.split(' ', 1)
            admin_username = parts[1] if len(parts) > 1 else ''
            
            continue
        
        if line.startswith('@admin_password'):
            parts = line.split(' ', 1)
            admin_password = parts[1] if len(parts) > 1 else ''

            continue
    
    return admin_username, admin_password


def parse_options(parser, args):
    parser.add_argument('event', help='the name of the event to relay')
    parser.add_argument('thread_id', help='the id of the thread')

    return parser.parse_args(args)
    

def main(parser, args):
    import meyectl
    
    options = parse_options(parser, args)
    
    meyectl.configure_logging('relayevent', options.log_to_file)
    meyectl.configure_tornado()

    logging.debug('hello!')
    logging.debug('event = %s' % options.event)
    logging.debug('thread_id = %s' % options.thread_id)
    
    admin_username, admin_password = get_admin_credentials()

    path = '/_relay_event/?event=%(event)s&thread_id=%(thread_id)s&_username=%(username)s' % {
            'username': admin_username,
            'thread_id': options.thread_id,
            'event': options.event}
    
    signature = utils.compute_signature('POST', path, '', admin_password)
    
    url = 'http://127.0.0.1:%(port)s' + path + '&_signature=' + signature
    url = url % {'port': settings.PORT}
    
    try:
        response = urllib.urlopen(url, data='')
        response = json.load(response)
        if response.get('error'):
            raise Exception(response['error'])
        
        logging.debug('event successfully relayed')
    
    except Exception as e:
        logging.error('failed to relay event: %s' % e)

    logging.debug('bye!')
