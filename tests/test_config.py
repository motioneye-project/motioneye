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
from typing import Optional

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

    def _create_files(self, *names: str) -> None:
        for name in names:
            open(os.path.join(self.conf_dir, name), 'a').close()

    def _assert_tarball_members(
        self, data: Optional[bytes], expected: list[str]
    ) -> None:
        if data is None:
            self.fail('tarball data is None')

        with tarfile.open(fileobj=BytesIO(data)) as tf:
            members = tf.getnames()
        self.assertEqual(sorted(members), sorted(expected))

    def test_backup_includes_motion_conf(self):
        self._create_files('motion.conf')

        data = config.backup()
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_includes_camera_confs(self):
        self._create_files('camera-1.conf', 'camera-2.conf')

        data = config.backup()
        self._assert_tarball_members(data, ['camera-1.conf', 'camera-2.conf'])

    def test_backup_includes_mask_files(self):
        self._create_files('mask_1.pgm', 'mask_2.pgm')

        data = config.backup()
        self._assert_tarball_members(data, ['mask_1.pgm', 'mask_2.pgm'])

    def test_backup_includes_prefs_json(self):
        self._create_files('prefs.json')

        data = config.backup()
        self._assert_tarball_members(data, ['prefs.json'])

    def test_backup_excludes_other_files(self):
        self._create_files(
            'motion.conf',
            'uploadservices.json',
            'secrets.json',
            'motioneye.conf',
        )

        data = config.backup()
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_empty_dir_returns_empty_tarball(self):
        data = config.backup()
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

    def _make_tarball(self, *names: str) -> bytes:
        """Create an in-memory .tar.gz with the given file names as empty members."""
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tf:
            for name in names:
                member = tarfile.TarInfo(name)
                member.size = 0
                tf.addfile(member)
        return buf.getvalue()

    def _make_tarball_members(self, *members: tarfile.TarInfo) -> bytes:
        """Create an in-memory .tar.gz with the given raw members."""
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tf:
            for member in members:
                tf.addfile(member)
        return buf.getvalue()

    def _assert_restored_files(self, *expected: str) -> None:
        self.assertEqual(sorted(os.listdir(self.conf_dir)), sorted(expected))

    def test_restore_extracts_motion_conf(self):
        tarball = self._make_tarball('motion.conf')

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_extracts_camera_confs(self):
        tarball = self._make_tarball('camera-1.conf', 'camera-42.conf')

        config.restore(tarball)
        self._assert_restored_files('camera-1.conf', 'camera-42.conf')

    def test_restore_extracts_mask_files(self):
        tarball = self._make_tarball('mask_1.pgm', 'mask_2.pgm')

        config.restore(tarball)
        self._assert_restored_files('mask_1.pgm', 'mask_2.pgm')

    def test_restore_extracts_prefs_json(self):
        tarball = self._make_tarball('prefs.json')

        config.restore(tarball)
        self._assert_restored_files('prefs.json')

    def test_restore_ignores_non_matching_files(self):
        tarball = self._make_tarball(
            'motion.conf',
            'uploadservices.json',
            'secrets.json',
            'motioneye.conf',
        )

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_ignores_non_regular_members(self):
        motion_config = tarfile.TarInfo(name='motion.conf')
        motion_config.size = 0

        camera_symlink = tarfile.TarInfo(name='camera-9.conf')
        camera_symlink.type = tarfile.SYMTYPE
        camera_symlink.linkname = 'motion.conf'

        mask_hardlink = tarfile.TarInfo(name='mask_9.pgm')
        mask_hardlink.type = tarfile.LNKTYPE
        mask_hardlink.linkname = 'motion.conf'

        tarball = self._make_tarball_members(
            motion_config, camera_symlink, mask_hardlink
        )

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_ignores_absolute_paths(self):
        tarball = self._make_tarball(
            '/motion.conf',
            '/camera-1.conf',
            '/mask_1.pgm',
            '/prefs.json',
            'motion.conf',
        )

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_ignores_pattern_matches_with_path_elements(self):
        tarball = self._make_tarball(
            'camera-1.conf',
            'mask_1.pgm',
            'subdir/camera-2.conf',
            'camera-3.conf/extra',
            './subdir/camera-4.conf',
            '../camera-5.conf',
            'subdir/mask_2.pgm',
            './subdir/mask_3.pgm',
            '../mask_4.pgm',
        )

        config.restore(tarball)
        self._assert_restored_files('camera-1.conf', 'mask_1.pgm')

    def test_restore_accepts_dot_slash_prefix(self):
        """Tarball entries prefixed with ./ (e.g. from GNU tar) should still be accepted."""
        tarball = self._make_tarball('./motion.conf')

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_returns_reboot_false(self):
        tarball = self._make_tarball('motion.conf')

        result = config.restore(tarball)
        self.assertEqual(result, {'reboot': False})

    def test_restore_invalid_data_returns_none(self):
        result = config.restore(b'not a tarball')
        self.assertIsNone(result)
