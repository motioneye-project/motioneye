# Copyright (c) 2026 motionEye contributors
#
# This program is free software: you can redistribute it and/or modify
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

from json import dumps, loads
from unittest.mock import AsyncMock, patch

from motioneye import config
from motioneye.handlers.config import ConfigHandler
from tests.test_handlers import _FAKE_REMOTE_CAMERA_CONFIG, RemoteCameraTestCase

# what /config/list/ and /config/<id>/get/ answer for a remote camera that cannot be reached
_FAILED_LIST_ENTRY = {
    'id': 1,
    'name': 'Camera 1 - Connection failed',
    'enabled': False,
    'connection_failed': True,
    'connection_error': 'Failed to get remote camera configuration',
    'connection_url': 'http://cam.example:8765',
    'streaming_framerate': 1,
    'framerate': 1,
}
_FAILED_GET_ANSWER = {
    'error': 'Failed to get remote camera configuration',
    'connection_failed': True,
    'connection_url': 'http://cam.example:8765',
}


class RemoteFailedEntryTest(RemoteCameraTestCase):
    """A client that posts back what it was told about an unreachable remote camera
    must not turn that into the camera's settings."""

    handler_cls = ConfigHandler

    def setUp(self):
        super().setUp()
        # the base class already replaced config.get_camera; give its mock our copy
        self.camera = dict(_FAKE_REMOTE_CAMERA_CONFIG)
        config.get_camera.return_value = self.camera
        self._start(patch('motioneye.config.get_main', return_value={'@enabled': True}))
        self.set_camera = self._start(patch('motioneye.config.set_camera'))
        self.remote_set_config = self._start(
            patch('motioneye.remote.set_config', AsyncMock(return_value=None))
        )

    def _start(self, patcher):
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _post_as_admin(self, body):
        return self.fetch(
            '/config/1/set/',
            method='POST',
            body=dumps(body),
            headers={'Cookie': self.make_session_cookie('admin')},
        )

    def test_a_failed_list_entry_posted_back_saves_nothing(self):
        response = self._post_as_admin(dict(_FAILED_LIST_ENTRY))

        self.assertEqual(200, response.code)
        self.assertIn('nothing was saved', loads(response.body)['error'])
        self.set_camera.assert_not_called()
        self.remote_set_config.assert_not_called()
        self.assertIs(True, self.camera['@enabled'])  # not disabled by the echo

    def test_a_failed_get_answer_posted_back_saves_nothing(self):
        response = self._post_as_admin(dict(_FAILED_GET_ANSWER))

        self.assertEqual(200, response.code)
        self.assertIn('nothing was saved', loads(response.body)['error'])
        self.set_camera.assert_not_called()
        self.remote_set_config.assert_not_called()

    def test_a_real_config_is_still_saved_and_forwarded(self):
        response = self._post_as_admin(
            {'enabled': True, 'name': 'cam', 'admin_only': False}
        )

        self.assertEqual(200, response.code)
        self.assertIsNone(loads(response.body)['error'])
        self.set_camera.assert_called_once()
        self.remote_set_config.assert_called_once()
