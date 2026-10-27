from __future__ import annotations

import unittest

from motioneye import config
from tests.test_notification_settings import _ConfigCase

# settings a hub running 0.44.0 does not have in its form, so it never posts them
_ADDED_AFTER_0_44 = ('upload_tls', 'upload_verify', 'clean_uploaded')
_NOT_DEFAULT = {'@upload_tls': True, '@upload_verify': False, '@clean_uploaded': True}


def _as_older_hub_posts(ui):
    return {name: value for name, value in ui.items() if name not in _ADDED_AFTER_0_44}


class OlderClientTest(_ConfigCase):
    """A camera config posted without the settings added after 0.44.0, as a hub running
    0.44 forwards it for a remote camera, is saved, and keeps what the camera has."""

    def test_a_post_without_the_new_settings_keeps_the_stored_values(self):
        changed = dict(self.camera, **_NOT_DEFAULT)
        defaults = {name: self.camera[name] for name in _NOT_DEFAULT}

        for stored, expected in ((self.camera, defaults), (changed, _NOT_DEFAULT)):
            with self.subTest(stored=expected):
                ui = _as_older_hub_posts(config.motion_camera_dict_to_ui(stored))
                data = config.motion_camera_ui_to_dict(ui, stored)

                self.assertEqual(expected, {name: data[name] for name in expected})

    def test_the_camera_file_is_unchanged_by_such_a_post(self):
        self._write(1, dict(self.camera, **_NOT_DEFAULT))
        self._post(self._get())  # the file as the server writes it
        text = self._read(1)
        for line in (
            '# @upload_tls on',
            '# @upload_verify off',
            '# @clean_uploaded on',
        ):
            self.assertIn(f'\n{line}\n', text)

        self._post(_as_older_hub_posts(self._get()))

        self.assertEqual(text, self._read(1))

    def test_a_post_with_the_new_settings_still_sets_them(self):
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(upload_tls=True, upload_verify=False, clean_uploaded=True)

        data = config.motion_camera_ui_to_dict(ui, self.camera)

        self.assertEqual(_NOT_DEFAULT, {name: data[name] for name in _NOT_DEFAULT})


if __name__ == '__main__':
    unittest.main()
