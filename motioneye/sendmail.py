
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
import time

from email import Encoders
from email.mime.text import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from tornado.ioloop import IOLoop

import settings

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
    conn = smtplib.SMTP(server, port, timeout=settings.SMTP_TIMEOUT)
    if tls:
        conn.starttls()
    
    if account and password:
        conn.login(account, password)
    
    _from = 'motionEye on %s <%s>' % (socket.gethostname(), to[0])
    
    email = MIMEMultipart()
    email['Subject'] = subject
    email['From'] = _from
    email['To'] = ', '.join(to)
    email.attach(MIMEText(message))
    
    for file in reversed(files):
        part = MIMEBase('image', 'jpeg')
        with open(file, 'rb') as f:
            part.set_payload(f.read())
        
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(file))
        email.attach(part)
    
    if files:
        logging.debug('attached %d pictures' % len(files))

    logging.debug('sending email message')
    conn.sendmail(_from, to, email.as_string())
    conn.quit()


def make_message(subject, message, camera_id, moment, timespan, callback):
    camera_config = config.get_camera(camera_id)
    
    def on_media_files(media_files):
        logging.debug('got media files')
        
        timestamp = time.mktime(moment.timetuple())

        media_files = [m for m in media_files if abs(m['timestamp'] - timestamp) < timespan] # filter out non-recent media files
        media_files.sort(key=lambda m: m['timestamp'], reverse=True)
        media_files = [os.path.join(camera_config['target_dir'], re.sub('^/', '', m['path'])) for m in media_files]
        
        logging.debug('selected %d pictures' % len(media_files))

        format_dict = {
            'camera': camera_config['@name'],
            'hostname': socket.gethostname(),
            'moment': moment.strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        if settings.LOCAL_TIME_FILE:
            format_dict['timezone'] = tzctl._get_time_zone()
        
        else:
            format_dict['timezone'] = 'local time'
    
        m = message % format_dict
        s = subject % format_dict
        s = s.replace('\n', ' ')
    
        m += '\n\n'
        m += 'motionEye.'
        
        callback(s, m, media_files)

    if not timespan:
        return on_media_files([])

    logging.debug('creating email message')

    time.sleep(timespan) # give motion some time to create motion pictures
    mediafiles.list_media(camera_config, media_type='picture', callback=on_media_files)


def parse_options(parser, args):
    parser.add_argument('server', help='address of the SMTP server')
    parser.add_argument('port', help='port for the SMTP connection')
    parser.add_argument('account', help='SMTP account name (username)')
    parser.add_argument('password', help='SMTP account password')
    parser.add_argument('tls', help='"true" to use TLS')
    parser.add_argument('to', help='the email recipient(s)')
    parser.add_argument('msg_id', help='the identifier of the message')
    parser.add_argument('camera_id', help='the id of the camera')
    parser.add_argument('moment', help='the moment in ISO-8601 format')
    parser.add_argument('timespan', help='picture collection time span')

    return parser.parse_args(args)
    

def main(parser, args):
    import meyectl
    
    options = parse_options(parser, args)
    
    meyectl.configure_logging('sendmail', options.log_to_file)
    meyectl.configure_tornado()

    logging.debug('hello!')

    options.port = int(options.port) 
    options.tls = options.tls.lower() == 'true'
    options.timespan = int(options.timespan)
    message = messages.get(options.msg_id)
    subject = subjects.get(options.msg_id)
    options.moment = datetime.datetime.strptime(options.moment, '%Y-%m-%dT%H:%M:%S')
    
    logging.debug('server = %s' % options.server)
    logging.debug('port = %s' % options.port)
    logging.debug('account = %s' % options.account)
    logging.debug('password = ******')
    logging.debug('server = %s' % options.server)
    logging.debug('tls = %s' % str(options.tls).lower())
    logging.debug('to = %s' % options.to)
    logging.debug('msg_id = %s' % options.msg_id)
    logging.debug('camera_id = %s' % options.camera_id)
    logging.debug('moment = %s' % options.moment.strftime('%Y-%m-%d %H:%M:%S'))
    logging.debug('smtp timeout = %d' % settings.SMTP_TIMEOUT)
    logging.debug('timespan = %d' % options.timespan)
    
    to = [t.strip() for t in re.split('[,;| ]', options.to)]
    to = [t for t in to if t]

    io_loop = IOLoop.instance()
    
    def on_message(subject, message, files):
        try:
            send_mail(options.server, options.port, options.account, options.password,
                    options.tls, to, subject, message, files)
            logging.info('email sent')

        except Exception as e:
            logging.error('failed to send mail: %s' % e, exc_info=True)

        io_loop.stop()
    
    def ioloop_timeout():
        io_loop.stop()
    
    make_message(subject, message, options.camera_id, options.moment, options.timespan, on_message)

    io_loop.add_timeout(datetime.timedelta(seconds=settings.SMTP_TIMEOUT), ioloop_timeout)
    io_loop.start()

    logging.debug('bye!')
