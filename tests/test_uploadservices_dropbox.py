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
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

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


def _http_error(code, body=b''):
    return HTTPError(
        'https://api.dropboxapi.com/2/x', code, 'reason', {}, BytesIO(body)
    )


class _Response:
    def read(self):
        return b'{}'


class TestDropboxRequestErrors(unittest.TestCase):
    """A failure after refreshed credentials is reported as that failure, with the
    reason Dropbox gives in the body (#3128)."""

    def setUp(self):
        self.service = Dropbox(camera_id=1)
        self.service._location = '/cams'
        self.service._credentials = {'access_token': 'old', 'refresh_token': 'r'}
        for target in ('save',):
            patcher = patch.object(Dropbox, target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _request(self, *responses, refresh=None):
        with (
            patch('motioneye.uploadservices.utils.urlopen', side_effect=responses),
            patch.object(
                Dropbox,
                '_refresh_credentials',
                side_effect=refresh,
                return_value={'access_token': 'new', 'refresh_token': 'r'},
            ) as refreshed,
            self.assertLogs(level='DEBUG') as logs,
        ):
            try:
                result = self.service._request(Dropbox.UPLOAD_URL, b'data', {})
            except Exception as e:
                result = e

        return result, refreshed, [r.getMessage() for r in logs.records]

    def test_a_failure_after_the_refresh_is_not_a_refresh_failure(self):
        conflict = (
            b'{"error_summary": "path/conflict/file/..", "error": {".tag": "path"}}'
        )
        result, refreshed, logs = self._request(
            _http_error(401), _http_error(409, conflict)
        )

        self.assertIsInstance(result, HTTPError)
        refreshed.assert_called_once_with('r')
        self.assertIn(
            'dropbox: request failed: HTTP Error 409: reason (path/conflict/file/..)',
            logs,
        )
        self.assertNotIn('dropbox: refreshing credentials failed', logs)

    def test_a_failing_refresh_is_reported_as_such(self):
        result, _refreshed, logs = self._request(
            _http_error(401), refresh=RuntimeError('invalid_grant')
        )

        self.assertIsInstance(result, RuntimeError)
        self.assertIn('dropbox: refreshing credentials failed', logs)

    def test_a_refreshed_request_that_works_answers(self):
        result, refreshed, _logs = self._request(_http_error(401), _Response())

        self.assertEqual(b'{}', result)
        refreshed.assert_called_once_with('r')
        self.assertEqual('new', self.service._credentials['access_token'])

    def test_a_missing_folder_is_told_by_the_body(self):
        not_found = b'{"error_summary": "path/not_found/..", "error": {}}'
        result, _refreshed, logs = self._request(_http_error(409, not_found))

        self.assertIsInstance(result, FileNotFoundError)
        self.assertIn('dropbox: folder "/cams" not found', logs)

    def test_without_a_summary_the_error_itself_is_logged(self):
        body = b'{"error": {".tag": "too_many_write_operations"}}'
        _result, _refreshed, logs = self._request(_http_error(429, body))

        self.assertIn(
            'dropbox: request failed: HTTP Error 429: reason '
            '({".tag": "too_many_write_operations"})',
            logs,
        )

    def test_a_body_that_is_not_json_is_left_out(self):
        _result, _refreshed, logs = self._request(_http_error(500, b'<html>'))

        self.assertIn('dropbox: request failed: HTTP Error 500: reason', logs)


if __name__ == '__main__':
    unittest.main()
