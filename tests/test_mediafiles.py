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

from motioneye.mediafiles import _list_media_files


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
        # Also create nested subdirectories to test recursion
        date1 = os.path.join(self.test_dir, '2024-01-01')
        date2 = os.path.join(self.test_dir, '2024-01-02')
        nested1 = os.path.join(self.test_dir, 'level1_dir')
        nested2 = os.path.join(nested1, 'level2_dir')
        nested3 = os.path.join(nested2, 'level3_dir')
        os.makedirs(date1)
        os.makedirs(date2)
        os.makedirs(nested3)

        # Create movie files at various levels
        movie_files = [
            os.path.join(self.test_dir, 'root_video1.mp4'),
            os.path.join(self.test_dir, 'root_video2.avi'),
            os.path.join(date1, 'video3.mp4'),
            os.path.join(date1, 'video4.mkv'),
            os.path.join(date2, 'video5.mp4'),
            os.path.join(nested1, 'level1_video.mp4'),
            os.path.join(nested2, 'level2_video.mp4'),
            os.path.join(nested3, 'level3_video.mp4'),
        ]

        # Create picture files at various levels
        picture_files = [
            os.path.join(self.test_dir, 'root_image1.jpg'),
            os.path.join(date1, 'image2.jpg'),
            os.path.join(date2, 'image3.jpg'),
            os.path.join(nested1, 'level1_image.jpg'),
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

    def test_recursive_listing_all_files(self):
        """Test that _list_media_files returns all regular files recursively when no subdirectory is given."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        # Pass all extensions to find all files
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
        result = _list_media_files(self.test_dir, all_exts)

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

    def test_return_structure(self):
        """Test that _list_media_files returns tuples with (path, stat)."""
        self.create_test_structure()
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
        result = _list_media_files(self.test_dir, all_exts)

        for item in result:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            path, st = item
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(hasattr(st, 'st_mtime'))  # Check it's a stat object

    def test_filter_by_movie_extensions(self):
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

    def test_filter_by_picture_extensions(self):
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

    def test_non_recursive_with_subdirectory(self):
        """Test listing media files with a subdirectory (non-recursive)."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        movie_exts = ['.mp4', '.avi', '.mkv']
        # Test with a specific date subdirectory
        result = _list_media_files(self.test_dir, movie_exts, subdirectory='2024-01-01')

        result_paths = [path for path, st in result]

        # Should only find files in the 2024-01-01 directory (not in subdirectories of it)
        expected_files = [
            f for f in movie_files if os.path.dirname(f).endswith('2024-01-01')
        ]
        self.assertEqual(len(result_paths), len(expected_files))

    def test_ungrouped_subdirectory(self):
        """Test listing media files with 'ungrouped' subdirectory."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        movie_exts = ['.mp4', '.avi', '.mkv']
        # 'ungrouped' should translate to empty string subdirectory
        result = _list_media_files(self.test_dir, movie_exts, subdirectory='ungrouped')

        result_paths = [path for path, st in result]

        # Should find files in the root directory only (not in subdirectories)
        expected_files = [f for f in movie_files if os.path.dirname(f) == self.test_dir]
        self.assertEqual(len(result_paths), len(expected_files))

    def test_nonexistent_subdirectory(self):
        """Test listing media files with a non-existent subdirectory."""
        self.create_test_structure()

        movie_exts = ['.mp4', '.avi', '.mkv']
        result = _list_media_files(
            self.test_dir, movie_exts, subdirectory='nonexistent'
        )

        # Should return empty list
        self.assertEqual(len(result), 0)

    def test_empty_directory(self):
        """Test _list_media_files on an empty directory."""
        all_exts = ['.mp4', '.avi', '.mkv', '.jpg']
        result = _list_media_files(self.test_dir, all_exts)
        self.assertEqual(len(result), 0)

    def test_performance_with_many_files(self):
        """Test that the optimized version can handle many files efficiently."""
        # Create a large number of files to test performance
        import time

        num_files = 1000
        for i in range(num_files):
            Path(os.path.join(self.test_dir, f'video{i}.mp4')).touch()

        # Measure time to list all files
        start_time = time.time()
        result = _list_media_files(self.test_dir, ['.mp4'])
        elapsed_time = time.time() - start_time

        # Should find all files
        self.assertEqual(len(result), num_files)

        # Should complete in reasonable time (< 1 second for 1000 files)
        # This is a loose check - the real benefit is seen with tens of thousands of files
        self.assertLess(elapsed_time, 1.0)

    def test_deep_recursion(self):
        """Test that _list_media_files recurses into deeply nested subdirectories."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        # List all movie files recursively
        result = _list_media_files(self.test_dir, ['.mp4', '.avi', '.mkv'])
        result_paths = [path for path, st in result]

        # Should find all movie files at all nesting levels
        self.assertEqual(len(result_paths), len(movie_files))
        for movie_file in movie_files:
            self.assertIn(movie_file, result_paths)

    def test_no_recursion_with_subdirectory_filter(self):
        """Test that _list_media_files does not recurse when subdirectory is provided."""
        movie_files, picture_files, ignored_files = self.create_test_structure()

        # List files in level1_dir with subdirectory filter (should not recurse into level2_dir)
        result = _list_media_files(
            self.test_dir, ['.mp4', '.avi', '.mkv', '.jpg'], subdirectory='level1_dir'
        )
        result_paths = [path for path, st in result]

        # Should find only files directly in level1_dir, not in nested subdirectories
        expected_files = [
            f
            for f in movie_files + picture_files
            if os.path.basename(os.path.dirname(f)) == 'level1_dir'
        ]
        self.assertEqual(len(result_paths), len(expected_files))
        for expected_file in expected_files:
            self.assertIn(expected_file, result_paths)

        # Should not find files in nested subdirectories
        level2_file = os.path.join(
            self.test_dir, 'level1_dir', 'level2_dir', 'level2_video.mp4'
        )
        self.assertNotIn(level2_file, result_paths)


if __name__ == '__main__':
    unittest.main()
