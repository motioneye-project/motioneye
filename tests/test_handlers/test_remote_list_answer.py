from __future__ import annotations

from json import loads
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from motioneye.handlers.config import ConfigHandler
from tests.test_handlers import RemoteCameraTestCase


class RemoteListAnswerShapeTest(RemoteCameraTestCase):
    """A remote answering its config with another shape fails only its own camera."""

    handler_cls = ConfigHandler

    def setUp(self):
        super().setUp()
        answer = SimpleNamespace(error=None, code=200, body=b'[]')
        self._extra_patches = [
            patch('motioneye.config.get_main', return_value={'@enabled': True}),
            patch('motioneye.remote._send_request', AsyncMock(return_value=answer)),
        ]
        for p in self._extra_patches:
            p.start()

    def tearDown(self):
        for p in self._extra_patches:
            p.stop()
        super().tearDown()

    def test_an_answer_of_another_shape_marks_only_that_camera_as_failed(self):
        response = self.fetch_as_admin('/config/list/')

        self.assertEqual(200, response.code)
        cameras = loads(response.body)['cameras']
        self.assertEqual(1, len(cameras))
        self.assertTrue(cameras[0]['connection_failed'])
        self.assertIn('unexpected answer', cameras[0]['connection_error'])
