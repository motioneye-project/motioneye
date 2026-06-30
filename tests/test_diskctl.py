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
from unittest.mock import mock_open, patch

from motioneye.controls import diskctl


class ListMountsTest(unittest.TestCase):
    _PROC_MOUNTS = (
        '/dev/sda1 /media/usb ext4 rw,relatime 0 0\n'
        '/dev/sdb1 /media/usb2 vfat rw,relatime 0 0\n'
        '/dev/sdb1 /media/bind ext4 rw,relatime 0 0\n'  # duplicate target (bind)
    )

    def test_includes_mounts_without_write_access(self):
        # a drive the motion user cannot write to used to be filtered out on a
        # missing os.W_OK, so it never appeared as a storage device (#3024)
        with patch(
            'motioneye.controls.diskctl.open', mock_open(read_data=self._PROC_MOUNTS)
        ), patch('motioneye.controls.diskctl.os.access', return_value=False):
            mounts = diskctl._list_mounts()

        targets = [m['target'] for m in mounts]
        self.assertIn('/dev/sda1', targets)
        self.assertIn('/dev/sdb1', targets)
        # ... but each is flagged as not writable so the UI can warn (#3024)
        self.assertTrue(all(m['writable'] is False for m in mounts))

    def test_deduplicates_bind_mounts(self):
        with patch(
            'motioneye.controls.diskctl.open', mock_open(read_data=self._PROC_MOUNTS)
        ), patch('motioneye.controls.diskctl.os.access', return_value=True):
            mounts = diskctl._list_mounts()

        # the second /dev/sdb1 entry (a bind mount) is collapsed
        self.assertEqual([m['target'] for m in mounts].count('/dev/sdb1'), 1)
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(m['writable'] is True for m in mounts))


if __name__ == '__main__':
    unittest.main()
