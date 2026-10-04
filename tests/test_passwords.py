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

import unittest
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import call, patch

from motioneye import config

_MAIN = {
    '@admin_username': 'admin',
    '@admin_password': 'admin-hash',
    '@normal_username': 'user',
    '@normal_password': 'user-hash',
    '@lang': 'en',
}


class _Case(unittest.TestCase):
    def _patch(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()


class MainPasswordsTest(_Case):
    def setUp(self):
        self.sessions = self._patch('motioneye.handlers.base.invalidate_user_sessions')
        self.hook = self._patch('motioneye.utils.call_subprocess')
        self._patch('motioneye.settings.PASSWORD_HOOK', 'hook')

    def test_set_passwords_are_left_out_and_kept(self):
        ui = config.main_dict_to_ui(_MAIN)
        self.assertNotIn('admin_password', ui)
        self.assertNotIn('normal_password', ui)

        data = config.main_ui_to_dict(ui)  # what API clients post back
        ui.update({'admin_password': '', 'normal_password': ''})  # e.g. an older UI
        data.update(config.main_ui_to_dict(ui))

        self.assertNotIn('@admin_password', data)  # the stored hashes stay
        self.assertNotIn('@normal_password', data)
        self.sessions.assert_not_called()
        self.hook.assert_not_called()

    def test_unset_passwords_are_empty(self):
        main = dict(_MAIN)
        main.update({'@admin_password': '', '@normal_password': ''})

        ui = config.main_dict_to_ui(main)

        self.assertEqual('', ui['admin_password'])
        self.assertEqual('', ui['normal_password'])

    def test_new_passwords_are_saved(self):
        ui = config.main_dict_to_ui(_MAIN)
        ui.update({'admin_password': 'n3w', 'normal_password': 'n3w2'})

        data = config.main_ui_to_dict(ui)

        self.assertTrue(config.ph.verify(data['@admin_password'], 'n3w'))
        self.assertTrue(config.ph.verify(data['@normal_password'], 'n3w2'))
        self.assertEqual([call('admin'), call('normal')], self.sessions.call_args_list)
        self.assertEqual(2, self.hook.call_count)


class StreamPasswordTest(_Case):
    # camera 1, a local network camera with basic stream authentication
    def setUp(self):
        self.conf_dir = mkdtemp()
        self.addCleanup(rmtree, self.conf_dir)
        main_config = {}
        config._set_default_motion(main_config)
        self._patch('builtins._', str, create=True)
        self._patch('motioneye.config.get_main', return_value=main_config)
        no_ffmpeg = (None, None, None)
        self._patch('motioneye.mediafiles.find_ffmpeg', return_value=no_ffmpeg)
        self._patch('motioneye.motionctl.is_motion_pre42', return_value=False)
        self._patch('motioneye.motionctl.is_motion_post43', return_value=False)
        self._patch('motioneye.utils.get_disk_usage', return_value=None)
        self._patch('motioneye.controls.diskctl.list_mounted_disks', return_value=[])

        self.camera = {'@id': 1, '@enabled': True, 'netcam_url': 'rtsp://example/'}
        self.camera.update(width=640, height=480)
        config._set_default_motion_camera(1, self.camera)
        self.camera['target_dir'] = self.conf_dir
        self.camera['stream_auth_method'] = 1
        self.camera['stream_authentication'] = 'viewer:s3cret'

    def _post(self, value):
        # what GET returns, posted back with this streaming_password
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui['streaming_password'] = value
        return config.motion_camera_ui_to_dict(ui, self.camera)['stream_authentication']

    def test_set_password_is_left_out_and_kept(self):
        ui = config.motion_camera_dict_to_ui(self.camera)
        self.assertNotIn('streaming_password', ui)
        self.assertEqual('viewer', ui['streaming_username'])

        data = config.motion_camera_ui_to_dict(ui, self.camera)

        self.assertEqual('viewer:s3cret', data['stream_authentication'])

    def test_unset_password_is_empty(self):
        for value in ('', 'viewer:', 'viewer'):  # '' = no stream authentication
            with self.subTest(value):
                self.camera['stream_authentication'] = value

                ui = config.motion_camera_dict_to_ui(self.camera)

                self.assertEqual('', ui['streaming_password'])
                self.assertEqual(value.partition(':')[0], ui['streaming_username'])

    def test_new_or_left_out_password(self):
        self.assertEqual('viewer:n3w', self._post('n3w'))
        self.assertEqual('viewer:s3cret', self._post(''))
        self.assertEqual('viewer:s3cret', self._post(None))


if __name__ == '__main__':
    unittest.main()
