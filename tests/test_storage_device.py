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

from motioneye import config
from tests.test_notification_settings import _ConfigCase


class StorageDeviceTest(_ConfigCase):
    def setUp(self):
        super().setUp()
        self.camera['target_dir'] = '/var/lib/motioneye/Camera1'

    def _post(self, ui_changes):
        # POST /config/1/set/, see handlers/config.py
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(ui_changes)
        return config.motion_camera_ui_to_dict(ui, self.camera)

    def test_null_or_empty_is_refused(self):
        for ui_changes in ({'storage_device': None}, {'storage_device': ''}):
            refused = self.assertRaisesRegex(ValueError, 'storage_device')
            with self.subTest(**ui_changes), refused:
                self._post(ui_changes)

    def test_missing_is_refused(self):
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.pop('storage_device')
        with self.assertRaisesRegex(ValueError, 'storage_device'):
            config.motion_camera_ui_to_dict(ui, self.camera)

    def test_a_given_storage_device_is_used(self):
        self.camera['@storage_device'] = 'network-share'
        data = self._post({'storage_device': 'custom-path'})
        self.assertEqual('custom-path', data['@storage_device'])


class InputRequiredTest(unittest.TestCase):
    def test_set_values_are_returned(self):
        for value in ('custom-path', False, 0):
            with self.subTest(value=value):
                self.assertIs(value, config.input_required({'key': value}, 'key'))

    def test_unset_values_are_refused(self):
        for ui in ({}, {'key': None}, {'key': ''}):
            refused = self.assertRaisesRegex(ValueError, '"key" must be set')
            with self.subTest(ui=ui), refused:
                config.input_required(ui, 'key')


if __name__ == '__main__':
    unittest.main()
