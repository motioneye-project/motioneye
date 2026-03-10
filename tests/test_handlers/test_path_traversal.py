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

"""Tests verifying that path traversal elements in API endpoints return HTTP 403."""

import json

import tornado.testing

from motioneye.handlers.movie import MovieHandler
from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import HandlerTestCase


def _assert_path_traversal_403(test_case, response):
    """Assert the response is a 403 specifically caused by path traversal detection."""
    test_case.assertEqual(403, response.code)
    body = json.loads(response.body)
    test_case.assertTrue(
        body.get('error', '').startswith('Path traversal detected'),
        f"Expected error starting with 'Path traversal detected', got: {body.get('error')!r}",
    )


class PictureHandlerPathTraversalTest(HandlerTestCase):
    handler_cls = PictureHandler

    # --- GET: plain path traversal in filename ---

    def test_get_download_plain_traversal_filename(self):
        _assert_path_traversal_403(
            self, self.fetch('/picture/1/download/../../etc/passwd')
        )

    def test_get_preview_plain_traversal_filename(self):
        _assert_path_traversal_403(self, self.fetch('/picture/1/preview/../secret.jpg'))

    # --- GET: URL-encoded path traversal in filename ---

    def test_get_download_url_encoded_traversal_filename(self):
        # %2e%2e decodes to '..'
        _assert_path_traversal_403(
            self, self.fetch('/picture/1/download/%2e%2e/etc/passwd')
        )

    def test_get_preview_url_encoded_traversal_filename_upper(self):
        # %2E%2E decodes to '..' (uppercase hex digits)
        _assert_path_traversal_403(
            self, self.fetch('/picture/1/preview/%2E%2E/secret.jpg')
        )

    # --- GET: plain path traversal in group ---

    def test_get_zipped_plain_traversal_group(self):
        _assert_path_traversal_403(self, self.fetch('/picture/1/zipped/../'))

    def test_get_timelapse_plain_traversal_group(self):
        _assert_path_traversal_403(self, self.fetch('/picture/1/timelapse/../'))

    # --- GET: URL-encoded path traversal in group ---

    def test_get_zipped_url_encoded_traversal_group(self):
        _assert_path_traversal_403(self, self.fetch('/picture/1/zipped/%2e%2e/'))

    def test_get_timelapse_url_encoded_traversal_group_upper(self):
        _assert_path_traversal_403(self, self.fetch('/picture/1/timelapse/%2E%2E/'))

    # --- POST: plain path traversal in filename ---

    def test_post_delete_plain_traversal_filename(self):
        _assert_path_traversal_403(
            self,
            self.fetch('/picture/1/delete/../../etc/passwd', method='POST', body=''),
        )

    # --- POST: URL-encoded path traversal in filename ---

    def test_post_delete_url_encoded_traversal_filename(self):
        _assert_path_traversal_403(
            self,
            self.fetch('/picture/1/delete/%2e%2e/etc/passwd', method='POST', body=''),
        )

    # --- POST: plain path traversal in group ---

    def test_post_delete_all_plain_traversal_group(self):
        _assert_path_traversal_403(
            self, self.fetch('/picture/1/delete_all/../', method='POST', body='')
        )

    # --- POST: URL-encoded path traversal in group ---

    def test_post_delete_all_url_encoded_traversal_group(self):
        _assert_path_traversal_403(
            self, self.fetch('/picture/1/delete_all/%2e%2e/', method='POST', body='')
        )


class MovieHandlerPathTraversalTest(HandlerTestCase):
    handler_cls = MovieHandler

    # --- GET: plain path traversal in filename ---

    def test_get_preview_plain_traversal_filename(self):
        _assert_path_traversal_403(
            self, self.fetch('/movie/1/preview/../../secret.mp4')
        )

    # --- GET: URL-encoded path traversal in filename ---

    def test_get_preview_url_encoded_traversal_filename(self):
        _assert_path_traversal_403(
            self, self.fetch('/movie/1/preview/%2e%2e/secret.mp4')
        )

    def test_get_preview_url_encoded_traversal_filename_upper(self):
        _assert_path_traversal_403(
            self, self.fetch('/movie/1/preview/%2E%2E/secret.mp4')
        )

    # --- POST: plain path traversal in filename ---

    def test_post_delete_plain_traversal_filename(self):
        _assert_path_traversal_403(
            self,
            self.fetch('/movie/1/delete/../../secret.mp4', method='POST', body=''),
        )

    # --- POST: URL-encoded path traversal in filename ---

    def test_post_delete_url_encoded_traversal_filename(self):
        _assert_path_traversal_403(
            self,
            self.fetch('/movie/1/delete/%2e%2e/secret.mp4', method='POST', body=''),
        )

    # --- POST: plain path traversal in group ---

    def test_post_delete_all_plain_traversal_group(self):
        _assert_path_traversal_403(
            self, self.fetch('/movie/1/delete_all/../', method='POST', body='')
        )

    # --- POST: URL-encoded path traversal in group ---

    def test_post_delete_all_url_encoded_traversal_group(self):
        _assert_path_traversal_403(
            self, self.fetch('/movie/1/delete_all/%2e%2e/', method='POST', body='')
        )


if __name__ == '__main__':
    tornado.testing.main()
