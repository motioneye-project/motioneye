from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.request import Request

from motioneye import utils


class TestUrlopen(unittest.TestCase):
    """utils.urlopen() leaves the certificate check to the standard library."""

    def test_the_request_is_passed_on_without_an_ssl_context(self):
        request = Request('https://x.example/')
        with patch('motioneye.utils._urlopen') as urlopen:
            utils.urlopen(request, timeout=3)

        urlopen.assert_called_once_with(request, timeout=3)

    def test_other_schemes_than_http_are_refused(self):
        refused = self.assertRaisesRegex(ValueError, 'Unsupported URL scheme')
        with patch('motioneye.utils._urlopen') as urlopen, refused:
            utils.urlopen(Request('ftp://x/'))

        urlopen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
