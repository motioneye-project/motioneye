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
        result = _list_media_files(self.test_dir, all_exts)

        for item in result:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            path, st = item
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(hasattr(st, 'st_mtime'))  # Check it's a stat object

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
        # List all movie files recursively
        result = _list_media_files(self.test_dir, ['.mp4', '.avi', '.mkv'])
        result_paths = sorted([path for path, st in result])

        # Should find all movie files at all nesting levels
        expected_files = sorted(self.movie_files)
        self.assertEqual(result_paths, expected_files)

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


if __name__ == '__main__':
    unittest.main()
