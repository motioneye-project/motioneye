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

import json
import unittest
from unittest.mock import patch

from motioneye.uploadservices import Dropbox


class TestDropboxTestAccess(unittest.TestCase):
    """Dropbox.test_access must send a bytes POST body; urllib's Request rejects
    a str body with "POST data should be bytes ... not str" (#2828)."""

    @patch.object(Dropbox, '_request')
    def test_test_access_sends_bytes_body(self, mock_request):
        service = Dropbox(camera_id=1)
        service._location = '/backups'

        result = service.test_access()

        self.assertTrue(result)
        # _request(url, body, headers) - positional, [0] is the args tuple
        url, body, _headers = mock_request.call_args[0]
        self.assertEqual(url, Dropbox.LIST_FOLDER_URL)
        self.assertIsInstance(body, bytes)
        self.assertEqual(json.loads(body.decode())['path'], '/backups')


if __name__ == '__main__':
    unittest.main()
