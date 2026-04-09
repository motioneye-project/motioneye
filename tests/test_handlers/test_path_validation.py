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

"""Tests verifying that path validation (traversal, absolute, dir escape) in API endpoints returns HTTP 403."""

import json

import tornado.testing

from motioneye.handlers.movie import MovieHandler
from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import HandlerTestCase, _FAKE_ESCAPE_LINK


def _assert_traversal_403(test_case, response):
    """Assert the response is a 403 caused by path traversal detection."""
    test_case.assertEqual(403, response.code)
    body = json.loads(response.body)
    test_case.assertTrue(
        body.get('error', '').startswith('Path traversal detected'),
        f"Expected error starting with 'Path traversal detected', got: {body.get('error')!r}",
    )


def _assert_absolute_path_403(test_case, response):
    """Assert the response is a 403 caused by absolute path detection."""
    test_case.assertEqual(403, response.code)
    body = json.loads(response.body)
    test_case.assertTrue(
        body.get('error', '').startswith('Absolute path'),
        f"Expected error starting with 'Absolute path', got: {body.get('error')!r}",
    )


def _assert_dir_escape_403(test_case, response):
    """Assert the response is a 403 caused by camera directory escape."""
    test_case.assertEqual(403, response.code)
    body = json.loads(response.body)
    test_case.assertIn(
        'escapes camera directory',
        body.get('error', ''),
        f"Expected error containing 'escapes camera directory', got: {body.get('error')!r}",
    )


class PictureHandlerPathValidationTest(HandlerTestCase):
    handler_cls = PictureHandler

    # --- GET download: filename ---

    def test_get_download_rejects_traversal(self):
        _assert_traversal_403(self, self.fetch('/picture/1/download/../../etc/passwd'))
        _assert_traversal_403(
            self, self.fetch('/picture/1/download/%2e%2e/etc/passwd')
        )

    def test_get_download_rejects_absolute_path(self):
        _assert_absolute_path_403(
            self, self.fetch('/picture/1/download/%2fetc/passwd')
        )

    def test_get_download_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self, self.fetch(f'/picture/1/download/{_FAKE_ESCAPE_LINK}/secret.jpg')
        )

    # --- GET preview: filename ---

    def test_get_preview_rejects_traversal(self):
        _assert_traversal_403(self, self.fetch('/picture/1/preview/../secret.jpg'))
        _assert_traversal_403(
            self, self.fetch('/picture/1/preview/%2E%2E/secret.jpg')
        )

    def test_get_preview_rejects_absolute_path(self):
        _assert_absolute_path_403(
            self, self.fetch('/picture/1/preview/%2fsecret.jpg')
        )

    def test_get_preview_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self, self.fetch(f'/picture/1/preview/{_FAKE_ESCAPE_LINK}/secret.jpg')
        )

    # --- GET zipped: group ---

    def test_get_zipped_rejects_traversal(self):
        _assert_traversal_403(self, self.fetch('/picture/1/zipped/../'))
        _assert_traversal_403(self, self.fetch('/picture/1/zipped/%2e%2e/'))

    def test_get_zipped_rejects_absolute_path(self):
        _assert_absolute_path_403(self, self.fetch('/picture/1/zipped/%2fetc/'))

    def test_get_zipped_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self, self.fetch(f'/picture/1/zipped/{_FAKE_ESCAPE_LINK}/')
        )

    # --- GET timelapse: group ---

    def test_get_timelapse_rejects_traversal(self):
        _assert_traversal_403(self, self.fetch('/picture/1/timelapse/../'))
        _assert_traversal_403(self, self.fetch('/picture/1/timelapse/%2E%2E/'))

    def test_get_timelapse_rejects_absolute_path(self):
        _assert_absolute_path_403(self, self.fetch('/picture/1/timelapse/%2fetc/'))

    def test_get_timelapse_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self, self.fetch(f'/picture/1/timelapse/{_FAKE_ESCAPE_LINK}/')
        )

    # --- POST delete: filename ---

    def test_post_delete_rejects_traversal(self):
        _assert_traversal_403(
            self,
            self.fetch('/picture/1/delete/../../etc/passwd', method='POST', body=''),
        )
        _assert_traversal_403(
            self,
            self.fetch('/picture/1/delete/%2e%2e/etc/passwd', method='POST', body=''),
        )

    def test_post_delete_rejects_absolute_path(self):
        _assert_absolute_path_403(
            self,
            self.fetch('/picture/1/delete/%2fetc/passwd', method='POST', body=''),
        )

    def test_post_delete_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self,
            self.fetch(
                f'/picture/1/delete/{_FAKE_ESCAPE_LINK}/secret.jpg',
                method='POST',
                body='',
            ),
        )

    # --- POST delete_all: group ---

    def test_post_delete_all_rejects_traversal(self):
        _assert_traversal_403(
            self, self.fetch('/picture/1/delete_all/../', method='POST', body='')
        )
        _assert_traversal_403(
            self, self.fetch('/picture/1/delete_all/%2e%2e/', method='POST', body='')
        )

    def test_post_delete_all_rejects_absolute_path(self):
        _assert_absolute_path_403(
            self,
            self.fetch('/picture/1/delete_all/%2fetc/', method='POST', body=''),
        )

    def test_post_delete_all_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self,
            self.fetch(
                f'/picture/1/delete_all/{_FAKE_ESCAPE_LINK}/', method='POST', body=''
            ),
        )


class MovieHandlerPathValidationTest(HandlerTestCase):
    handler_cls = MovieHandler

    # --- GET preview: filename ---

    def test_get_preview_rejects_traversal(self):
        _assert_traversal_403(self, self.fetch('/movie/1/preview/../../secret.mp4'))
        _assert_traversal_403(self, self.fetch('/movie/1/preview/%2e%2e/secret.mp4'))
        _assert_traversal_403(self, self.fetch('/movie/1/preview/%2E%2E/secret.mp4'))

    def test_get_preview_rejects_absolute_path(self):
        _assert_absolute_path_403(
            self, self.fetch('/movie/1/preview/%2fsecret.mp4')
        )

    def test_get_preview_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self, self.fetch(f'/movie/1/preview/{_FAKE_ESCAPE_LINK}/secret.mp4')
        )

    # --- POST delete: filename ---

    def test_post_delete_rejects_traversal(self):
        _assert_traversal_403(
            self,
            self.fetch('/movie/1/delete/../../secret.mp4', method='POST', body=''),
        )
        _assert_traversal_403(
            self,
            self.fetch('/movie/1/delete/%2e%2e/secret.mp4', method='POST', body=''),
        )

    def test_post_delete_rejects_absolute_path(self):
        _assert_absolute_path_403(
            self,
            self.fetch('/movie/1/delete/%2fsecret.mp4', method='POST', body=''),
        )

    def test_post_delete_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self,
            self.fetch(
                f'/movie/1/delete/{_FAKE_ESCAPE_LINK}/secret.mp4',
                method='POST',
                body='',
            ),
        )

    # --- POST delete_all: group ---

    def test_post_delete_all_rejects_traversal(self):
        _assert_traversal_403(
            self, self.fetch('/movie/1/delete_all/../', method='POST', body='')
        )
        _assert_traversal_403(
            self, self.fetch('/movie/1/delete_all/%2e%2e/', method='POST', body='')
        )

    def test_post_delete_all_rejects_absolute_path(self):
        _assert_absolute_path_403(
            self,
            self.fetch('/movie/1/delete_all/%2fetc/', method='POST', body=''),
        )

    def test_post_delete_all_rejects_dir_escape(self):
        _assert_dir_escape_403(
            self,
            self.fetch(
                f'/movie/1/delete_all/{_FAKE_ESCAPE_LINK}/', method='POST', body=''
            ),
        )


if __name__ == '__main__':
    tornado.testing.main()
