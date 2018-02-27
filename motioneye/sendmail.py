
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
import signal
import smtplib
import socket
import time

from email import Encoders
from email.mime.text import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.Utils import formatdate

from tornado.ioloop import IOLoop

import settings

import config
import mediafiles
import motionctl
import tzctl


messages = {
    'motion_start': 'Motion has been detected by camera "%(camera)s/%(hostname)s" at %(moment)s (%(timezone)s).'
}

subjects = {
    'motion_start': 'motionEye: motion detected by "%(camera)s"'
}


def send_mail(server, port, account, password, tls, _from, to, subject, message, files):
    conn = smtplib.SMTP(server, port, timeout=settings.SMTP_TIMEOUT)
    if tls:
        conn.starttls()
    
    if account and password:
        conn.login(account, password)
    
    email = MIMEMultipart()
    email['Subject'] = subject
    email['From'] = _from
    email['To'] = ', '.join(to)
    email['Date'] = formatdate(localtime=True)
    email.attach(MIMEText(message))
    
    for name in reversed(files):
        part = MIMEBase('image', 'jpeg')
        with open(name, 'rb') as f:
            part.set_payload(f.read())
        
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(name))
        email.attach(part)
    
    if files:
        logging.debug('attached %d pictures' % len(files))

    logging.debug('sending email message')
    conn.sendmail(_from, to, email.as_string())
    conn.quit()


def make_message(subject, message, camera_id, moment, timespan, callback):
    camera_config = config.get_camera(camera_id)
    
    # we must start the IO loop for the media list subprocess polling
    io_loop = IOLoop.instance()

    def on_media_files(media_files):
        io_loop.stop()
        
        timestamp = time.mktime(moment.timetuple())

        if media_files:
            logging.debug('got media files')

            # filter out non-recent media files
            media_files = [m for m in media_files if abs(m['timestamp'] - timestamp) < timespan]
            media_files.sort(key=lambda m: m['timestamp'], reverse=True)
            media_files = [os.path.join(camera_config['target_dir'], re.sub('^/', '', m['path'])) for m in media_files]

            logging.debug('selected %d pictures' % len(media_files))

        format_dict = {
            'camera': camera_config['@name'],
            'hostname': socket.gethostname(),
            'moment': moment.strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        if settings.LOCAL_TIME_FILE:
            format_dict['timezone'] = tzctl.get_time_zone()

        else:
            format_dict['timezone'] = 'local time'

        logging.debug('creating email message')
    
        m = message % format_dict
        s = subject % format_dict
        s = s.replace('\n', ' ')
    
        m += '\n\n'
        m += 'motionEye.'

        callback(s, m, media_files)

    if not timespan:
        return on_media_files([])
    
    logging.debug('waiting for pictures to be taken')
    time.sleep(timespan)  # give motion some time to create motion pictures

    prefix = None
    picture_filename = camera_config.get('picture_filename')
    snapshot_filename = camera_config.get('snapshot_filename')

    if ((picture_filename or snapshot_filename) and
        not picture_filename or picture_filename.startswith('%Y-%m-%d/') and
        not snapshot_filename or snapshot_filename .startswith('%Y-%m-%d/')):

        prefix = moment.strftime('%Y-%m-%d')
        logging.debug('narrowing down still images path lookup to %s' % prefix)

    mediafiles.list_media(camera_config, media_type='picture', prefix=prefix, callback=on_media_files)
    
    io_loop.start()


def parse_options(parser, args):
    parser.add_argument('server', help='address of the SMTP server')
    parser.add_argument('port', help='port for the SMTP connection')
    parser.add_argument('account', help='SMTP account name (username)')
    parser.add_argument('password', help='SMTP account password')
    parser.add_argument('tls', help='"true" to use TLS')
    parser.add_argument('from', help='the email from field')
    parser.add_argument('to', help='the email recipient(s)')
    parser.add_argument('msg_id', help='the identifier of the message')
    parser.add_argument('thread_id', help='the id of the motion thread')
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
    
    meyectl.configure_logging('sendmail', options.log_to_file)

    logging.debug('hello!')

    options.port = int(options.port) 
    options.tls = options.tls.lower() == 'true'
    options.timespan = int(options.timespan)
    message = messages.get(options.msg_id)
    subject = subjects.get(options.msg_id)
    options.moment = datetime.datetime.strptime(options.moment, '%Y-%m-%dT%H:%M:%S')
    options.password = options.password.replace('\\;', ';')  # unescape password
    
    # do not wait too long for media list,
    # email notifications are critical
    settings.LIST_MEDIA_TIMEOUT = settings.LIST_MEDIA_TIMEOUT_EMAIL
    
    camera_id = motionctl.thread_id_to_camera_id(options.thread_id)
    _from = getattr(options, 'from')

    logging.debug('server = %s' % options.server)
    logging.debug('port = %s' % options.port)
    logging.debug('account = %s' % options.account)
    logging.debug('password = ******')
    logging.debug('server = %s' % options.server)
    logging.debug('tls = %s' % str(options.tls).lower())
    logging.debug('from = %s' % _from)
    logging.debug('to = %s' % options.to)
    logging.debug('msg_id = %s' % options.msg_id)
    logging.debug('thread_id = %s' % options.thread_id)
    logging.debug('camera_id = %s' % camera_id)
    logging.debug('moment = %s' % options.moment.strftime('%Y-%m-%d %H:%M:%S'))
    logging.debug('smtp timeout = %d' % settings.SMTP_TIMEOUT)
    logging.debug('timespan = %d' % options.timespan)
    
    to = [t.strip() for t in re.split('[,;| ]', options.to)]
    to = [t for t in to if t]

    def on_message(subject, message, files):
        try:
            logging.info('sending email')
            send_mail(options.server, options.port, options.account, options.password,
                      options.tls, _from, to, subject, message, files or [])
            logging.info('email sent')

        except Exception as e:
            logging.error('failed to send mail: %s' % e, exc_info=True)

        logging.debug('bye!')
    
    make_message(subject, message, camera_id, options.moment, options.timespan, on_message)
