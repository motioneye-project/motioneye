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
from unittest.mock import patch

from motioneye import config, utils

# what saving an SMTP password with a ' in it writes, unescaped
_BROKEN_MAIL = (
    "/usr/bin/meyectl sendmail 'smtp.example' '587' 'me' 'it's' 'True' '' "
    "'a@example' 'motion_start' '%t' '%Y-%m-%dT%H:%M:%S' '5'"
)
_BROKEN_HOOK = "/usr/bin/meyectl webhook 'POST' 'https://x.example/?q=it's'"
_BROKEN_RELAY = "/home/o'b/motioneye/scripts/relayevent.sh \"c.conf\" stop %t"


class _Case(unittest.TestCase):
    # camera 1, a local network camera
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

    def _patch(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()


class UnparsableCommandTest(_Case):
    def test_quote_in_smtp_password(self):
        self.camera['on_event_start'] = _BROKEN_MAIL

        ui = config.motion_camera_dict_to_ui(self.camera)  # raised ValueError before

        self.assertFalse(ui['email_notifications_enabled'])
        self.assertEqual(_BROKEN_MAIL, ui['command_notifications_exec'])
        saved = config.motion_camera_ui_to_dict(ui, self.camera)
        parts = utils.split_semicolon(saved['on_event_start'])
        self.assertEqual(_BROKEN_MAIL, parts[-1])

    def test_unparsable_relay_is_still_ignored(self):
        self.camera['on_event_end'] = _BROKEN_RELAY

        ui = config.motion_camera_dict_to_ui(self.camera)

        self.assertFalse(ui['command_end_notifications_enabled'])

    def test_quote_in_webhook_commands(self):
        self.camera['on_event_end'] = _BROKEN_HOOK
        self.camera['on_movie_end'] = _BROKEN_HOOK

        ui = config.motion_camera_dict_to_ui(self.camera)

        self.assertFalse(ui['web_hook_end_notifications_enabled'])
        self.assertFalse(ui['web_hook_storage_enabled'])
        self.assertEqual(_BROKEN_HOOK, ui['command_end_notifications_exec'])
        self.assertEqual(_BROKEN_HOOK, ui['command_storage_exec'])


class SplitSemicolonTest(unittest.TestCase):
    def test_double_semicolon(self):
        case = 'case $1 in a) echo a;; *) echo b;; esac'
        self.assertEqual(case, '; '.join(utils.split_semicolon(case)))
        self.assertEqual(['a;b', 'c'], utils.split_semicolon('a\\;b; c'))


if __name__ == '__main__':
    unittest.main()
