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

import os
import smtplib
import socket
import sys

from email.mime.text import MIMEText

import settings


def send_mail(host, port, username, password, tls, to, subject, message):
    conn = smtplib.SMTP(host, port, timeout=getattr(settings, 'SMTP_TIMEOUT', 60))
    if tls:
        conn.starttls()
    
    if username and password:
        conn.login(username, password)
    
    _from = username or 'motioneye@' + socket.gethostname()
    
    email = MIMEText(message)
    email['Subject'] = subject
    email['From'] = _from
    email['To'] = to
    
    conn.sendmail(_from, to, email.as_string())
    conn.quit()


def print_usage():
    print 'Usage: sendmail.py <to> <message>'
    print 'Environment: HOST, PORT, USERNAME, PASSWORD, TLD'


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print_usage()
        sys.exit(-1)
    
    host = os.environ.get('SMTP_HOST', 'localhost')
    port = int(os.environ.get('SMTP_PORT', '465')) 
    username = os.environ.get('SMTP_USERNAME')
    password = os.environ.get('SMTP_PASSWORD')
    tls = os.environ.get('SMTP_TLS') == 'true' or True
    to = sys.argv[1]
    subject = sys.argv[2]
    message = sys.argv[3]
    
    send_mail(host, port, username, password, tls, to, subject, message)
    
    print('message sent.')
