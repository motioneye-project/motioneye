from __future__ import annotations

from unittest.mock import AsyncMock, patch

from motioneye.handlers.picture import PictureHandler
from motioneye.utils import GetConfigResponse
from tests.test_handlers import RemoteCameraTestCase

_REMOTE_UI_CONFIG = {
    'name': '<b>cam</b>',
    'streaming_framerate': 'abc',
    'streaming_server_resize': 'yes',
    'target_dir': '/nonexistent/f29',
    'enabled': True,
}


class RemoteFramePageTest(RemoteCameraTestCase):
    """The frame page of a remote camera is built from the values it shows, nothing else."""

    handler_cls = PictureHandler

    def setUp(self):
        super().setUp()
        answer = GetConfigResponse(remote_ui_config=dict(_REMOTE_UI_CONFIG), error=None)
        self._convert = patch('motioneye.config.motion_camera_ui_to_dict')
        self._render = patch('motioneye.template.render', return_value='<html></html>')
        self._extra_patches = [
            patch('motioneye.remote.get_config', AsyncMock(return_value=answer)),
            self._convert,
            self._render,
        ]
        self.convert = self._convert.start()
        self.render = self._render.start()
        self._extra_patches[0].start()

    def tearDown(self):
        for p in self._extra_patches:
            p.stop()
        super().tearDown()

    def test_the_remote_answer_is_not_converted_into_a_motion_config(self):
        response = self.fetch_as_admin('/picture/1/frame/')

        self.assertEqual(200, response.code)
        self.convert.assert_not_called()
        camera_config = self.render.call_args.kwargs['camera_config']
        self.assertEqual('<b>cam</b>', camera_config['camera_name'])
        self.assertEqual(0, camera_config['stream_maxrate'])
        self.assertTrue(camera_config['@webcam_server_resize'])
        self.assertEqual('motioneye', camera_config['@proto'])
        self.assertEqual('<b>cam</b>', self.render.call_args.kwargs['title'])
