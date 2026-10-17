from __future__ import annotations

from json import loads
from unittest.mock import AsyncMock, patch

from motioneye.handlers.picture import PictureHandler
from motioneye.utils import CommonExternalResponse
from tests.test_handlers import RemoteCameraTestCase


def _answer(data, content_type, content_disposition):
    return CommonExternalResponse(
        result={
            'data': data,
            'content_type': content_type,
            'content_disposition': content_disposition,
        }
    )


class RemoteMediaDownloadTest(RemoteCameraTestCase):
    """The hub sets its own headers on a remote camera's zip and timelapse downloads."""

    handler_cls = PictureHandler

    def fetch_zip(self, answer):
        with patch(
            'motioneye.remote.get_zipped_content', AsyncMock(return_value=answer)
        ):
            return self.fetch_as_admin('/picture/1/zipped/g/?key=k')

    def fetch_timelapse(self, answer):
        with patch(
            'motioneye.remote.get_timelapse_movie', AsyncMock(return_value=answer)
        ):
            return self.fetch_as_admin('/picture/1/timelapse/g/?key=k')

    def test_zip_keeps_the_remote_file_name_with_the_zip_extension(self):
        response = self.fetch_zip(
            _answer(b'zip', 'application/zip', 'attachment; filename=Cam_g.zip;')
        )

        self.assertEqual(200, response.code)
        self.assertEqual('application/zip', response.headers['Content-Type'])
        self.assertEqual(
            'attachment; filename=Cam_g.zip;', response.headers['Content-Disposition']
        )
        self.assertEqual('nosniff', response.headers['X-Content-Type-Options'])
        self.assertEqual(b'zip', response.body)

    def test_zip_file_name_is_reduced_to_its_base_name_letters_and_digits(self):
        response = self.fetch_zip(
            _answer(
                b'zip',
                'application/zip; charset=x',
                'inline; filename="../sub/dir/a b;c.html"',
            )
        )

        self.assertEqual(200, response.code)
        self.assertEqual('application/zip', response.headers['Content-Type'])
        self.assertEqual(
            'attachment; filename=a_b.zip;', response.headers['Content-Disposition']
        )

    def test_zip_without_a_file_name_is_named_after_the_camera(self):
        response = self.fetch_zip(_answer(b'zip', 'application/zip', None))

        self.assertEqual(200, response.code)
        self.assertEqual(
            'attachment; filename=Camera1_g.zip;',
            response.headers['Content-Disposition'],
        )

    def test_zip_with_a_document_type_is_an_error(self):
        response = self.fetch_zip(
            _answer(b'<html>', 'text/html', 'attachment; filename=page.zip;')
        )

        self.assertEqual(200, response.code)
        self.assertEqual('application/json', response.headers['Content-Type'])
        self.assertIn('unexpected content type', loads(response.body)['error'])

    def test_a_json_answer_is_an_error_with_the_remote_message(self):
        response = self.fetch_zip(
            _answer(
                b'{"error": "no such key"}',
                'application/json',
                'attachment; filename=x.zip;',
            )
        )

        self.assertEqual(200, response.code)
        self.assertIn('no such key', loads(response.body)['error'])

    def test_timelapse_keeps_the_movie_type_and_extension(self):
        response = self.fetch_timelapse(
            _answer(b'mp4', 'video/mp4', 'attachment; filename=Cam_g.mp4;')
        )

        self.assertEqual(200, response.code)
        self.assertEqual('video/mp4', response.headers['Content-Type'])
        self.assertEqual(
            'attachment; filename=Cam_g.mp4;', response.headers['Content-Disposition']
        )

    def test_timelapse_with_a_document_type_is_an_error(self):
        response = self.fetch_timelapse(
            _answer(b'<html>', 'text/html', 'inline; filename="page.html"')
        )

        self.assertEqual(200, response.code)
        self.assertIn('unexpected content type', loads(response.body)['error'])
