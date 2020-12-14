
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
import os
import io
import sys
import re
import signal
import socket
import time
#<<<<<<< HEAD
#import urllib
#import urllib2
#import random
#import codecs
#import uuid
#import binascii
#import json
#
#
#import settings
#
#import config
#import mediafiles
#import motionctl
#import tzctl
#=======
import pycurl
import datetime

from tornado.ioloop import IOLoop

from motioneye import config
from motioneye import mediafiles
from motioneye import motionctl
from motioneye import settings
from motioneye import utils
from motioneye.controls import tzctl


messages = {
    'motion_start': 'Motion has been detected by camera "%(camera)s/%(hostname)s" at %(moment)s (%(timezone)s).'
}

user_agent = 'motionEye'


def send_message(api_key, chat_id, message, files):
    telegram_message_url = 'https://api.telegram.org/bot%s/sendMessage' % api_key
    telegram_photo_url = 'https://api.telegram.org/bot%s/sendPhoto' % api_key
    c = pycurl.Curl()
    c.setopt(c.POST, 1)
    c.setopt(c.URL, telegram_message_url)
    if not files:
        logging.info('no files')
        c.setopt(c.POSTFIELDS, "chat_id=%s&text=%s" % (chat_id, message))
        c.perform()
    else:
        logging.info('files present')
        for f in files:
            c.setopt(c.URL, telegram_photo_url)
            # Send photos
            c.setopt(c.HTTPPOST, [("chat_id", chat_id), ("caption", message), ("photo", (c.FORM_FILE, f))])
            c.perform()
    c.close()
    logging.debug('sending email message')

def make_message(message, camera_id, moment, timespan, callback):
    camera_config = config.get_camera(camera_id)
    
    # we must start the IO loop for the media list subprocess polling
    io_loop = IOLoop.instance()

    def on_media_files(media_files):
        io_loop.stop()
        photos = []

        timestamp = time.mktime(moment.timetuple())
        if media_files:
            logging.debug('got media files')
            media_files = [m for m in media_files if abs(m['timestamp'] - timestamp) < float(timespan)]
            media_files.sort(key=lambda m: m['timestamp'], reverse=True)
            media_files = [os.path.join(camera_config['target_dir'], re.sub('^/', '', m['path'])) for m in media_files]
            logging.debug('selected %d pictures' % len(media_files))

        format_dict = {
            'camera': camera_config['camera_name'],
            'hostname': socket.gethostname(),
            'moment': moment.strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        if settings.LOCAL_TIME_FILE:
            format_dict['timezone'] = tzctl.get_time_zone()

        else:
            format_dict['timezone'] = 'local time'

        logging.debug('creating email message')
    
        m = message % format_dict

        callback(m, media_files)

    if not timespan:
        return on_media_files([])
    
    logging.debug('waiting for pictures to be taken')
    time.sleep(float(timespan))  # give motion some time to create motion pictures

    prefix = None
    picture_filename = camera_config.get('picture_filename')
    snapshot_filename = camera_config.get('snapshot_filename')

    if ((picture_filename or snapshot_filename) and
        not picture_filename or picture_filename.startswith('%Y-%m-%d/') and
        not snapshot_filename or snapshot_filename .startswith('%Y-%m-%d/')):
        moment = datetime.datetime.strptime(moment, '%Y-%m-%dT%H:%M:%S')
        prefix = moment.strftime('%Y-%m-%d')
        logging.debug('narrowing down still images path lookup to %s' % prefix)

    ## mediafiles.list_media(camera_config, media_type='picture', prefix=prefix, callback=on_media_files)
    fut = utils.cast_future(mediafiles.list_media(camera_config, media_type='picture', prefix=prefix))
    fut.add_done_callback(on_media_files)
    
    io_loop.start()


def parse_options(parser, args):
    parser.add_argument('api', help='telegram api key')
    parser.add_argument('chatid', help='telegram chat room id')
    parser.add_argument('msg_id', help='the identifier of the message')
    parser.add_argument('motion_camera_id', help='the id of the motion camera')
    parser.add_argument('moment', help='the moment in ISO-8601 format')
    parser.add_argument('timespan', help='picture collection time span')
    return parser.parse_args(args)
    

def main(parser, args):
    import meyectl
    
    # the motion daemon overrides SIGCHLD,
    # so we must restore it here,
    # or otherwise media listing won't work
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    if len(args) == 12:
        # backwards compatibility with older configs lacking "from" field
        _from = 'motionEye on %s <%s>' % (socket.gethostname(), args[7].split(',')[0])
        args = args[:7] + [_from] + args[7:]
    
    if not args[7]:
        args[7] = 'motionEye on %s <%s>' % (socket.gethostname(), args[8].split(',')[0])

    options = parse_options(parser, args)
    print(options)
    meyectl.configure_logging('telegram', options.log_to_file)

    logging.debug('hello!')
    message = messages.get(options.msg_id)

    # do not wait too long for media list,
    # telegram notifications are critical
    settings.LIST_MEDIA_TIMEOUT = settings.LIST_MEDIA_TIMEOUT_TELEGRAM
    
    camera_id = motionctl.motion_camera_id_to_camera_id(options.motion_camera_id)

    logging.debug('timespan = %d' % int(options.timespan))
    
    def on_message(message, files):
        try:
            print(message)
            logging.info('sending telegram')
            send_message(options.api, options.chatid, message, files or [])
            logging.info('telegram sent')

        except Exception as e:
            logging.error('failed to send telegram: %s' % e, exc_info=True)

        logging.debug('bye!')
    
    make_message(message, camera_id, options.moment, options.timespan, on_message)
