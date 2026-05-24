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
import tarfile
import unittest
from io import BytesIO
from shutil import rmtree
from tempfile import mkdtemp

from motioneye import config, settings


class TestBackup(unittest.TestCase):
    """Tests for config.backup()."""

    conf_dir: str

    @classmethod
    def setUpClass(cls):
        cls.conf_dir = mkdtemp()
        cls._orig_conf_path = settings.CONF_PATH
        settings.CONF_PATH = cls.conf_dir

    @classmethod
    def tearDownClass(cls):
        settings.CONF_PATH = cls._orig_conf_path
        rmtree(cls.conf_dir)

    def setUp(self):
        # Clean the config dir before each test
        for name in os.listdir(self.conf_dir):
            os.remove(os.path.join(self.conf_dir, name))

    def _write(self, filename, content=b''):
        path = os.path.join(self.conf_dir, filename)
        with open(path, 'wb') as f:
            f.write(content)

    def _get_tarball_names(self, data: bytes) -> list:
        with tarfile.open(fileobj=BytesIO(data)) as tf:
            return tf.getnames()

    def _assert_tarball_members(self, data: bytes, expected: list[str]):
        self.assertEqual(sorted(self._get_tarball_names(data)), sorted(expected))

    def test_backup_includes_motion_conf(self):
        self._write('motion.conf', b'[motion]\n')

        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_includes_camera_confs(self):
        self._write('camera-1.conf', b'camera 1\n')
        self._write('camera-2.conf', b'camera 2\n')

        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, ['camera-1.conf', 'camera-2.conf'])

    def test_backup_includes_mask_files(self):
        self._write('mask_1.pgm', b'P5\n')
        self._write('mask_2.pgm', b'P5\n')

        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, ['mask_1.pgm', 'mask_2.pgm'])

    def test_backup_includes_prefs_json(self):
        self._write('prefs.json', b'{}')

        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, ['prefs.json'])

    def test_backup_excludes_other_files(self):
        self._write('motion.conf', b'[motion]\n')
        self._write('uploadservices.json', b'{}')
        self._write('secrets.json', b'{}')
        self._write('motioneye.conf', b'secret=password\n')

        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_omits_missing_mask_files(self):
        self._write('motion.conf', b'[motion]\n')
        # mask_*.pgm intentionally not created

        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_omits_missing_prefs_json(self):
        self._write('motion.conf', b'[motion]\n')
        # prefs.json intentionally not created

        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_empty_dir_returns_empty_tarball(self):
        data = config.backup()
        self.assertIsNotNone(data)
        self._assert_tarball_members(data, [])


class TestRestore(unittest.TestCase):
    """Tests for config.restore()."""

    conf_dir: str

    @classmethod
    def setUpClass(cls):
        cls.conf_dir = mkdtemp()
        cls._orig_conf_path = settings.CONF_PATH
        cls._orig_enable_reboot = settings.ENABLE_REBOOT
        settings.CONF_PATH = cls.conf_dir
        settings.ENABLE_REBOOT = False

    @classmethod
    def tearDownClass(cls):
        settings.CONF_PATH = cls._orig_conf_path
        settings.ENABLE_REBOOT = cls._orig_enable_reboot
        rmtree(cls.conf_dir)

    def setUp(self):
        # Clean the config dir before each test
        for name in os.listdir(self.conf_dir):
            os.remove(os.path.join(self.conf_dir, name))

    def _make_tarball(self, files: dict) -> bytes:
        """Create an in-memory .tar.gz with the given filename->content mapping."""
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tf:
            for name, content in files.items():
                data = content if isinstance(content, bytes) else content.encode()
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tf.addfile(info, BytesIO(data))
        return buf.getvalue()

    def _make_tarball_members(
        self, members: list[tuple[tarfile.TarInfo, bytes | None]]
    ) -> bytes:
        """Create an in-memory .tar.gz with raw tar members."""
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tf:
            for info, content in members:
                if content is None:
                    tf.addfile(info)
                    continue

                data = content if isinstance(content, bytes) else content.encode()
                info.size = len(data)
                tf.addfile(info, BytesIO(data))
        return buf.getvalue()

    def _assert_restored_files(self, expected: list[str]):
        self.assertEqual(sorted(os.listdir(self.conf_dir)), sorted(expected))

    def test_restore_extracts_motion_conf(self):
        content = b'[motion]\ndaemon = on\n'
        tarball = self._make_tarball({'motion.conf': content})

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['motion.conf'])
        with open(os.path.join(self.conf_dir, 'motion.conf'), 'rb') as f:
            self.assertEqual(f.read(), content)

    def test_restore_extracts_camera_confs(self):
        tarball = self._make_tarball(
            {
                'camera-1.conf': b'camera 1',
                'camera-42.conf': b'camera 42',
            }
        )

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['camera-1.conf', 'camera-42.conf'])

    def test_restore_extracts_mask_files(self):
        tarball = self._make_tarball(
            {
                'mask_1.pgm': b'P5\n',
                'mask_2.pgm': b'P5\n',
            }
        )

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['mask_1.pgm', 'mask_2.pgm'])

    def test_restore_extracts_prefs_json(self):
        tarball = self._make_tarball({'prefs.json': b'{}'})

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['prefs.json'])

    def test_restore_ignores_non_matching_files(self):
        tarball = self._make_tarball(
            {
                'motion.conf': b'[motion]\n',
                'uploadservices.json': b'{}',
                'secrets.json': b'{}',
                'motioneye.conf': b'secret=password\n',
            }
        )

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['motion.conf'])

    def test_restore_ignores_non_regular_members(self):
        camera_symlink_info = tarfile.TarInfo(name='camera-9.conf')
        camera_symlink_info.type = tarfile.SYMTYPE
        camera_symlink_info.linkname = 'motion.conf'

        mask_hardlink_info = tarfile.TarInfo(name='mask_9.pgm')
        mask_hardlink_info.type = tarfile.LNKTYPE
        mask_hardlink_info.linkname = 'motion.conf'

        tarball = self._make_tarball_members(
            [
                (tarfile.TarInfo(name='motion.conf'), b'[motion]\n'),
                (camera_symlink_info, None),
                (mask_hardlink_info, None),
            ]
        )

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['motion.conf'])

    def test_restore_ignores_absolute_paths(self):
        tarball = self._make_tarball(
            {
                '/motion.conf': b'ignored',
                '/camera-1.conf': b'ignored',
                '/mask_1.pgm': b'ignored',
                '/prefs.json': b'ignored',
                'motion.conf': b'[motion]\n',
            }
        )

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['motion.conf'])

    def test_restore_ignores_pattern_matches_with_path_elements(self):
        tarball = self._make_tarball(
            {
                'camera-1.conf': b'camera 1',
                'mask_1.pgm': b'P5\n',
                'subdir/camera-2.conf': b'ignored',
                'camera-3.conf/extra': b'ignored',
                './subdir/camera-4.conf': b'ignored',
                '../camera-5.conf': b'ignored',
                'subdir/mask_2.pgm': b'ignored',
                './subdir/mask_3.pgm': b'ignored',
                '../mask_4.pgm': b'ignored',
            }
        )

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['camera-1.conf', 'mask_1.pgm'])

    def test_restore_accepts_dot_slash_prefix(self):
        """Tarball entries prefixed with ./ (e.g. from GNU tar) should still be accepted."""
        tarball = self._make_tarball({'./motion.conf': b'[motion]\n'})

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self._assert_restored_files(['motion.conf'])

    def test_restore_returns_reboot_false(self):
        tarball = self._make_tarball({'motion.conf': b'[motion]\n'})

        result = config.restore(tarball)
        self.assertIsNotNone(result)
        self.assertEqual(result, {'reboot': False})

    def test_restore_invalid_data_returns_none(self):
        result = config.restore(b'not a tarball')
        self.assertIsNone(result)
