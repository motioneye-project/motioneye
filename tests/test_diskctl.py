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
        with (
            patch(
                'motioneye.controls.diskctl.open',
                mock_open(read_data=self._PROC_MOUNTS),
            ),
            patch('motioneye.controls.diskctl.os.access', return_value=False),
        ):
            mounts = diskctl._list_mounts()

        targets = [m['target'] for m in mounts]
        self.assertIn('/dev/sda1', targets)
        self.assertIn('/dev/sdb1', targets)
        # ... but each is flagged as not writable so the UI can warn (#3024)
        self.assertTrue(all(m['writable'] is False for m in mounts))

    def test_deduplicates_bind_mounts(self):
        with (
            patch(
                'motioneye.controls.diskctl.open',
                mock_open(read_data=self._PROC_MOUNTS),
            ),
            patch('motioneye.controls.diskctl.os.access', return_value=True),
        ):
            mounts = diskctl._list_mounts()

        # the second /dev/sdb1 entry (a bind mount) is collapsed
        self.assertEqual([m['target'] for m in mounts].count('/dev/sdb1'), 1)
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(m['writable'] is True for m in mounts))


class FreeBSDMountTableTest(unittest.TestCase):
    # "mount -p" on FreeBSD 15.1, which has no /proc/mounts (#1616)
    _MOUNT_P = (
        'zroot/ROOT/default\t/\t\t\tzfs\trw,nfsv4acls \t0 0\n'
        'devfs\t\t\t/dev\t\t\tdevfs\trw\t\t0 0\n'
        '/dev/da0p1\t\t/media/usb\t\tmsdosfs\trw\t\t0 0\n'
    )

    def _without_proc_mounts(self):
        return patch('motioneye.controls.diskctl.open', side_effect=FileNotFoundError)

    def test_mounts_are_read_with_mount_p(self):
        with (
            self._without_proc_mounts(),
            patch(
                'motioneye.controls.diskctl.utils.call_subprocess',
                return_value=self._MOUNT_P,
            ) as call,
            patch('motioneye.controls.diskctl.os.access', return_value=True),
        ):
            mounts = diskctl._list_mounts()

        call.assert_called_once_with(['mount', '-p'])
        self.assertEqual(
            [
                ('zroot/ROOT/default', '/', 'zfs'),
                ('devfs', '/dev', 'devfs'),
                ('/dev/da0p1', '/media/usb', 'msdosfs'),
            ],
            [(m['target'], m['mount_point'], m['fstype']) for m in mounts],
        )


class FreeBSDDisksTest(unittest.TestCase):
    # from FreeBSD 15.1, trimmed, with md0 a memory disk and da0 a USB stick, and
    # the descr of vtbd0 from FreeBSD 14.3
    _GEOM_DISK_LIST = """Geom name: vtbd0
Providers:
1. Name: vtbd0
   Mediasize: 221225156608 (206G)
   Sectorsize: 512
   descr: (null)
   ident:

Geom name: cd0
Providers:
1. Name: cd0
   Mediasize: 0 (0B)
   descr: QEMU QEMU DVD-ROM

Geom name: da0
Providers:
1. Name: da0
   Mediasize: 31406948352 (29G)
   descr: SanDisk Ultra
"""
    _GEOM_PART_LIST = """Geom name: vtbd0
modified: false
scheme: GPT
Providers:
1. Name: vtbd0p1
   Mediasize: 177664 (174K)
   label: bootfs
   type: freebsd-boot
   index: 1
2. Name: vtbd0p2
   Mediasize: 34091008 (33M)
   label: efiboot0
   type: efi
   index: 2
Consumers:
1. Name: vtbd0
   Mediasize: 221225156608 (206G)

Geom name: md0
scheme: GPT
Providers:
1. Name: md0p1
   Mediasize: 67067904 (64M)
   label: camdata
   type: ms-basic-data
   index: 1
Consumers:
1. Name: md0
"""
    _GLABEL_STATUS = (
        '                                gpt/bootfs     N/A  vtbd0p1\n'
        'gptid/b1767c30-6654-11f1-067b-ff9d86f8dced     N/A  vtbd0p1\n'
        '                              gpt/efiboot0     N/A  vtbd0p2\n'
        '                              msdosfs/CAMS     N/A  md0p1\n'
    )
    _MOUNT_P = (
        'zroot/ROOT/default\t/\t\t\tzfs\trw,nfsv4acls \t0 0\n'
        '/dev/gpt/efiboot0\t/boot/efi\t\tmsdosfs\trw\t\t2 2\n'
        '/dev/msdosfs/CAMS\t/media/a\t\tmsdosfs\trw\t\t0 0\n'
        '/dev/da0\t\t/media/usb\t\tufs\trw\t\t2 2\n'
    )

    def _call(self, args):
        return {
            ('geom', 'disk', 'list'): self._GEOM_DISK_LIST,
            ('geom', 'part', 'list'): self._GEOM_PART_LIST,
            ('glabel', 'status', '-s'): self._GLABEL_STATUS,
            ('mount', '-p'): self._MOUNT_P,
        }[tuple(args)]

    def setUp(self):
        for target, kwargs in (
            ('sys.platform', {'new': 'freebsd15'}),
            ('os.path.exists', {'return_value': False}),
            ('open', {'side_effect': FileNotFoundError}),
            ('utils.call_subprocess', {'side_effect': self._call}),
            ('os.access', {'return_value': True}),
        ):
            patcher = patch(f'motioneye.controls.diskctl.{target}', **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_disks_are_listed_with_geom(self):
        disks = diskctl._list_disks()

        self.assertEqual(
            [
                ('/dev/da0', 'SanDisk Ultra', ['/dev/da0']),
                ('/dev/md0', '', ['/dev/md0p1']),
                ('/dev/vtbd0', '', ['/dev/vtbd0p1', '/dev/vtbd0p2']),
            ],
            [
                (d['target'], d['vendor'], [p['target'] for p in d['partitions']])
                for d in disks
            ],
        )

    def test_partitions_mounted_by_label_are_found(self):
        partitions = diskctl.list_mounted_partitions()

        # by the partition, not the label, so that the storage device stays the
        # same however it is mounted
        self.assertEqual(
            {
                '/dev/da0': '/media/usb',
                '/dev/md0p1': '/media/a',
                '/dev/vtbd0p2': '/boot/efi',
            },
            {t: p['mount_point'] for t, p in partitions.items()},
        )
        self.assertTrue(all(t == p['target'] for t, p in partitions.items()))


if __name__ == '__main__':
    unittest.main()
