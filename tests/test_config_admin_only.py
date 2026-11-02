from __future__ import annotations

import unittest

from motioneye import config
from tests.test_notification_settings import _ConfigCase


class AdminOnlyTest(_ConfigCase):
    """admin_only stays local to each motionEye instance: a hub drops it before it
    forwards a camera's settings to the remote, so a save without it keeps the stored
    value, for motion cameras as well as for simple MJPEG cameras."""

    def _cameras(self):
        mjpeg = {
            '@id': 2,
            '@enabled': True,
            '@url': 'http://example/mjpeg',
            'camera_name': 'MJPEG',
        }
        return (
            (
                'motion',
                self.camera,
                config.motion_camera_dict_to_ui,
                config.motion_camera_ui_to_dict,
            ),
            (
                'simple mjpeg',
                mjpeg,
                config.simple_mjpeg_camera_dict_to_ui,
                config.simple_mjpeg_camera_ui_to_dict,
            ),
        )

    def _saved(self, camera, dict_to_ui, ui_to_dict, stored, posted):
        # the camera saved with admin_only stored and posted (None: absent)
        prev = {name: value for name, value in camera.items() if name != '@admin_only'}
        if stored is not None:
            prev['@admin_only'] = stored

        ui = dict_to_ui(prev)
        del ui['admin_only']
        if posted is not None:
            ui['admin_only'] = posted

        return ui_to_dict(ui, prev)['@admin_only']

    def test_a_save_without_admin_only_keeps_the_stored_value(self):
        for kind, *camera in self._cameras():
            for stored, expected in ((True, True), (False, False), (None, False)):
                with self.subTest(camera=kind, stored=stored):
                    self.assertIs(expected, self._saved(*camera, stored, None))

    def test_a_save_with_admin_only_sets_it(self):
        for kind, *camera in self._cameras():
            for stored, posted in ((True, False), (False, True)):
                with self.subTest(camera=kind, stored=stored):
                    self.assertIs(posted, self._saved(*camera, stored, posted))


if __name__ == '__main__':
    unittest.main()
