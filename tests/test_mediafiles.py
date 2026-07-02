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
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from time import time
from unittest.mock import patch

from motioneye import mediafiles
from motioneye.mediafiles import _list_media_files


class TestMediaFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create a temporary directory structure for testing."""
        cls.test_dir = mkdtemp()

        # Create some subdirectories (like date-based groups)
        # Also create nested subdirectories to test recursion
        date1 = os.path.join(cls.test_dir, '2024-01-01')
        date2 = os.path.join(cls.test_dir, '2024-01-02')
        nested1 = os.path.join(cls.test_dir, 'level1_dir')
        nested2 = os.path.join(nested1, 'level2_dir')
        nested3 = os.path.join(nested2, 'level3_dir')
        os.makedirs(date1)
        os.makedirs(date2)
        os.makedirs(nested3)

        # Create movie files at various levels
        cls.movie_files = [
            os.path.join(cls.test_dir, 'root_movie1.mp4'),
            os.path.join(cls.test_dir, 'root_movie2.avi'),
            os.path.join(date1, 'movie3.mp4'),
            os.path.join(date1, 'movie4.mkv'),
            os.path.join(date2, 'movie5.mp4'),
            os.path.join(nested1, 'level1_movie.mp4'),
            os.path.join(nested2, 'level2_movie.mp4'),
            os.path.join(nested3, 'level3_movie.mp4'),
        ]

        # Create picture files at various levels
        cls.picture_files = [
            os.path.join(cls.test_dir, 'root_picture1.jpg'),
            os.path.join(date1, 'picture2.jpg'),
            os.path.join(date2, 'picture3.jpg'),
            os.path.join(nested1, 'level1_picture.jpg'),
        ]

        # Create files that should be ignored
        cls.ignored_files = [
            os.path.join(cls.test_dir, '.hidden'),
            os.path.join(cls.test_dir, 'lastsnap.jpg'),
            os.path.join(date1, '.dotfile'),
        ]

        # Create non-media files that should also be ignored
        cls.non_media_files = [
            os.path.join(cls.test_dir, 'readme.txt'),
            os.path.join(cls.test_dir, 'debug.log'),
            os.path.join(date1, 'notes.txt'),
            os.path.join(nested1, 'config.log'),
            os.path.join(nested2, 'info.txt'),
        ]

        all_files = (
            cls.movie_files
            + cls.picture_files
            + cls.ignored_files
            + cls.non_media_files
        )
        for f in all_files:
            Path(f).touch()

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary files and directories."""
        if os.path.exists(cls.test_dir):
            rmtree(cls.test_dir)

    def test_list_media_files_recursive_all_files(self):
        """Test that _list_media_files returns all regular files recursively when no sub_path is given."""
        # Pass all extensions to find all files
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
        result = _list_media_files(self.test_dir, all_exts)

        # Extract just the file paths from the result tuples
        result_paths = sorted([path for path, st in result])

        # Should find all non-ignored files
        expected_files = sorted(self.movie_files + self.picture_files)
        self.assertEqual(result_paths, expected_files)

    def test_list_media_files_return_structure(self):
        """Test that _list_media_files returns tuples with (path, stat)."""
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']

        # Test default behavior (with_stat=True by default)
        result = _list_media_files(self.test_dir, all_exts)
        for item in result:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            path, st = item
            self.assertTrue(os.path.isfile(path))
            self.assertIsNotNone(st)
            self.assertTrue(hasattr(st, 'st_mtime'))  # Check it's a stat object
            self.assertTrue(hasattr(st, 'st_size'))

        # Test with_stat=False
        result_no_stat = _list_media_files(self.test_dir, all_exts, with_stat=False)
        for item in result_no_stat:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            path, st = item
            self.assertTrue(os.path.isfile(path))
            self.assertIsNone(st)  # stat should be None when with_stat=False

    def test_list_media_files_filter_by_movie_extensions(self):
        """Test listing movie files with correct extensions."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        result = _list_media_files(self.test_dir, movie_exts)

        # Extract just the file paths
        result_paths = sorted([path for path, st in result])

        # Should find only movie files
        expected_files = sorted(self.movie_files)
        self.assertEqual(result_paths, expected_files)

    def test_list_media_files_filter_by_picture_extensions(self):
        """Test listing picture files with correct extensions."""
        picture_exts = ['.jpg']
        result = _list_media_files(self.test_dir, picture_exts)

        # Extract just the file paths
        result_paths = sorted([path for path, st in result])

        # Should find only picture files
        expected_files = sorted(self.picture_files)
        self.assertEqual(result_paths, expected_files)

    def test_list_media_files_non_recursive_with_sub_path(self):
        """Test listing media files with a sub_path (non-recursive)."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        # Test with a specific date sub_path
        result = _list_media_files(self.test_dir, movie_exts, sub_path='2024-01-01')

        result_paths = sorted([path for path, st in result])

        # Should only find files in the 2024-01-01 directory (not in subdirectories of it)
        expected_files = sorted(
            [f for f in self.movie_files if os.path.dirname(f).endswith('2024-01-01')]
        )
        self.assertEqual(result_paths, expected_files)

    def test_list_media_files_ungrouped_sub_path(self):
        """Test listing media files with 'ungrouped' sub_path."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        # 'ungrouped' should translate to empty string sub_path
        result = _list_media_files(self.test_dir, movie_exts, sub_path='ungrouped')

        result_paths = sorted([path for path, st in result])

        # Should find files in the root directory only (not in subdirectories)
        expected_files = sorted(
            [f for f in self.movie_files if os.path.dirname(f) == self.test_dir]
        )
        self.assertEqual(result_paths, expected_files)

    def test_list_media_files_nonexistent_sub_path(self):
        """Test listing media files with a non-existent sub_path."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        result = _list_media_files(self.test_dir, movie_exts, sub_path='nonexistent')

        # Should return empty list
        self.assertEqual(len(result), 0)

    def test_list_media_files_empty_directory(self):
        """Test _list_media_files on an empty directory."""
        # Create a new empty directory for this test
        empty_dir = mkdtemp()
        try:
            all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
            result = _list_media_files(empty_dir, all_exts)
            self.assertEqual(len(result), 0)
        finally:
            rmtree(empty_dir)

    def test_list_media_files_performance_with_many_files(self):
        """Test that the optimized version can handle many files efficiently."""
        # Create a temporary directory for this test
        perf_test_dir = mkdtemp()
        try:
            num_files = 1000
            for i in range(num_files):
                Path(os.path.join(perf_test_dir, f'movie{i}.mp4')).touch()

            # Measure time to list all files
            start_time = time()
            result = _list_media_files(perf_test_dir, ['.mp4'])
            elapsed_time = time() - start_time

            # Should find all files
            self.assertEqual(len(result), num_files)

            # Should complete in reasonable time (< 1 second for 1000 files)
            # This is a loose check - the real benefit is seen with tens of thousands of files
            self.assertLess(elapsed_time, 1.0)
        finally:
            rmtree(perf_test_dir)

    def test_list_media_files_deep_recursion(self):
        """Test that _list_media_files recurses into deeply nested subdirectories."""
        # List all movie files recursively with stat
        result = _list_media_files(self.test_dir, ['.mp4', '.avi', '.mkv'])
        result_paths = sorted([path for path, st in result])
        expected_files = sorted(self.movie_files)
        self.assertEqual(result_paths, expected_files)

        # Test that with_stat parameter is propagated during recursion
        result_no_stat = _list_media_files(
            self.test_dir, ['.mp4', '.avi', '.mkv'], with_stat=False
        )
        self.assertGreater(len(result_no_stat), 0)
        # All should have None as stat when with_stat=False
        for path, st in result_no_stat:
            self.assertIsNone(st)

    def test_list_media_files_limit_one_stops_early(self):
        """Test that limit=1 returns a single entry (cheap existence check)."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        result = _list_media_files(self.test_dir, movie_exts, with_stat=False, limit=1)

        self.assertEqual(len(result), 1)
        # the returned entry is one of the actual movie files
        self.assertIn(result[0][0], self.movie_files)

    def test_list_media_files_limit_spans_recursion(self):
        """Test that limit is honored across subdirectory recursion."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        # only 2 movies live in the root dir, so a limit of 5 must also count
        # files collected while recursing into subdirectories
        result = _list_media_files(self.test_dir, movie_exts, limit=5)

        self.assertEqual(len(result), 5)
        for path, st in result:
            self.assertIn(path, self.movie_files)

    def test_list_media_files_limit_above_total_returns_all(self):
        """Test that a limit larger than the number of files returns everything."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        result = _list_media_files(self.test_dir, movie_exts, limit=100)

        result_paths = sorted([path for path, st in result])
        self.assertEqual(result_paths, sorted(self.movie_files))

    def test_list_media_files_limit_with_sub_path(self):
        """Test that limit also applies when listing a sub_path."""
        movie_exts = ['.mp4', '.avi', '.mkv']
        # 2024-01-01 contains two movie files
        result = _list_media_files(
            self.test_dir, movie_exts, sub_path='2024-01-01', limit=1
        )

        self.assertEqual(len(result), 1)
        self.assertIn('2024-01-01', result[0][0])

    def test_list_media_files_limit_stops_scanning_early(self):
        """Test that limit=1 stops consuming directory entries at the first
        match instead of walking everything and truncating afterwards."""
        flat_dir = mkdtemp()
        try:
            num_files = 1000
            for i in range(num_files):
                Path(os.path.join(flat_dir, f'movie{i}.mp4')).touch()

            consumed = []
            real_scandir = os.scandir

            class CountingScandir:
                def __init__(self, path):
                    self._it = real_scandir(path)

                def __enter__(self):
                    return self

                def __exit__(self, *exc_info):
                    return self._it.__exit__(*exc_info)

                def __iter__(self):
                    for entry in self._it:
                        consumed.append(entry.name)
                        yield entry

            with patch('motioneye.mediafiles.os.scandir', CountingScandir):
                result = _list_media_files(flat_dir, ['.mp4'], with_stat=False, limit=1)

            self.assertEqual(len(result), 1)
            # every entry matches, so the walk must stop right after the
            # first one instead of scanning all 1000 files
            self.assertLessEqual(len(consumed), 2)
        finally:
            rmtree(flat_dir)

    def test_list_media_files_limit_counts_matches_not_scanned_entries(self):
        """Test that limit counts collected media files rather than examined
        directory entries, whatever the scan order."""
        mixed_dir = mkdtemp()
        try:
            # many non-media files and exactly one movie: with limit=1 the
            # movie must be found no matter in which order entries are scanned
            for i in range(50):
                Path(os.path.join(mixed_dir, f'note{i}.txt')).touch()
            movie = os.path.join(mixed_dir, 'only_movie.mp4')
            Path(movie).touch()

            result = _list_media_files(mixed_dir, ['.mp4'], with_stat=False, limit=1)
            self.assertEqual([path for path, st in result], [movie])

            # and nothing is returned when no entry matches at all
            result = _list_media_files(mixed_dir, ['.avi'], with_stat=False, limit=1)
            self.assertEqual(result, [])
        finally:
            rmtree(mixed_dir)

    def test_list_media_files_limit_remaining_budget_in_recursion(self):
        """Test that recursion only receives the remaining budget: with more
        files per subdirectory than budget left, the total must still not
        exceed the limit, whatever the scan order."""
        tree_dir = mkdtemp()
        try:
            # two subdirectories with 3 movies each; whichever is scanned
            # first leaves only one slot of the limit=4 budget for the other
            for sub in ('cam1', 'cam2'):
                os.makedirs(os.path.join(tree_dir, sub))
                for i in range(3):
                    Path(os.path.join(tree_dir, sub, f'movie{i}.mp4')).touch()

            result = _list_media_files(tree_dir, ['.mp4'], with_stat=False, limit=4)
            self.assertEqual(len(result), 4)
        finally:
            rmtree(tree_dir)

    def test_list_media_files_no_recursion_with_sub_path_filter(self):
        """Test that _list_media_files does not recurse when sub_path is provided."""
        # List files in level1_dir with sub_path filter (should not recurse into level2_dir)
        result = _list_media_files(
            self.test_dir, ['.mp4', '.avi', '.mkv', '.jpg'], sub_path='level1_dir'
        )
        result_paths = sorted([path for path, st in result])

        # Should find only files directly in level1_dir, not in nested subdirectories
        expected_files = sorted(
            [
                f
                for f in self.movie_files + self.picture_files
                if os.path.basename(os.path.dirname(f)) == 'level1_dir'
            ]
        )
        self.assertEqual(result_paths, expected_files)

        # Test with_stat=False works correctly with sub_path
        result_no_stat = _list_media_files(
            self.test_dir,
            ['.mp4', '.avi', '.mkv'],
            sub_path='2024-01-01',
            with_stat=False,
        )
        self.assertGreater(len(result_no_stat), 0)
        for path, st in result_no_stat:
            self.assertIsNone(st)
            self.assertTrue('2024-01-01' in path)

        # Should find only files directly in level1_dir, not in nested subdirectories
        expected_files = sorted(
            [
                f
                for f in self.movie_files + self.picture_files
                if os.path.basename(os.path.dirname(f)) == 'level1_dir'
            ]
        )
        self.assertEqual(result_paths, expected_files)


class TestDoListMedia(unittest.TestCase):
    """Tests for the _do_list_media subprocess entry point, using a fake pipe
    so no multiprocessing is involved."""

    class _FakePipe:
        def __init__(self):
            self.sent = []
            self.closed = False

        def send(self, obj):
            self.sent.append(obj)

        def close(self):
            self.closed = True

    def setUp(self):
        self.target_dir = mkdtemp()
        for i in range(3):
            Path(os.path.join(self.target_dir, f'movie{i}.mp4')).touch()

    def tearDown(self):
        rmtree(self.target_dir)

    def test_do_list_media_respects_limit(self):
        pipe = self._FakePipe()
        mediafiles._do_list_media(pipe, self.target_dir, ['.mp4'], None, False, 2)

        self.assertEqual(len(pipe.sent), 2)
        self.assertTrue(pipe.closed)
        for entry in pipe.sent:
            # without stat, only the path is sent
            self.assertEqual(list(entry.keys()), ['path'])
            self.assertTrue(entry['path'].startswith('/'))

    def test_do_list_media_defaults_list_everything_with_stat(self):
        pipe = self._FakePipe()
        mediafiles._do_list_media(pipe, self.target_dir, ['.mp4'], None, True)

        self.assertEqual(len(pipe.sent), 3)
        self.assertTrue(pipe.closed)
        for entry in pipe.sent:
            self.assertIn('mimeType', entry)
            self.assertIn('timestamp', entry)


class TestMediaFilesPathValidation(unittest.TestCase):
    """Tests verifying that path validation (traversal, absolute, dir escape) is enforced in mediafiles functions."""

    @classmethod
    def setUpClass(cls):
        cls._target_dir = mkdtemp()
        cls._outside_dir = mkdtemp()
        os.symlink(cls._outside_dir, os.path.join(cls._target_dir, 'escape'))
        cls._camera_config = {
            'target_dir': cls._target_dir,
            'framerate': 2,
            'pre_capture': 2,
        }

    @classmethod
    def tearDownClass(cls):
        rmtree(cls._target_dir, ignore_errors=True)
        rmtree(cls._outside_dir, ignore_errors=True)

    # Traversal inputs: each contains '..' as a path component.
    _FILENAME_TRAVERSALS = [
        '../etc/passwd',
        '../../etc/passwd',
        'subdir/../../../etc/passwd',
        '../secret.jpg',
    ]
    _SUBDIR_TRAVERSALS = [
        '..',
        '../group',
        'subdir/..',
        'subdir/../../other',
    ]

    # Absolute path inputs: each starts with '/'.
    _FILENAME_ABSOLUTES = ['/etc/passwd', '/mnt/secret.jpg']
    _SUBDIR_ABSOLUTES = ['/etc', '/root/.ssh', '/var/log']

    # Camera dir escape inputs: use the 'escape' symlink.
    _FILENAME_ESCAPES = ['escape/secret.jpg', 'escape/subdir/file.mp4']
    _SUBDIR_ESCAPES = ['escape', 'escape/subdir']

    def _assert_raises_traversal(self, fn, *args, **kwargs):
        with self.assertRaises(Exception) as ctx:
            fn(*args, **kwargs)
        self.assertIn('Path traversal', str(ctx.exception))

    def _assert_raises_absolute_path(self, fn, *args, **kwargs):
        with self.assertRaises(Exception) as ctx:
            fn(*args, **kwargs)
        self.assertIn('Absolute path', str(ctx.exception))

    def _assert_raises_dir_escape(self, fn, *args, **kwargs):
        with self.assertRaises(Exception) as ctx:
            fn(*args, **kwargs)
        self.assertIn('escapes camera directory', str(ctx.exception))

    # --- make_movie_preview ---

    def test_make_movie_preview_rejects_traversal(self):
        for path in self._FILENAME_TRAVERSALS:
            full_path = os.path.join(self._camera_config['target_dir'], path)
            with self.subTest(full_path=full_path):
                self._assert_raises_traversal(
                    mediafiles.make_movie_preview, self._camera_config, full_path
                )

    def test_make_movie_preview_rejects_absolute_path(self):
        for path in self._FILENAME_ABSOLUTES:
            with self.subTest(path=path):
                self._assert_raises_absolute_path(
                    mediafiles.make_movie_preview, self._camera_config, path
                )

    def test_make_movie_preview_rejects_dir_escape(self):
        for path in self._FILENAME_ESCAPES:
            full_path = os.path.join(self._camera_config['target_dir'], path)
            with self.subTest(full_path=full_path):
                self._assert_raises_dir_escape(
                    mediafiles.make_movie_preview, self._camera_config, full_path
                )

    # --- list_media ---

    def test_list_media_rejects_traversal(self):
        for prefix in self._SUBDIR_TRAVERSALS:
            with self.subTest(prefix=prefix):
                self._assert_raises_traversal(
                    mediafiles.list_media,
                    self._camera_config,
                    'picture',
                    prefix=prefix,
                )

    def test_list_media_rejects_absolute_path(self):
        for prefix in self._SUBDIR_ABSOLUTES:
            with self.subTest(prefix=prefix):
                self._assert_raises_absolute_path(
                    mediafiles.list_media,
                    self._camera_config,
                    'picture',
                    prefix=prefix,
                )

    def test_list_media_rejects_dir_escape(self):
        for prefix in self._SUBDIR_ESCAPES:
            with self.subTest(prefix=prefix):
                self._assert_raises_dir_escape(
                    mediafiles.list_media,
                    self._camera_config,
                    'picture',
                    prefix=prefix,
                )

    # --- get_media_path ---

    def test_get_media_path_rejects_traversal(self):
        for path in self._FILENAME_TRAVERSALS:
            with self.subTest(path=path):
                self._assert_raises_traversal(
                    mediafiles.get_media_path, self._camera_config, path, 'picture'
                )

    def test_get_media_path_rejects_absolute_path(self):
        for path in self._FILENAME_ABSOLUTES:
            with self.subTest(path=path):
                self._assert_raises_absolute_path(
                    mediafiles.get_media_path, self._camera_config, path, 'picture'
                )

    def test_get_media_path_rejects_dir_escape(self):
        for path in self._FILENAME_ESCAPES:
            with self.subTest(path=path):
                self._assert_raises_dir_escape(
                    mediafiles.get_media_path, self._camera_config, path, 'picture'
                )

    # --- get_media_content ---

    def test_get_media_content_rejects_traversal(self):
        for path in self._FILENAME_TRAVERSALS:
            with self.subTest(path=path):
                self._assert_raises_traversal(
                    mediafiles.get_media_content,
                    self._camera_config,
                    path,
                    'picture',
                )

    def test_get_media_content_rejects_absolute_path(self):
        for path in self._FILENAME_ABSOLUTES:
            with self.subTest(path=path):
                self._assert_raises_absolute_path(
                    mediafiles.get_media_content,
                    self._camera_config,
                    path,
                    'picture',
                )

    def test_get_media_content_rejects_dir_escape(self):
        for path in self._FILENAME_ESCAPES:
            with self.subTest(path=path):
                self._assert_raises_dir_escape(
                    mediafiles.get_media_content,
                    self._camera_config,
                    path,
                    'picture',
                )

    # --- get_zipped_content ---

    def test_get_zipped_content_rejects_traversal(self):
        for group in self._SUBDIR_TRAVERSALS:
            with self.subTest(group=group):
                self._assert_raises_traversal(
                    mediafiles.get_zipped_content,
                    self._camera_config,
                    'picture',
                    group,
                )

    def test_get_zipped_content_rejects_absolute_path(self):
        for group in self._SUBDIR_ABSOLUTES:
            with self.subTest(group=group):
                self._assert_raises_absolute_path(
                    mediafiles.get_zipped_content,
                    self._camera_config,
                    'picture',
                    group,
                )

    def test_get_zipped_content_rejects_dir_escape(self):
        for group in self._SUBDIR_ESCAPES:
            with self.subTest(group=group):
                self._assert_raises_dir_escape(
                    mediafiles.get_zipped_content,
                    self._camera_config,
                    'picture',
                    group,
                )

    # --- make_timelapse_movie ---

    def test_make_timelapse_movie_rejects_traversal(self):
        for group in self._SUBDIR_TRAVERSALS:
            with self.subTest(group=group):
                self._assert_raises_traversal(
                    mediafiles.make_timelapse_movie,
                    self._camera_config,
                    2,
                    1,
                    group,
                )

    def test_make_timelapse_movie_rejects_absolute_path(self):
        for group in self._SUBDIR_ABSOLUTES:
            with self.subTest(group=group):
                self._assert_raises_absolute_path(
                    mediafiles.make_timelapse_movie,
                    self._camera_config,
                    2,
                    1,
                    group,
                )

    def test_make_timelapse_movie_rejects_dir_escape(self):
        for group in self._SUBDIR_ESCAPES:
            with self.subTest(group=group):
                self._assert_raises_dir_escape(
                    mediafiles.make_timelapse_movie,
                    self._camera_config,
                    2,
                    1,
                    group,
                )

    # --- get_media_preview ---

    def test_get_media_preview_rejects_traversal(self):
        for path in self._FILENAME_TRAVERSALS:
            with self.subTest(path=path):
                self._assert_raises_traversal(
                    mediafiles.get_media_preview,
                    self._camera_config,
                    path,
                    'picture',
                    None,
                    None,
                )

    def test_get_media_preview_rejects_absolute_path(self):
        for path in self._FILENAME_ABSOLUTES:
            with self.subTest(path=path):
                self._assert_raises_absolute_path(
                    mediafiles.get_media_preview,
                    self._camera_config,
                    path,
                    'picture',
                    None,
                    None,
                )

    def test_get_media_preview_rejects_dir_escape(self):
        for path in self._FILENAME_ESCAPES:
            with self.subTest(path=path):
                self._assert_raises_dir_escape(
                    mediafiles.get_media_preview,
                    self._camera_config,
                    path,
                    'picture',
                    None,
                    None,
                )

    # --- del_media_content ---

    def test_del_media_content_rejects_traversal(self):
        for path in self._FILENAME_TRAVERSALS:
            with self.subTest(path=path):
                self._assert_raises_traversal(
                    mediafiles.del_media_content,
                    self._camera_config,
                    path,
                    'picture',
                )

    def test_del_media_content_rejects_absolute_path(self):
        for path in self._FILENAME_ABSOLUTES:
            with self.subTest(path=path):
                self._assert_raises_absolute_path(
                    mediafiles.del_media_content,
                    self._camera_config,
                    path,
                    'picture',
                )

    def test_del_media_content_rejects_dir_escape(self):
        for path in self._FILENAME_ESCAPES:
            with self.subTest(path=path):
                self._assert_raises_dir_escape(
                    mediafiles.del_media_content,
                    self._camera_config,
                    path,
                    'picture',
                )

    # --- del_media_group ---

    def test_del_media_group_rejects_traversal(self):
        for group in self._SUBDIR_TRAVERSALS:
            with self.subTest(group=group):
                self._assert_raises_traversal(
                    mediafiles.del_media_group,
                    self._camera_config,
                    group,
                    'picture',
                )

    def test_del_media_group_rejects_absolute_path(self):
        for group in self._SUBDIR_ABSOLUTES:
            with self.subTest(group=group):
                self._assert_raises_absolute_path(
                    mediafiles.del_media_group,
                    self._camera_config,
                    group,
                    'picture',
                )

    def test_del_media_group_rejects_dir_escape(self):
        for group in self._SUBDIR_ESCAPES:
            with self.subTest(group=group):
                self._assert_raises_dir_escape(
                    mediafiles.del_media_group,
                    self._camera_config,
                    group,
                    'picture',
                )


if __name__ == '__main__':
    unittest.main()
