import unittest

from motioneye.utils import remove_prefix


class RemovePrefixTest(unittest.TestCase):
    def test_strips_matching_prefix(self):
        self.assertEqual(
            remove_prefix('/media/cam1/2024-01-01/movie.mp4', '/media/cam1/'),
            '2024-01-01/movie.mp4',
        )

    def test_returns_unchanged_when_prefix_does_not_match(self):
        # security-relevant: a path outside target_dir must come back as-is so
        # validate_paths() can still reject it as an absolute path
        self.assertEqual(remove_prefix('/etc/passwd', '/media/cam1/'), '/etc/passwd')

    def test_empty_prefix_returns_unchanged(self):
        self.assertEqual(remove_prefix('/etc/passwd', ''), '/etc/passwd')

    def test_string_equal_to_prefix_becomes_empty(self):
        self.assertEqual(remove_prefix('/media/cam1/', '/media/cam1/'), '')

    def test_shorter_than_prefix_returns_unchanged(self):
        self.assertEqual(remove_prefix('abc', 'abcdef'), 'abc')


if __name__ == '__main__':
    unittest.main()
