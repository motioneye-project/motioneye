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

import unittest
from base64 import b64encode

from motioneye import config
from tests.test_notification_settings import _ConfigCase

_KEY = b64encode(bytes(range(32))).decode()


class SseCKeyTest(_ConfigCase):
    """Saving S3 uploads with an encryption key S3 would refuse fails at once,
    instead of every upload failing later (#3574)."""

    def setUp(self):
        super().setUp()
        self.updates = self._patch('motioneye.tasks.add')

    def _save_upload(self, key, service='s3', enabled=True):
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(upload_enabled=enabled, upload_service=service, upload_sse_c_key=key)
        return config.motion_camera_ui_to_dict(ui, self.camera)

    def test_a_valid_key_is_saved_without_surrounding_space(self):
        data = self._save_upload(f' {_KEY}\n')
        self.assertEqual(_KEY, data['@upload_sse_c_key'])

    def test_no_key_means_no_encryption(self):
        self.assertEqual('', self._save_upload('')['@upload_sse_c_key'])

    def test_a_key_s3_refuses_is_not_saved_and_not_shown(self):
        for key in (
            'my secret password',
            b64encode(bytes(16)).decode(),  # AES-128
            bytes(32).hex(),  # openssl rand -hex 32
            _KEY[:-1],  # padding lost when pasted
        ):
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValueError, '32 bytes in base64') as raised,
            ):
                self._save_upload(key)

            self.assertNotIn(key, str(raised.exception))

    def test_only_s3_uploads_check_the_key(self):
        # the field is hidden for the other services, so a stale value stays
        for service, enabled in (('ftp', True), ('s3', False)):
            with self.subTest(service=service, enabled=enabled):
                data = self._save_upload('stale', service=service, enabled=enabled)
                self.assertEqual('stale', data['@upload_sse_c_key'])


if __name__ == '__main__':
    unittest.main()
