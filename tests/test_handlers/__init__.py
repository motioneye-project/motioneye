import atexit
import os
from secrets import token_hex
from shutil import rmtree
from tempfile import mkdtemp
from time import time
from typing import Generic, Optional, Type, TypeVar
from unittest.mock import MagicMock, patch

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, RequestHandler, create_signed_value

from motioneye.handlers.base import _SESSION_EXPIRY_SECONDS, _session_store
from motioneye.server import make_app

__all__ = ('HandlerTestCase',)

T = TypeVar('T', bound=RequestHandler)

# Minimal camera config used across all handler tests.
_FAKE_CAMERA_ID = 1
_FAKE_TARGET_DIR = mkdtemp()

# Create a symlink inside _FAKE_TARGET_DIR that points outside,
# used by path validation tests to verify camera directory escape detection.
_FAKE_OUTSIDE_DIR = mkdtemp()
_FAKE_ESCAPE_LINK = 'escape'
os.symlink(_FAKE_OUTSIDE_DIR, os.path.join(_FAKE_TARGET_DIR, _FAKE_ESCAPE_LINK))
atexit.register(rmtree, _FAKE_TARGET_DIR, True)
atexit.register(rmtree, _FAKE_OUTSIDE_DIR, True)

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
        # Wipe any sessions left over from this test so the next test starts clean.
        _session_store.clear()

    def get_handler(self, request: Optional[MagicMock] = None) -> T:
        req = request or MagicMock()
        return self.handler_cls(self.app, req)

    def make_session_cookie(self, user_type: str) -> str:
        """Insert a session into _session_store and return a matching Cookie header value.

        This bypasses the login flow so handler tests can authenticate directly
        without repeating the credential round-trip that is already covered by
        the dedicated login tests.
        """
        session_id = token_hex(32)
        _session_store[session_id] = {
            'user': user_type,
            'expires': time() + _SESSION_EXPIRY_SECONDS,
        }
        signed = create_signed_value(
            self.app.settings['cookie_secret'], 'user', session_id
        )
        return 'user=' + signed.decode()
