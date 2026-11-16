from json import loads
from unittest.mock import AsyncMock, patch

import tornado.testing

from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import HandlerTestCase

NAVIGATION = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
TIMELAPSE = '/picture/1/timelapse/group/?interval=60&framerate=20'


class PreparePictureHandlerTest(HandlerTestCase):
    handler_cls = PictureHandler

    def setUp(self):
        super().setUp()
        patches = (
            patch(
                'motioneye.mediafiles.check_timelapse_movie',
                return_value={'progress': -1, 'data': None},
            ),
            patch('motioneye.mediafiles.make_timelapse_movie'),
            patch(
                'motioneye.mediafiles.get_zipped_content',
                new=AsyncMock(return_value=b'zip'),
            ),
        )
        _, self.make_timelapse, self.make_zip = (p.start() for p in patches)
        for p in patches:
            self.addCleanup(p.stop)

    def _fetch(self, path, accept, **headers):
        return self.fetch(
            path,
            headers={
                'Accept': accept,
                'Cookie': self.make_session_cookie('admin'),
                **headers,
            },
        )

    def test_fetch_metadata_of_another_site_or_a_navigation_is_refused(self):
        # what browsers send to HTTPS and localhost, whatever the Accept header
        for headers in (
            {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'no-cors'},
            {'Sec-Fetch-Site': 'same-site', 'Sec-Fetch-Mode': 'cors'},
            {'Sec-Fetch-Site': 'none', 'Sec-Fetch-Mode': 'navigate'},
            {'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'navigate'},
        ):
            with self.subTest(**headers):
                response = self._fetch(TIMELAPSE, '*/*', **headers)
                self.assertEqual(403, response.code)

        self.make_timelapse.assert_not_called()

    def test_the_page_own_request_with_fetch_metadata_still_starts_timelapse(self):
        headers = {'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors'}
        response = self._fetch(TIMELAPSE, '*/*', **headers)
        self.assertEqual(200, response.code)
        self.make_timelapse.assert_called_once()

    def test_navigation_does_not_start_timelapse(self):
        response = self._fetch(TIMELAPSE, NAVIGATION)
        self.assertEqual(403, response.code)
        self.make_timelapse.assert_not_called()

    def test_navigation_does_not_prepare_zip(self):
        response = self._fetch('/picture/1/zipped/group/', NAVIGATION)
        self.assertEqual(403, response.code)
        self.make_zip.assert_not_called()

    def test_ajax_and_hub_start_timelapse(self):
        response = self._fetch(TIMELAPSE, '*/*')
        self.assertEqual(200, response.code)
        self.assertEqual({'progress': -1}, loads(response.body))
        self.make_timelapse.assert_called_once()

    def test_ajax_and_hub_prepare_zip(self):
        response = self._fetch('/picture/1/zipped/group/', '*/*')
        self.assertEqual(200, response.code)
        self.assertIn('key', loads(response.body))
        self.make_zip.assert_called_once()

    def test_download_by_key_stays_a_navigation(self):
        with patch('motioneye.mediafiles.get_prepared_cache', return_value=b'zip'):
            response = self._fetch('/picture/1/zipped/group/?key=abc', NAVIGATION)
        self.assertEqual(200, response.code)
        self.assertEqual(b'zip', response.body)


if __name__ == '__main__':
    tornado.testing.main()
