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
import ssl
import unittest
from unittest.mock import patch

from motioneye import sendmail

_ARGS = ('smtp.example', 25, '', '', False, 'a@example', ['b@example'])
_TLS_ARGS = ('smtp.example', 587, '', '', True, 'a@example', ['b@example'])
_KW = {'subject': 'subj', 'message': 'msg', 'files': []}

# what OpenSSL reports for a self-signed certificate
_VERIFY_FAILED = (
    '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: '
    'self-signed certificate'
)


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

    @patch('motioneye.sendmail.smtplib.SMTP')
    def test_starttls_verifies_the_certificate_by_default(self, mock_smtp):
        conn = mock_smtp.return_value

        # smtplib's own context accepts any certificate; ours checks the chain
        # against the system's authorities and the host name, before anything
        # else goes over the connection
        sendmail.send_mail(*_TLS_ARGS, **_KW)

        conn.starttls.assert_called_once()
        context = conn.starttls.call_args.kwargs['context']
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertTrue(context.check_hostname)
        self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)
        names = [name for name, _, _ in conn.method_calls]
        self.assertLess(names.index('starttls'), names.index('sendmail'))

    @patch('motioneye.sendmail.smtplib.SMTP')
    def test_the_check_can_be_turned_off(self, mock_smtp):
        conn = mock_smtp.return_value

        # a self-signed certificate the user trusts: still encrypted, not authenticated
        sendmail.send_mail(*_TLS_ARGS, **_KW, verify=False)

        context = conn.starttls.call_args.kwargs['context']
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertFalse(context.check_hostname)
        self.assertEqual(ssl.CERT_NONE, context.verify_mode)
        conn.sendmail.assert_called_once()

    @patch('motioneye.sendmail.smtplib.SMTP')
    def test_no_tls_means_no_starttls(self, mock_smtp):
        conn = mock_smtp.return_value
        for verify in (True, False):
            with self.subTest(verify=verify):
                conn.reset_mock()
                # the switch only matters with TLS on
                sendmail.send_mail(*_ARGS, **_KW, verify=verify)

                conn.starttls.assert_not_called()
                conn.sendmail.assert_called_once()

    @patch('motioneye.sendmail.smtplib.SMTP')
    def test_a_certificate_error_propagates(self, mock_smtp):
        conn = mock_smtp.return_value
        conn.starttls.side_effect = ssl.SSLCertVerificationError(1, _VERIFY_FAILED)

        # a failed check must reach the caller before the credentials are sent
        with_login = (*_TLS_ARGS[:2], '007', 'FAKE-pw', *_TLS_ARGS[4:])
        with self.assertRaises(ssl.SSLCertVerificationError):
            sendmail.send_mail(*with_login, **_KW)

        conn.login.assert_not_called()
        conn.sendmail.assert_not_called()


if __name__ == '__main__':
    unittest.main()
