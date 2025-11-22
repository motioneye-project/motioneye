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
import tempfile
import unittest
from pathlib import Path

from motioneye.mediafiles import _list_media_files, findfiles


class TestMediaFiles(unittest.TestCase):
    def setUp(self):
        """Create a temporary directory structure for testing."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files and directories."""
        import shutil

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_test_structure(self):
        """Create a realistic test directory structure with movies and pictures."""
        # Create some subdirectories (like date-based groups)
        date1 = os.path.join(self.test_dir, '2024-01-01')
        date2 = os.path.join(self.test_dir, '2024-01-02')
        os.makedirs(date1)
        os.makedirs(date2)

        # Create movie files
        movie_files = [
            os.path.join(self.test_dir, 'video1.mp4'),
            os.path.join(self.test_dir, 'video2.avi'),
            os.path.join(date1, 'video3.mp4'),
            os.path.join(date1, 'video4.mkv'),
            os.path.join(date2, 'video5.mp4'),
        ]

        # Create picture files
        picture_files = [
            os.path.join(self.test_dir, 'image1.jpg'),
            os.path.join(date1, 'image2.jpg'),
            os.path.join(date2, 'image3.jpg'),
        ]

        # Create files that should be ignored
        ignored_files = [
            os.path.join(self.test_dir, '.hidden'),
            os.path.join(self.test_dir, 'lastsnap.jpg'),
            os.path.join(date1, '.dotfile'),
        ]

        all_files = movie_files + picture_files + ignored_files
        for f in all_files:
            Path(f).touch()

        return movie_files, picture_files, ignored_files

    def test_findfiles_basic(self):
        """Test that findfiles returns all regular files recursively."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        # Pass all extensions to find all files
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
        result = findfiles(self.test_dir, all_exts)

        # Extract just the file paths from the result tuples
        result_paths = [path for path, st in result]

        # Should find all non-ignored files
        expected_files = movie_files + picture_files
        self.assertEqual(len(result_paths), len(expected_files))

        # Verify all expected files are found
        for expected_file in expected_files:
            self.assertIn(expected_file, result_paths)

        # Verify ignored files are not found
        for ignored_file in ignored_files:
            self.assertNotIn(ignored_file, result_paths)

    def test_findfiles_returns_correct_structure(self):
        """Test that findfiles returns tuples with (path, stat)."""
        self.create_test_structure()
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
        result = findfiles(self.test_dir, all_exts)

        for item in result:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            path, st = item
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(hasattr(st, 'st_mtime'))  # Check it's a stat object

    def test_list_media_files_movies(self):
        """Test listing movie files with correct extensions."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        movie_exts = ['.mp4', '.avi', '.mkv']
        result = _list_media_files(self.test_dir, movie_exts)

        # Extract just the file paths
        result_paths = [path for path, st in result]

        # Should find only movie files
        self.assertEqual(len(result_paths), len(movie_files))
        for movie_file in movie_files:
            self.assertIn(movie_file, result_paths)

        # Should not find picture files
        for picture_file in picture_files:
            self.assertNotIn(picture_file, result_paths)

    def test_list_media_files_pictures(self):
        """Test listing picture files with correct extensions."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        picture_exts = ['.jpg']
        result = _list_media_files(self.test_dir, picture_exts)

        # Extract just the file paths
        result_paths = [path for path, st in result]

        # Should find only picture files
        self.assertEqual(len(result_paths), len(picture_files))
        for picture_file in picture_files:
            self.assertIn(picture_file, result_paths)

    def test_list_media_files_with_prefix(self):
        """Test listing media files with a prefix/group."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        movie_exts = ['.mp4', '.avi', '.mkv']
        # Test with a specific date prefix
        result = _list_media_files(self.test_dir, movie_exts, prefix='2024-01-01')

        result_paths = [path for path, st in result]

        # Should only find files in the 2024-01-01 directory
        expected_files = [
            f for f in movie_files if os.path.dirname(f).endswith('2024-01-01')
        ]
        self.assertEqual(len(result_paths), len(expected_files))

    def test_list_media_files_ungrouped_prefix(self):
        """Test listing media files with 'ungrouped' prefix."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        movie_exts = ['.mp4', '.avi', '.mkv']
        # 'ungrouped' should translate to empty string prefix
        result = _list_media_files(self.test_dir, movie_exts, prefix='ungrouped')

        result_paths = [path for path, st in result]

        # Should find files in the root directory only
        expected_files = [f for f in movie_files if os.path.dirname(f) == self.test_dir]
        self.assertEqual(len(result_paths), len(expected_files))

    def test_list_media_files_nonexistent_prefix(self):
        """Test listing media files with a non-existent prefix."""
        self.create_test_structure()

        movie_exts = ['.mp4', '.avi', '.mkv']
        result = _list_media_files(self.test_dir, movie_exts, prefix='nonexistent')

        # Should return empty list
        self.assertEqual(len(result), 0)

    def test_findfiles_empty_directory(self):
        """Test findfiles on an empty directory."""
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
        result = findfiles(self.test_dir, all_exts)
        self.assertEqual(len(result), 0)

    def test_large_directory_performance(self):
        """Test that the optimized version can handle many files efficiently."""
        # Create a large number of files to test performance
        import time

        num_files = 1000
        for i in range(num_files):
            Path(os.path.join(self.test_dir, f'video{i}.mp4')).touch()

        # Measure time to list all files
        start_time = time.time()
        result = findfiles(self.test_dir, ['.mp4'])
        elapsed_time = time.time() - start_time

        # Should find all files
        self.assertEqual(len(result), num_files)

        # Should complete in reasonable time (< 1 second for 1000 files)
        # This is a loose check - the real benefit is seen with tens of thousands of files
        self.assertLess(elapsed_time, 1.0)

    def test_findfiles_with_extension_filter(self):
        """Test that findfiles filters by extension when exts parameter is provided."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        # Test filtering for movies only
        movie_exts = ['.mp4', '.avi', '.mkv']
        result = findfiles(self.test_dir, exts=movie_exts)
        result_paths = [path for path, st in result]

        # Should find only movie files
        self.assertEqual(len(result_paths), len(movie_files))
        for movie_file in movie_files:
            self.assertIn(movie_file, result_paths)

        # Should not find picture files
        for picture_file in picture_files:
            self.assertNotIn(picture_file, result_paths)

        # Test filtering for pictures only
        picture_exts = ['.jpg']
        result = findfiles(self.test_dir, exts=picture_exts)
        result_paths = [path for path, st in result]

        # Should find only picture files
        self.assertEqual(len(result_paths), len(picture_files))
        for picture_file in picture_files:
            self.assertIn(picture_file, result_paths)


if __name__ == '__main__':
    unittest.main()
