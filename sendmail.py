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
import smtplib
import socket
import sys

from email.mime.text import MIMEText

import settings

from motioneye import _configure_settings, _configure_logging

_configure_settings()
_configure_logging()

import config
import tzctl


messages = {
    'motion_start': 'Motion has been detected by camera "%(camera)s/%(hostname)s" at %(moment)s (%(timezone)s).'
}

subjects = {
    'motion_start': 'motionEye: motion detected by "%(camera)s"'
}


def send_mail(server, port, account, password, tls, to, subject, message):
    conn = smtplib.SMTP(server, port, timeout=getattr(settings, 'SMTP_TIMEOUT', 60))
    if tls:
        conn.starttls()
    
    if account and password:
        conn.login(account, password)
    
    _from = account or 'motioneye@' + socket.gethostname()
    
    email = MIMEText(message)
    email['Subject'] = subject
    email['From'] = _from
    email['To'] = to
    
    conn.sendmail(_from, to, email.as_string())
    conn.quit()


def format_message(subject, message, camera_id, moment):
    format_dict = {
        'camera': config.get_camera(camera_id)['@name'],
        'hostname': socket.gethostname(),
        'moment': moment.strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    if settings.LOCAL_TIME_FILE:
        format_dict['timezone'] = tzctl.get_time_zone()
    
    else:
        format_dict['timezone'] = 'local time'

    message = message % format_dict
    subject = subject % format_dict
    subject = subject.replace('\n', ' ')

    message += '\n\n'
    message += 'motionEye.'

    return (subject, message)


def print_usage():
    print 'Usage: sendmail.py <server> <port> <account> <password> <tls> <to> <msg_id> <camera_id> <moment>'


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
    subject, message = format_message(subject, message, camera_id, moment)
    
    send_mail(server, port, account, password, tls, to, subject, message)
    
    logging.info('message sent.')
