from __future__ import annotations

import ssl
import unittest
from unittest.mock import patch
from urllib.request import Request

from motioneye import utils


class TestUrlopen(unittest.TestCase):
    """utils.urlopen() leaves the certificate check to the standard library
    unless the caller turns it off."""

    def test_the_request_is_passed_on_without_an_ssl_context(self):
        request = Request('https://x.example/')
        with patch('motioneye.utils._urlopen') as urlopen:
            utils.urlopen(request, timeout=3)

        urlopen.assert_called_once_with(request, timeout=3)

    def test_verify_on_passes_no_context(self):
        request = Request('https://x.example/')
        with patch('motioneye.utils._urlopen') as urlopen:
            utils.urlopen(request, verify=True)

        urlopen.assert_called_once_with(request)

    def test_the_check_can_be_turned_off_for_one_request(self):
        request = Request('https://x.example/')
        with patch('motioneye.utils._urlopen') as urlopen:
            utils.urlopen(request, timeout=3, verify=False)

        urlopen.assert_called_once()
        self.assertEqual((request,), urlopen.call_args.args)
        context = urlopen.call_args.kwargs['context']
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertFalse(context.check_hostname)
        self.assertEqual(ssl.CERT_NONE, context.verify_mode)
        self.assertEqual(3, urlopen.call_args.kwargs['timeout'])

    def test_other_schemes_than_http_are_refused(self):
        refused = self.assertRaisesRegex(ValueError, 'Unsupported URL scheme')
        with patch('motioneye.utils._urlopen') as urlopen, refused:
            utils.urlopen(Request('ftp://x/'))

        urlopen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
