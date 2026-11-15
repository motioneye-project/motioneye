from json import loads
from unittest.mock import AsyncMock, patch

from motioneye import config, remote, uploadservices
from tests.test_handlers import HandlerTestCase

NAVIGATION = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'

_LOCAL = {'@proto': 'v4l2', '@id': 1}
_REMOTE = {'@proto': 'motioneye', '@id': 2, '@host': '192.168.1.20'}


class AuthorizeTest(HandlerTestCase):
    """The link to obtain an upload service key comes from the server that redeems
    the key, as only that one has the PKCE verifier of the link (#2516)."""

    def _authorize(self, camera, accept='*/*'):
        with (
            patch.object(config, 'get_camera_ids', return_value=[1, 2]),
            patch.object(config, 'get_camera', return_value=camera),
        ):
            return self.fetch(
                f'/config/{camera["@id"]}/authorize/?service=gdrive',
                headers={'Accept': accept, 'Cookie': self.make_session_cookie('admin')},
                follow_redirects=False,
            )

    def test_link_keeps_the_pending_verifier(self):
        # a new link replaces the verifier, and the session cookie is SameSite=Lax
        with patch.object(uploadservices, 'get_authorize_url') as local:
            response = self._authorize(_LOCAL, accept=NAVIGATION)

        self.assertEqual(403, response.code)
        local.assert_not_called()

    def test_local_camera_link_is_created_here(self):
        with (
            patch.object(
                uploadservices, 'get_authorize_url', return_value='https://g/local'
            ) as local,
            patch.object(remote, 'get_authorize_url', new=AsyncMock()) as other,
        ):
            response = self._authorize(_LOCAL)

        # as JSON, for the page and for a hub
        self.assertEqual(200, response.code)
        self.assertEqual({'url': 'https://g/local'}, loads(response.body))
        local.assert_called_once_with('gdrive')
        other.assert_not_called()

    def test_remote_camera_link_comes_from_the_remote(self):
        with (
            patch.object(uploadservices, 'get_authorize_url') as local,
            patch.object(
                remote,
                'get_authorize_url',
                new=AsyncMock(return_value='https://g/remote'),
            ) as other,
        ):
            response = self._authorize(_REMOTE)

        self.assertEqual(200, response.code)
        self.assertEqual({'url': 'https://g/remote'}, loads(response.body))
        other.assert_awaited_once_with(_REMOTE, 'gdrive')
        local.assert_not_called()

    def test_unknown_camera(self):
        response = self._authorize({'@id': 9})

        self.assertEqual(404, response.code)
