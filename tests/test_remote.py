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

"""Tests verifying that path traversal elements are rejected in remote module functions."""

import unittest

from motioneye import remote


class TestRemotePathTraversal(unittest.IsolatedAsyncioTestCase):
    """Tests verifying that path traversal elements are rejected in remote functions.

    Each remote function performs its path traversal check synchronously before
    any network I/O, so awaiting the coroutine raises immediately.
    """

    _LOCAL_CONFIG = {
        '@proto': 'mjpeg',
        '@host': '127.0.0.1',
        '@port': 8765,
        '@username': '',
        '@password': '',
        '@path': '',
        '@remote_camera_id': 1,
    }

    # Traversal inputs to test for filenames/paths and groups/prefixes.
    _FILENAME_TRAVERSALS = [
        '../etc/passwd',
        '../../etc/passwd',
        'subdir/../../../etc/passwd',
        '../secret.jpg',
    ]
    _GROUP_TRAVERSALS = [
        '..',
        '../group',
        'subdir/..',
        'subdir/../../other',
    ]
    _PREFIX_TRAVERSALS = [
        '..',
        '../prefix',
        'prefix/../..',
    ]

    def _assert_raises_path_traversal(self, exception):
        self.assertIn('Path traversal', str(exception))

    async def test_list_media_rejects_prefix_traversal(self):
        for prefix in self._PREFIX_TRAVERSALS:
            with self.subTest(prefix=prefix):
                with self.assertRaises(Exception) as ctx:
                    await remote.list_media(
                        self._LOCAL_CONFIG, 'picture', prefix=prefix
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_media_content_rejects_traversal(self):
        for filename in self._FILENAME_TRAVERSALS:
            with self.subTest(filename=filename):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_media_content(
                        self._LOCAL_CONFIG, filename, 'picture'
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_make_zipped_content_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.make_zipped_content(
                        self._LOCAL_CONFIG, 'picture', group
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_zipped_content_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_zipped_content(
                        self._LOCAL_CONFIG, 'picture', 'key123', group
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_make_timelapse_movie_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.make_timelapse_movie(self._LOCAL_CONFIG, 2, 1, group)
                self._assert_raises_path_traversal(ctx.exception)

    async def test_check_timelapse_movie_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.check_timelapse_movie(self._LOCAL_CONFIG, group)
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_timelapse_movie_rejects_group_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_timelapse_movie(
                        self._LOCAL_CONFIG, 'key123', group
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_get_media_preview_rejects_traversal(self):
        for filename in self._FILENAME_TRAVERSALS:
            with self.subTest(filename=filename):
                with self.assertRaises(Exception) as ctx:
                    await remote.get_media_preview(
                        self._LOCAL_CONFIG, filename, 'picture', None, None
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_del_media_content_rejects_traversal(self):
        for filename in self._FILENAME_TRAVERSALS:
            with self.subTest(filename=filename):
                with self.assertRaises(Exception) as ctx:
                    await remote.del_media_content(
                        self._LOCAL_CONFIG, filename, 'picture'
                    )
                self._assert_raises_path_traversal(ctx.exception)

    async def test_del_media_group_rejects_traversal(self):
        for group in self._GROUP_TRAVERSALS:
            with self.subTest(group=group):
                with self.assertRaises(Exception) as ctx:
                    await remote.del_media_group(self._LOCAL_CONFIG, group, 'picture')
                self._assert_raises_path_traversal(ctx.exception)


if __name__ == '__main__':
    unittest.main()
