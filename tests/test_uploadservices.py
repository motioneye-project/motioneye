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

import os
import unittest
from unittest.mock import MagicMock, patch

from motioneye import uploadservices


class TestUploadMediaFileCleanup(unittest.TestCase):
    """Tests for the optional "remove after successful upload" behaviour of
    uploadservices.upload_media_file (the @clean_uploaded option, see #3089).

    The caller (relay handler) passes clean_uploaded, so the cleanup branch -
    including the camera config lookup and the mediafiles import - must be
    skipped entirely when it is False."""

    def setUp(self):
        self.target_dir = os.path.join(os.sep + 'data', 'cam1')
        self.filename = os.path.join(self.target_dir, '2024-01-01', 'movie.mp4')
        self.expected_rel = os.path.join('2024-01-01', 'movie.mp4')

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices.get')
    def test_removes_local_file_on_success_when_enabled(
        self, mock_get, mock_get_camera, mock_del
    ):
        mock_get.return_value = MagicMock()  # upload_file() succeeds
        camera_config = {'target_dir': self.target_dir}
        mock_get_camera.return_value = camera_config

        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            'movie',
            clean_uploaded=True,
        )

        mock_del.assert_called_once_with(camera_config, self.expected_rel, 'movie')

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices.get')
    def test_keeps_local_file_when_disabled(self, mock_get, mock_get_camera, mock_del):
        mock_get.return_value = MagicMock()

        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            'movie',
            clean_uploaded=False,
        )

        # the common path must not even look up the camera config
        mock_get_camera.assert_not_called()
        mock_del.assert_not_called()

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices.get')
    def test_keeps_local_file_when_upload_fails(
        self, mock_get, mock_get_camera, mock_del
    ):
        service = MagicMock()
        service.upload_file.side_effect = Exception('upload boom')
        mock_get.return_value = service

        # a failed upload must not raise and must not delete the local file
        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            'movie',
            clean_uploaded=True,
        )

        mock_get_camera.assert_not_called()
        mock_del.assert_not_called()

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.uploadservices.get')
    def test_no_cleanup_when_service_missing(self, mock_get, mock_del):
        mock_get.return_value = None

        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            'movie',
            clean_uploaded=True,
        )

        mock_del.assert_not_called()

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices.get')
    def test_cleanup_error_does_not_propagate(
        self, mock_get, mock_get_camera, mock_del
    ):
        mock_get.return_value = MagicMock()
        mock_get_camera.return_value = {'target_dir': self.target_dir}
        mock_del.side_effect = Exception('disk error')

        # a cleanup error must never affect the (already successful) upload
        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            'movie',
            clean_uploaded=True,
        )

        mock_del.assert_called_once()


if __name__ == '__main__':
    unittest.main()
