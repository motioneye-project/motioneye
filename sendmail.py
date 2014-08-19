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

import datetime
import logging
import os
import re
import smtplib
import socket
import sys
import time

from email import Encoders
from email.mime.text import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from tornado.ioloop import IOLoop

import settings

from motioneye import _configure_settings, _configure_logging, _configure_signals

_configure_settings()
_configure_signals()
_configure_logging()

import config
import mediafiles
import tzctl


messages = {
    'motion_start': 'Motion has been detected by camera "%(camera)s/%(hostname)s" at %(moment)s (%(timezone)s).'
}

subjects = {
    'motion_start': 'motionEye: motion detected by "%(camera)s"'
}


def send_mail(server, port, account, password, tls, to, subject, message, files):
    conn = smtplib.SMTP(server, port, timeout=getattr(settings, 'SMTP_TIMEOUT', 60))
    if tls:
        conn.starttls()
    
    if account and password:
        conn.login(account, password)
    
    _from = account or 'motioneye@' + socket.gethostname()
    
    email = MIMEMultipart()
    email['Subject'] = subject
    email['From'] = _from
    email['To'] = to
    email.attach(MIMEText(message))
    
    for file in reversed(files):
        part = MIMEBase('application', 'image/jpg')
        with open(file, 'rb') as f:
            part.set_payload(f.read())
        
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(file))
        email.attach(part)
    
    if files:
        logging.debug('attached %d pictures' % len(files))

    conn.sendmail(_from, to, email.as_string())
    conn.quit()


def make_message(subject, message, camera_id, moment, callback):
    camera_config = config.get_camera(camera_id)
    
    def on_media_files(media_files):
        timestamp = time.mktime(moment.timetuple())

        media_files = [m for m in media_files if abs(m['timestamp'] - timestamp) < settings.NOTIFY_MEDIA_TIMESPAN] # filter out non-recent media files
        media_files.sort(key=lambda m: m['timestamp'], reverse=True)
        media_files = [os.path.join(camera_config['target_dir'], re.sub('^/', '', m['path'])) for m in media_files]

        format_dict = {
            'camera': camera_config['@name'],
            'hostname': socket.gethostname(),
            'moment': moment.strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        if settings.LOCAL_TIME_FILE:
            format_dict['timezone'] = tzctl.get_time_zone()
        
        else:
            format_dict['timezone'] = 'local time'
    
        m = message % format_dict
        s = subject % format_dict
        s = s.replace('\n', ' ')
    
        m += '\n\n'
        m += 'motionEye.'
        
        callback(s, m, media_files)

    time.sleep(settings.NOTIFY_MEDIA_TIMESPAN)
    mediafiles.list_media(camera_config, media_type='picture', callback=on_media_files)


def print_usage():
    print 'Usage: sendmail.py <server> <port> <account> <password> <tls> <to> <msg_id> <camera_id> <moment> <frames>'


if __name__ == '__main__':
    if len(sys.argv) < 10:
        print_usage()
        sys.exit(-1)
    
    server = sys.argv[1]
    port = int(sys.argv[2]) 
    account = sys.argv[3]
    password = sys.argv[4]
    tls = sys.argv[5].lower() == 'true'
    to = sys.argv[6]
    msg_id = sys.argv[7]
    camera_id = sys.argv[8]
    moment = sys.argv[9]
    
    message = messages.get(msg_id)
    subject = subjects.get(msg_id)
    if not message or not subject:
        logging.error('unknown message id')
        sys.exit(-1)
    
    moment = datetime.datetime.strptime(moment, '%Y-%m-%dT%H:%M:%S')
    
    logging.debug('server = %s' % server)
    logging.debug('port = %s' % port)
    logging.debug('account = %s' % account)
    logging.debug('password = ******')
    logging.debug('server = %s' % server)
    logging.debug('tls = %s' % tls)
    logging.debug('to = %s' % to)
    logging.debug('msg_id = %s' % msg_id)
    logging.debug('camera_id = %s' % camera_id)
    logging.debug('moment = %s' % moment.strftime('%Y-%m-%d %H:%M:%S'))
    logging.debug('smtp timeout = %d' % settings.SMTP_TIMEOUT)
    
    io_loop = IOLoop.instance()
    
    def on_message(subject, message, files):
        try:
            send_mail(server, port, account, password, tls, to, subject, message, files)
            logging.info('email sent')
        
        except Exception as e:
            logging.error('failed to send mail: %s' % e, exc_info=True)

        io_loop.stop()
    
    def ioloop_timeout():
        io_loop.stop()
    
    make_message(subject, message, camera_id, moment, on_message)

    io_loop.add_timeout(datetime.timedelta(seconds=settings.SMTP_TIMEOUT), ioloop_timeout)
    io_loop.start()
