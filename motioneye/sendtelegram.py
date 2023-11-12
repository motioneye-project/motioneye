
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

import os
import sys
import time
import socket
import logging
import datetime
import binascii
import json
import pycurl
import random
from tornado.ioloop import IOLoop

import settings
import config
import mediafiles
import motionctl
import tzctl
import meyectl  # Assuming this is a local module

# Constants
user_agent = 'motionEye'
messages = {
    'motion_start': 'Motion has been detected by camera "%(camera)s/%(hostname)s" at %(moment)s (%(timezone)s).'
}

def send_telegram_message(api_key, chat_id, text, files):
    """
    Send a Telegram message with optional files.

    Args:
        api_key (str): Telegram API key.
        chat_id (str): Telegram chat room id.
        text (str): Message text.
        files (list): List of file paths to be sent.

    Returns:
        None
    """
    telegram_message_url = 'https://api.telegram.org/bot%s/sendMessage' % api_key
    telegram_photo_url = 'https://api.telegram.org/bot%s/sendPhoto' % api_key
    c = pycurl.Curl()
    c.setopt(c.POST, 1)
    c.setopt(c.URL, telegram_message_url)
    
    if not files:
        logging.info('no files')
        c.setopt(c.POSTFIELDS, "chat_id=%s&text=%s" % (chat_id, text))
        c.perform()
    else:
        logging.info('files present')
        for f in files:
            c.setopt(c.URL, telegram_photo_url)
            c.setopt(c.HTTPPOST, [("chat_id", chat_id), ("caption", text), ("photo", (c.FORM_FILE, f))])
            c.perform()
    c.close()
    logging.debug('sending email message')

def create_telegram_message(api_key, chat_id, msg_id, motion_camera_id, moment, timespan):
    """
    Create a Telegram message based on motion detection.

    Args:
        api_key (str): Telegram API key.
        chat_id (str): Telegram chat room id.
        msg_id (str): Identifier of the message.
        motion_camera_id (str): Motion camera id.
        moment (str): Moment in ISO-8601 format.
        timespan (str): Picture collection time span.

    Returns:
        None
    """
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
    
        m = messages.get(msg_id) % format_dict

        on_telegram_message(m, media_files)

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

    mediafiles.list_media(camera_config, media_type='picture', prefix=prefix, callback=on_media_files)
    
    io_loop.start()

def parse_command_line_args(parser, args):
    """
    Parse command line arguments.

    Args:
        parser: ArgumentParser object.
        args (list): List of command line arguments.

    Returns:
        Namespace: Parsed command line arguments.
    """
    parser.add_argument('api', help='Telegram API key')
    parser.add_argument('chatid', help='Telegram chat room id')
    parser.add_argument('msg_id', help='Identifier of the message')
    parser.add_argument('motion_camera_id', help='Motion camera id')
    parser.add_argument('moment', help='Moment in ISO-8601 format')
    parser.add_argument('timespan', help='Picture collection time span')
    return parser.parse_args(args)

def main(parser, args):
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    if len(args) == 12:
        _from = 'motionEye on %s <%s>' % (socket.gethostname(), args[7].split(',')[0])
        args = args[:7] + [_from] + args[7:]

    if not args[7]:
        args[7] = 'motionEye on %s <%s>' % (socket.gethostname(), args[8].split(',')[0])

    options = parse_command_line_args(parser, args)
    meyectl.configure_logging('telegram', options.log_to_file)

    logging.debug('hello!')
    
    settings.LIST_MEDIA_TIMEOUT = settings.LIST_MEDIA_TIMEOUT_TELEGRAM
    
    camera_id = motionctl.motion_camera_id_to_camera_id(options.motion_camera_id)

    logging.debug('timespan = %d' % int(options.timespan))

    def on_telegram_message(message, files):
        try:
            logging.info('sending telegram')
            send_telegram_message(options.api, options.chatid, message, files or [])
            logging.info('telegram sent')
        except Exception as e:
            logging.error('failed to send telegram: %s' % e, exc_info=True)

        logging.debug('bye!')

    create_telegram_message(options.api, options.chatid, options.msg_id, camera_id, options.moment, options.timespan)

if __name__ == "__main__":
    # Add ArgumentParser initialization if not present
    parser = ArgumentParser(description='MotionEye Telegram Notification Script')
    main(parser, sys.argv[1:])

