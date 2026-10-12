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

_PARTITION = {'target': '/dev/sda1', 'mount_point': '/media/usb'}


class LocalDiskTest(_ConfigCase):
    def setUp(self):
        super().setUp()
        self.camera['@storage_device'] = 'local-disk-dev-sda1'
        self.camera['target_dir'] = '/media/usb/Camera1'
        self.partitions = self._patch(
            'motioneye.controls.diskctl.list_mounted_partitions', return_value={}
        )

    def _round_trip(self):
        # GET /config/1/get/ and POST the same settings back to /config/1/set/
        ui = config.motion_camera_dict_to_ui(self.camera)
        return config.motion_camera_ui_to_dict(ui, self.camera)

    def test_mounted_disk_round_trips(self):
        self.partitions.return_value = {'/dev/sda1': _PARTITION}
        data = self._round_trip()
        self.assertEqual('local-disk-dev-sda1', data['@storage_device'])
        self.assertEqual('/media/usb/Camera1', data['target_dir'])

    def test_unmounted_disk_keeps_the_target_dir(self):
        data = self._round_trip()
        self.assertEqual('local-disk-dev-sda1', data['@storage_device'])
        self.assertEqual('/media/usb/Camera1', data['target_dir'])

    def test_disk_unmounted_after_the_settings_were_opened(self):
        self.partitions.return_value = {'/dev/sda1': _PARTITION}
        ui = config.motion_camera_dict_to_ui(self.camera)
        self.assertEqual('/Camera1', ui['root_directory'])  # relative to the mount

        self.partitions.return_value = {}
        data = config.motion_camera_ui_to_dict(ui, self.camera)
        self.assertEqual('local-disk-dev-sda1', data['@storage_device'])
        self.assertEqual('/media/usb/Camera1', data['target_dir'])


if __name__ == '__main__':
    unittest.main()
