from __future__ import annotations

import unittest

from motioneye import remote


class TestRemoteRequest(unittest.TestCase):
    """The hub's requests to a remote motionEye never follow a redirect."""

    def test_redirects_are_not_followed(self):
        request = remote._make_request(
            'http', 'cam.example', 8765, 'secret', '/config/list/'
        )

        self.assertFalse(request.follow_redirects)
        self.assertEqual(
            'http://cam.example:8765/config/list/', request.url.split('?')[0]
        )


class TestRemoteRequestCertificate(unittest.TestCase):
    """The certificate of a remote motionEye is verified unless the camera says not to."""

    def test_the_certificate_is_verified_by_default(self):
        request = remote._make_request(
            'https', 'cam.example', 8765, 'secret', '/config/list/'
        )

        self.assertIs(True, request.validate_cert)

    def test_the_certificate_check_can_be_turned_off(self):
        request = remote._make_request(
            'https', 'cam.example', 8765, 'secret', '/config/list/', validate_cert=False
        )

        self.assertIs(False, request.validate_cert)
