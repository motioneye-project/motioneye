import asyncio
import importlib.util
import logging
import unittest
from unittest import mock

import tornado.testing
from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.testing import bind_unused_port
from tornado.web import RequestHandler

from motioneye import settings
from motioneye.utils.mjpeg import test_mjpeg_url
from tests import WebTestCase


class RawStreamServer(TCPServer):
    # like `rpicam-vid --listen -o tcp://`: JPEG bytes without any HTTP response
    async def handle_stream(self, stream, address):
        await stream.write(b'\xff\xd8\xff\xe0' + b'\x00' * 70000)
        stream.close()


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

        class EndlessMjpegHandler(RequestHandler):
            async def get(self):
                self.set_header('Content-Type', 'multipart/x-mixed-replace')
                try:
                    while True:
                        self.write(b'--frame\r\n\r\n' + b'\xff' * 1000)
                        await self.flush()
                        await asyncio.sleep(0.05)
                except StreamClosedError:
                    pass

        return [('/', MjpegHandler), ('/stream', EndlessMjpegHandler)]

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

    @tornado.testing.gen_test
    async def test_test_mjpeg_url_connection_refused(self):
        sock, port = bind_unused_port()
        sock.close()

        data = {'port': port, 'path': '/video.cgi?user=u&pwd=s3cret'}
        debug = mock.patch.object(logging, 'debug')
        with self.assertLogs(level='ERROR') as logs, debug as debug_log:
            resp = await test_mjpeg_url(data, auth_modes=['basic'], allow_jpeg=True)
        self.assertIsNone(resp.cameras)
        self.assertTrue(resp.error)

        # both log lines leave out the query, which may hold a password
        ours = str(logs.output) + str(debug_log.call_args_list)
        self.assertIn('/video.cgi using no authentication', ours)
        self.assertIn('/video.cgi failed', ours)
        self.assertNotIn('s3cret', ours)

    @tornado.testing.gen_test
    async def test_test_mjpeg_url_not_http(self):
        sock, port = bind_unused_port()
        server = RawStreamServer()
        server.add_sockets([sock])
        try:
            resp = await test_mjpeg_url(
                {'port': port}, auth_modes=['basic'], allow_jpeg=True
            )
        finally:
            server.stop()

        self.assertIsNone(resp.cameras)
        self.assertTrue(resp.error)

    @tornado.testing.gen_test(timeout=10)
    async def test_test_mjpeg_url_stream_timeout_after_detection(self):
        asyncio_log = logging.getLogger('asyncio')
        short_timeout = mock.patch.object(settings, 'REMOTE_REQUEST_TIMEOUT', 1)
        with short_timeout, mock.patch.object(asyncio_log, 'error') as log_error:
            resp = await test_mjpeg_url(
                {'port': self.get_http_port(), 'path': '/stream'},
                auth_modes=['basic'],
                allow_jpeg=True,
            )
            self.assertIsNone(resp.error)
            self.assertEqual('MJPEG Network Camera', resp.cameras[0]['name'])

            # the stream never ends, so its request still runs into the timeout
            await asyncio.sleep(2)

        log_error.assert_not_called()


@unittest.skipUnless(importlib.util.find_spec('pycurl'), 'pycurl is not installed')
class UtilsMjpegCurlTest(UtilsMjpegTest):
    # the same tests with the curl client that motionEye's server uses
    def setUp(self) -> None:
        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
        self.addCleanup(AsyncHTTPClient.configure, None)
        super().setUp()


if __name__ == '__main__':
    tornado.testing.main()
