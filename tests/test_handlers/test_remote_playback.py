from __future__ import annotations

from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, patch

from motioneye.handlers.movie_playback import MoviePlaybackHandler
from motioneye.utils import CommonExternalResponse
from tests.test_handlers import RemoteCameraTestCase


class RemoteMoviePlaybackTest(RemoteCameraTestCase):
    """A remote movie is served with a type taken from its extension, never sniffed."""

    handler_cls = MoviePlaybackHandler

    def setUp(self):
        super().setUp()
        self._tmpdir = mkdtemp()
        self._tmpdir_patch = patch.object(MoviePlaybackHandler, 'tmpdir', self._tmpdir)
        self._tmpdir_patch.start()

    def tearDown(self):
        self._tmpdir_patch.stop()
        rmtree(self._tmpdir, True)
        super().tearDown()

    def fetch_playback(self, filename, data):
        with patch(
            'motioneye.remote.get_media_content',
            AsyncMock(return_value=CommonExternalResponse(result=data)),
        ):
            return self.fetch_as_admin('/movie/1/playback/' + filename)

    def test_an_unknown_extension_is_served_as_octet_stream(self):
        response = self.fetch_playback('f29test.html', b'<html>')

        self.assertEqual(200, response.code)
        self.assertEqual('application/octet-stream', response.headers['Content-Type'])
        self.assertEqual('nosniff', response.headers['X-Content-Type-Options'])

    def test_a_movie_extension_keeps_its_type(self):
        response = self.fetch_playback('f29test.mp4', b'mp4')

        self.assertEqual(200, response.code)
        self.assertEqual('video/mp4', response.headers['Content-Type'])
        self.assertEqual('nosniff', response.headers['X-Content-Type-Options'])

    def test_an_mpg_movie_is_video_mpeg(self):
        response = self.fetch_playback('f29test.mpg', b'mpg')

        self.assertEqual(200, response.code)
        self.assertEqual('video/mpeg', response.headers['Content-Type'])
