from tempfile import mkdtemp
from typing import Generic, Type, TypeVar
from unittest.mock import MagicMock, patch

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, RequestHandler

from motioneye.server import make_app

__all__ = ('HandlerTestCase',)

T = TypeVar('T', bound=RequestHandler)

# Minimal camera config used across all handler tests.
_FAKE_CAMERA_ID = 1
_FAKE_TARGET_DIR = mkdtemp()
_FAKE_CAMERA_CONFIG = {
    '@id': _FAKE_CAMERA_ID,
    '@enabled': True,
    '@admin_only': False,
    'camera_name': 'test',
    'netcam_url': 'http://localhost/stream',  # makes is_local_motion_camera() True
    'target_dir': _FAKE_TARGET_DIR,
    # minimal motion defaults so the config is complete enough
    'framerate': 2,
    'pre_capture': 1,
}


class HandlerTestCase(AsyncHTTPTestCase, Generic[T]):
    handler_cls: Type[T]

    def get_app(self) -> Application:
        self.app = make_app()
        return self.app

    def setUp(self):
        # Patch config look-ups so the handler always finds camera 1
        # with a known target_dir (needed by validate_paths).
        self._patches = [
            patch(
                'motioneye.config.get_camera_ids',
                return_value=[_FAKE_CAMERA_ID],
            ),
            patch(
                'motioneye.config.get_camera',
                return_value=_FAKE_CAMERA_CONFIG,
            ),
        ]
        for p in self._patches:
            p.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        for p in self._patches:
            p.stop()

    def get_handler(self, request: MagicMock | None = None) -> T:
        req = request or MagicMock()
        return self.handler_cls(self.app, req)
