import ssl
from json import dumps, loads
from unittest.mock import patch

import tornado.testing

from motioneye import settings
from motioneye.handlers.config import ConfigHandler
from tests.test_handlers import HandlerTestCase

# what the Test Email button posts, see doTestEmail() in main.js
_BODY = {
    'what': 'email',
    'from': '',
    'addresses': 'a@example,b@example',
    'smtp_server': 'smtp.example',
    'smtp_port': '587',
    'smtp_account': '',
    'smtp_password': '',
    'smtp_tls': True,
}

# what OpenSSL reports for a self-signed certificate
_VERIFY_FAILED = (
    '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: '
    'self-signed certificate'
)
# a host name with 'tls' in it: the generic 'tls' hint must not win over the certificate one
_MISMATCH = "Hostname mismatch, certificate is not valid for 'starttls.example'."


class TestEmailTest(HandlerTestCase):
    """The Test Email button checks the server certificate as a notification does."""

    handler_cls = ConfigHandler

    def _post_as_admin(self, path, body):
        return self.fetch(
            path,
            method='POST',
            body=dumps(body),
            headers={  # the handler reads the body only as JSON
                'Cookie': self.make_session_cookie('admin'),
                'Content-Type': 'application/json',
            },
        )

    def _test_email(self, **fields):
        # POST /config/1/test/ as the button does, with these fields changed
        response = self._post_as_admin('/config/1/test/', dict(_BODY, **fields))
        self.assertEqual(200, response.code)
        return loads(response.body)

    def test_the_test_email_verifies_the_certificate_by_default(self):
        with patch('motioneye.sendmail.send_mail') as send_mail:
            answer = self._test_email()  # no smtp_verify: an older UI or client

        self.assertEqual({}, answer)
        expected = ('smtp.example', 587, '', '', True, '', ['a@example', 'b@example'])
        self.assertEqual(expected, send_mail.call_args.args[:7])
        self.assertIs(True, send_mail.call_args.kwargs['verify'])

    def test_the_test_email_can_turn_the_check_off(self):
        with patch('motioneye.sendmail.send_mail') as send_mail:
            answer = self._test_email(smtp_verify=False)

        self.assertEqual({}, answer)
        self.assertIs(False, send_mail.call_args.kwargs['verify'])

    def test_a_text_off_value_turns_the_check_off(self):
        # an API client may send the switch as text
        with patch('motioneye.sendmail.send_mail') as send_mail:
            answer = self._test_email(smtp_verify='off')

        self.assertEqual({}, answer)
        self.assertIs(False, send_mail.call_args.kwargs['verify'])

    def test_a_certificate_error_names_the_switch(self):
        error = ssl.SSLCertVerificationError(
            1,
            f'[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: {_MISMATCH}',
        )
        error.verify_message = _MISMATCH  # what a real handshake failure carries
        with (
            patch('motioneye.sendmail.send_mail', side_effect=error),
            self.assertLogs(level='ERROR') as logs,
        ):
            answer = self._test_email()

        self.assertEqual(
            f'certificate check failed ({_MISMATCH}); turn off Verify certificate '
            'only for a server with a self-signed certificate that you trust',
            answer['error'],
        )
        self.assertIn('notification email test failed', '\n'.join(logs.output))

    def test_the_smtp_timeout_is_restored_after_a_failure(self):
        error = ssl.SSLCertVerificationError(1, _VERIFY_FAILED)
        with (
            patch('motioneye.settings.SMTP_TIMEOUT', 60),
            patch('motioneye.sendmail.send_mail', side_effect=error),
            self.assertLogs(level='ERROR'),
        ):
            self._test_email()

            # the test shortens the timeout to 10 s, the senders must get theirs back
            self.assertEqual(60, settings.SMTP_TIMEOUT)


if __name__ == '__main__':
    tornado.testing.main()
