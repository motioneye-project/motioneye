from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from motioneye import remote
from motioneye.handlers.movie import MovieHandler
from motioneye.handlers.movie_playback import MoviePlaybackHandler
from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import (
    _FAKE_CAMERA_CONFIG,
    HandlerTestCase,
    RemoteCameraTestCase,
)


class LocalMediaExtensionTest(HandlerTestCase):
    """A local camera only serves and deletes the file type of the endpoint."""

    handler_cls = PictureHandler

    def setUp(self):
        super().setUp()
        self._tmp = TemporaryDirectory()
        self._camera_patch = patch(
            'motioneye.config.get_camera',
            return_value={**_FAKE_CAMERA_CONFIG, 'target_dir': self._tmp.name},
        )
        self._camera_patch.start()
        # on_finish() of the playback handler removes stale files of its cache dir
        self._cache = TemporaryDirectory()
        self._cache_patch = patch.object(
            MoviePlaybackHandler, 'tmpdir', self._cache.name
        )
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()
        self._camera_patch.stop()
        self._cache.cleanup()
        self._tmp.cleanup()
        super().tearDown()

    def _file(self, name, data=b'data'):
        path = Path(self._tmp.name, name)
        path.write_bytes(data)
        return path

    def _request(self, method, url, user='admin'):
        headers = {'Cookie': self.make_session_cookie(user)} if user else {}
        return self.fetch(
            url, method=method, headers=headers, body='' if method == 'POST' else None
        )

    def test_the_wrong_type_is_refused_and_the_files_are_kept(self):
        files = {
            name: self._file(name) for name in ('photo.jpg', 'clip.mp4', 'note.txt')
        }
        requests = (
            ('GET', '/picture/1/download/note.txt'),
            ('GET', '/picture/1/download/clip.mp4'),
            ('GET', '/picture/1/preview/note.txt'),
            ('GET', '/picture/1/preview/clip.mp4'),
            ('POST', '/picture/1/delete/note.txt'),
            ('POST', '/picture/1/delete/clip.mp4'),
            ('GET', '/movie/1/preview/note.txt'),
            ('GET', '/movie/1/preview/photo.jpg'),
            ('GET', '/movie/1/playback/note.txt'),
            ('GET', '/movie/1/playback/photo.jpg'),
            ('GET', '/movie/1/download/note.txt'),
            ('GET', '/movie/1/download/photo.jpg'),
            ('POST', '/movie/1/delete/note.txt'),
            ('POST', '/movie/1/delete/photo.jpg'),
        )
        for method, url in requests:
            with self.subTest(method=method, url=url):
                response = self._request(method, url)

                self.assertEqual(403, response.code)
                error = json.loads(response.body)['error']
                self.assertIn('is not a', error)
                self.assertIn('file', error)

        for name, path in files.items():
            self.assertEqual(b'data', path.read_bytes(), name)

    def test_the_extension_is_not_case_sensitive(self):
        self._file('PHOTO.JPG', b'jpeg')
        self._file('CLIP.MP4', b'mp4')

        response = self._request('GET', '/picture/1/download/PHOTO.JPG')
        self.assertEqual((200, b'jpeg'), (response.code, response.body))

        response = self._request('GET', '/movie/1/playback/CLIP.MP4')
        self.assertEqual((200, b'mp4'), (response.code, response.body))
        self.assertEqual('video/mp4', response.headers['Content-Type'])

    def test_the_matching_type_is_served(self):
        self._file('photo.jpg', b'jpeg')
        self._file('clip.mp4', b'mp4')
        self._file('clip.mp4.thumb', b'thumb')

        for url, body, content_type in (
            ('/picture/1/download/photo.jpg', b'jpeg', 'image/jpeg'),
            ('/picture/1/preview/photo.jpg', b'jpeg', 'image/jpeg'),
            ('/movie/1/preview/clip.mp4', b'thumb', 'image/jpeg'),
            ('/movie/1/playback/clip.mp4', b'mp4', 'video/mp4'),
            ('/movie/1/download/clip.mp4', b'mp4', 'video/mp4'),
        ):
            with self.subTest(url=url):
                response = self._request('GET', url)

                self.assertEqual(200, response.code)
                self.assertEqual(body, response.body)
                self.assertEqual(content_type, response.headers['Content-Type'])

    def test_the_matching_type_is_deleted(self):
        photo = self._file('photo.jpg')
        clip = self._file('clip.mp4')

        self.assertEqual(200, self._request('POST', '/picture/1/delete/photo.jpg').code)
        self.assertEqual(200, self._request('POST', '/movie/1/delete/clip.mp4').code)

        self.assertFalse(photo.exists())
        self.assertFalse(clip.exists())

    def test_a_refused_extension_is_checked_after_the_login(self):
        self._file('note.txt')

        for method, url in (
            ('GET', '/picture/1/download/note.txt'),
            ('POST', '/picture/1/delete/note.txt'),
            ('GET', '/movie/1/playback/note.txt'),
            ('POST', '/movie/1/delete/note.txt'),
        ):
            with self.subTest(method=method, url=url):
                response = self._request(method, url, user=None)

                self.assertEqual('unauthorized', json.loads(response.body)['error'])


class RemoteMediaExtensionTest(RemoteCameraTestCase):
    """A remote camera is not checked on the hub, the remote decides."""

    handler_cls = MovieHandler

    def test_the_request_is_passed_on_to_the_remote(self):
        for method, url, content_type in (
            ('GET', '/picture/1/download/clip.webp', 'image/jpeg'),
            ('GET', '/picture/1/preview/clip.webp', 'image/jpeg'),
            ('POST', '/movie/1/delete/clip.webm', 'application/json'),
        ):
            with self.subTest(method=method, url=url):
                answer = SimpleNamespace(
                    code=200,
                    body=b'{}' if content_type.endswith('json') else b'data',
                    headers={'Content-Type': content_type},
                    error=None,
                )
                fetch = AsyncMock(return_value=answer)
                client = patch.object(
                    remote, 'AsyncHTTPClient', return_value=SimpleNamespace(fetch=fetch)
                )
                with client:
                    response = self.fetch(
                        url,
                        method=method,
                        body='' if method == 'POST' else None,
                        headers={'Cookie': self.make_session_cookie('admin')},
                    )

                self.assertEqual(200, response.code)
                fetch.assert_awaited_once()
                request = fetch.call_args.args[0]
                self.assertEqual(method, request.method)
                self.assertEqual('http://cam.example:8765' + url, request.url)
