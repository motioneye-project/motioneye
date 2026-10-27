import os
import shutil
import tempfile
import unittest
from unittest import mock

from PIL import Image

from motioneye import settings, utils


def mask_grid(width, height):
    """Returns the mask grid of the mask editor in static/js/main.js: the number
    of full columns and rows, and the size of the remainder column and row.
    """
    nx = utils.MASK_WIDTH
    rx = 0
    if width % nx:
        nx -= 1
        rx = width % nx

    ny = height * utils.MASK_WIDTH // width
    ry = 0
    if height % ny:
        ny -= 1
        ry = height % ny

    return nx, rx, ny, ry


class TestEditableMask(unittest.TestCase):
    def setUp(self):
        self.conf_path = tempfile.mkdtemp()
        # as load_settings() sets it from motioneye.conf, after utils was imported
        patcher = mock.patch.object(settings, 'CONF_PATH', self.conf_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.conf_path)

    def test_mask_files_are_in_the_configured_conf_path(self):
        for mask_class, name in [
            ('motion', 'mask_1.pgm'),
            ('privacy', 'mask_1_privacy.pgm'),
        ]:
            with self.subTest(mask_class=mask_class):
                file_name = utils.build_editable_mask_file(
                    1, mask_class, [640, 480] + [0] * 24
                )

                self.assertEqual(os.path.join(self.conf_path, name), file_name)
                self.assertTrue(os.path.isfile(file_name))

    def test_build_and_parse_round_trip(self):
        for width, height in [
            (640, 480),
            (1920, 1080),
            (1366, 768),  # remainder column
            (704, 576),  # remainder row
            (1000, 562),  # remainder column and row
            (1300, 700),  # large remainders
        ]:
            with self.subTest(size=f'{width}x{height}'):
                nx, rx, ny, ry = mask_grid(width, height)
                # bits of the full columns, plus bit 0 for the remainder column
                bits = sum(1 << (utils.MASK_WIDTH - 1 - x) for x in range(nx))
                bits |= 1 if rx else 0
                # a different pattern for each line, with the remainder bit in some
                lines = [
                    (0x9E3779B9 * (y + 1)) & 0xFFFFFFFF & bits
                    for y in range(ny + bool(ry))
                ]

                utils.build_editable_mask_file(1, 'motion', [width, height] + lines)

                self.assertEqual(
                    [width, height] + lines,
                    utils.parse_editable_mask_file(1, 'motion'),
                )

    def test_build_draws_the_remainder_column_and_row(self):
        width, height = 1000, 562
        _nx, rx, ny, _ry = mask_grid(width, height)
        # only the remainder column, in every row including the remainder row
        lines = [1] * (ny + 1)

        file_name = utils.build_editable_mask_file(1, 'motion', [width, height] + lines)

        with Image.open(file_name) as im:
            self.assertEqual(0, im.getpixel((width - rx, 0)))
            self.assertEqual(0, im.getpixel((width - 1, height - 1)))
            self.assertEqual(255, im.getpixel((width - rx - 1, 0)))
            # remainder row, first full column: not selected
            self.assertEqual(255, im.getpixel((0, height - 1)))


if __name__ == '__main__':
    unittest.main()
