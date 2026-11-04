import logging
from asyncio import sleep
from unittest import mock

from tornado.concurrent import Future
from tornado.httpclient import HTTPResponse
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.testing import bind_unused_port, gen_test, main
from tornado.web import RequestHandler

from motioneye import settings
from motioneye.utils.mjpeg import test_mjpeg_url
from tests import WebTestCase
from tests.test_utils import digest_params, digest_response


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
                        await sleep(0.05)
                except StreamClosedError:
                    pass

        class RedirectHandler(RequestHandler):
            def get(self):
                self.redirect(test.location)

        return [
            ('/', MjpegHandler),
            ('/stream', EndlessMjpegHandler),
            ('/redirect', RedirectHandler),
        ]

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

    @gen_test
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

    @gen_test
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

    @gen_test(timeout=10)
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
            await sleep(2)

        log_error.assert_not_called()

    @gen_test
    async def test_the_certificate_of_an_https_camera_is_verified(self):
        def fetch(request, **kwargs):
            fetch_future: Future = Future()
            fetch_future.set_result(HTTPResponse(request, 200))
            return fetch_future

        client = mock.Mock(fetch=mock.Mock(side_effect=fetch))
        client_patch = mock.patch(
            'motioneye.utils.mjpeg.AsyncHTTPClient', return_value=client
        )
        camera = {'scheme': 'https', 'host': 'cam.example', 'port': '443'}
        with client_patch, self.assertLogs(level='ERROR'):
            resp = await test_mjpeg_url(camera, auth_modes=['basic'], allow_jpeg=True)

        request = client.fetch.call_args.args[0]
        self.assertEqual('https://cam.example:443', request.url)
        # None is Tornado's default here, which verifies
        self.assertIsNot(False, request.validate_cert)
        self.assertEqual('not a supported network camera', resp.error)

    @gen_test
    async def test_an_unsupported_scheme_error_leaves_out_the_query(self):
        camera = {'scheme': 'mjpeg', 'port': 80, 'path': '/video.cgi?pwd=s3cret'}
        with self.assertLogs(level='ERROR') as logs:
            resp = await test_mjpeg_url(camera, auth_modes=['basic'], allow_jpeg=True)

        self.assertIsNone(resp.cameras)
        self.assertNotIn('s3cret', resp.error + str(logs.output))

    @gen_test
    async def test_a_redirect_is_reported_not_followed(self):
        sock, port = bind_unused_port()
        sock.close()  # where it redirects to nothing answers
        self.location = f'http://user:pw@127.0.0.1:{port}/video.cgi?pwd=s3cret'

        camera = {'port': self.get_http_port(), 'path': '/redirect'}
        with self.assertLogs(level='ERROR') as logs:
            resp = await test_mjpeg_url(camera, auth_modes=['basic'], allow_jpeg=True)

        self.assertIsNone(resp.cameras)
        self.assertEqual(
            f'the camera redirects to http://127.0.0.1:{port}/video.cgi', resp.error
        )
        self.assertNotIn('s3cret', str(logs.output))


class DigestCameraTest(WebTestCase):
    """A camera asking for digest, which Tornado's client leaves to motionEye."""

    def setUp(self) -> None:
        super().setUp()
        self.algorithm = 'MD5'
        self.authorizations: list[str] = []

    def get_handlers(self):
        test = self

        class DigestHandler(RequestHandler):
            def get(self):
                authorization = self.request.headers.get('Authorization', '')
                test.authorizations.append(authorization)
                if authorization.startswith('Digest '):
                    params = digest_params(authorization)
                    response = digest_response(params, 'GET', 'pw')
                    if (params['uri'], params['response']) == (
                        self.request.uri,
                        response,
                    ):
                        self.set_header('Content-Type', 'multipart/x-mixed-replace')
                        self.write('mjpeg')
                        return

                self.set_status(401)
                self.add_header('WWW-Authenticate', 'Basic realm="cam"')
                self.add_header(
                    'WWW-Authenticate',
                    'Digest realm="cam", qop="auth,auth-int", nonce="n0nce", '
                    f'algorithm={test.algorithm}',
                )

        return [(r'/.*', DigestHandler)]

    def check(self, password, path='/video.cgi?res=hi', auth_modes=('basic', 'digest')):
        camera = {
            'port': self.get_http_port(),
            'path': path,
            'username': 'user',
            'password': password,
        }
        return test_mjpeg_url(camera, auth_modes=list(auth_modes), allow_jpeg=False)

    @gen_test
    async def test_digest_is_answered_after_basic_was_refused(self):
        for algorithm in ('MD5', 'SHA-256'):
            with self.subTest(algorithm):
                self.algorithm = algorithm
                self.authorizations.clear()

                resp = await self.check('pw')

                self.assertIsNone(resp.error)
                self.assertEqual('MJPEG Network Camera', resp.cameras[0]['name'])
                self.assertEqual(
                    ['Basic', 'Digest'], [a.split()[0] for a in self.authorizations]
                )

    @gen_test
    async def test_an_empty_path_is_answered_for_the_slash_sent(self):
        resp = await self.check('pw', path='')

        self.assertIsNone(resp.error)

    @gen_test
    async def test_a_wrong_password_fails_authentication(self):
        with self.assertLogs(level='ERROR'):
            resp = await self.check('wrong')

        self.assertEqual('authentication failed', resp.error)
        self.assertEqual(2, len(self.authorizations))

    @gen_test
    async def test_no_digest_without_a_usable_challenge(self):
        for case, algorithm, auth_modes in (
            ('a network camera tries basic only', 'MD5', ['basic']),
            ('an unsupported algorithm', 'SHA-512-256', ['basic', 'digest']),
        ):
            with self.subTest(case):
                self.algorithm = algorithm
                self.authorizations.clear()
                with self.assertLogs(level='ERROR'):
                    resp = await self.check('pw', auth_modes=auth_modes)

                self.assertEqual('authentication failed', resp.error)
                self.assertEqual(1, len(self.authorizations))


if __name__ == '__main__':
    main()
