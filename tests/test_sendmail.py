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

import smtplib
import unittest
from unittest.mock import patch

from motioneye import sendmail

_ARGS = ('smtp.example', 25, '', '', False, 'a@example', ['b@example'])
_KW = {'subject': 'subj', 'message': 'msg', 'files': []}


class SendMailTest(unittest.TestCase):
    @patch('motioneye.sendmail.smtplib.SMTP')
    def test_quit_failure_is_not_a_send_failure(self, mock_smtp):
        conn = mock_smtp.return_value
        conn.quit.side_effect = smtplib.SMTPServerDisconnected('connection closed')

        # the message was accepted by sendmail(); a failing quit() (e.g. Gmail
        # dropping the connection) must not be reported as a send failure (#3125)
        sendmail.send_mail(*_ARGS, **_KW)

        conn.sendmail.assert_called_once()
        conn.quit.assert_called_once()

    @patch('motioneye.sendmail.smtplib.SMTP')
    def test_send_failure_propagates(self, mock_smtp):
        conn = mock_smtp.return_value
        conn.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
            {'b@example': (550, b'no')}
        )

        # a real failure while sending must still propagate to the caller
        with self.assertRaises(smtplib.SMTPException):
            sendmail.send_mail(*_ARGS, **_KW)


if __name__ == '__main__':
    unittest.main()
