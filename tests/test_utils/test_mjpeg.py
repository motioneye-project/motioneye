import tornado.testing
from tornado.concurrent import Future
from tornado.web import RequestHandler

from motioneye.utils.mjpeg import test_mjpeg_url
from tests import WebTestCase


class UtilsMjpegTest(WebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data = None

    def get_handlers(self):
        test = self

        class MjpegHandler(RequestHandler):
            async def get(self):
                if 'image/jpeg' in test.data:
                    self.set_header('Content-Type', 'image/jpeg')

                if 'mjpeg' in test.data:
                    self.set_header('Content-Type', 'multipart/x-mixed-replace')
                self.write(test.data)
                await self.flush()

        return [('/', MjpegHandler)]

    def test_test_mjpeg_url_invalid_data(self):
        self.data = 'Some random string'

        callback_result = []

        def mock_on_response(future: Future) -> None:
            resp = future.result()
            self.stop()
            callback_result.append((resp.cameras, resp.error))

        future = test_mjpeg_url(
            {'port': self.get_http_port()}, auth_modes=['basic'], allow_jpeg=True
        )
        future.add_done_callback(mock_on_response)

        self.wait()
        self.assertEqual(1, len(callback_result))
        self.assertIsNone(callback_result[0][0])
        self.assertEqual('not a supported network camera', callback_result[0][1])

    def test_test_mjpeg_url_jpeg_cam(self):
        self.data = 'image/jpeg camera'
        callback_result = []

        def mock_on_response(future: Future) -> None:
            resp = future.result()
            self.stop()
            callback_result.append((resp.cameras, resp.error))

        future = test_mjpeg_url(
            {'port': self.get_http_port()}, auth_modes=['basic'], allow_jpeg=True
        )
        future.add_done_callback(mock_on_response)

        self.wait()
        self.assertEqual(1, len(callback_result))
        self.assertIsNone(callback_result[0][1])

        cams = callback_result[0][0]
        self.assertEqual(1, len(cams))

        cam = cams[0]
        self.assertDictEqual(
            {'id': 1, 'name': 'JPEG Network Camera', 'keep_alive': True}, cam
        )

    def test_test_mjpeg_url_mjpeg_cam(self):
        self.data = 'mjpeg camera'
        callback_result = []

        def mock_on_response(future: Future) -> None:
            resp = future.result()
            self.stop()
            callback_result.append((resp.cameras, resp.error))

        future = test_mjpeg_url(
            {'port': self.get_http_port()}, auth_modes=['basic'], allow_jpeg=True
        )
        future.add_done_callback(mock_on_response)

        self.wait()
        self.assertEqual(1, len(callback_result))
        self.assertIsNone(callback_result[0][1])

        cams = callback_result[0][0]
        self.assertEqual(1, len(cams))

        cam = cams[0]
        self.assertDictEqual(
            {'id': 1, 'name': 'MJPEG Network Camera', 'keep_alive': True}, cam
        )


if __name__ == '__main__':
    tornado.testing.main()
