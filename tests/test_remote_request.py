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
