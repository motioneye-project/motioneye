import asyncio
from unittest.mock import patch

from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.testing import AsyncTestCase, bind_unused_port, gen_test

from motioneye import settings
from motioneye.mjpgclient import MjpgClient
from tests.test_utils import digest_params, digest_response


class DigestTest(AsyncTestCase):
    """motion's stream asks for digest; only its first request is answered."""

    def setUp(self):
        super().setUp()
        self.challenge = ''
        self.requests: list[str] = []
        test = self

        class Stream(TCPServer):
            async def handle_stream(self, stream, address):
                try:
                    while True:
                        test.requests.append(
                            (await stream.read_until(b'\r\n\r\n')).decode()
                        )
                        if len(test.requests) == 1:
                            await stream.write(
                                b'HTTP/1.0 401 Unauthorized\r\n'
                                b'WWW-Authenticate: '
                                + test.challenge.encode()
                                + b'\r\n\r\n'
                            )

                except StreamClosedError:
                    pass

        sock, self.port = bind_unused_port()
        self.server = Stream()
        self.server.add_sockets([sock])
        restart = patch.object(settings, 'MOTION_RESTART_ON_ERRORS', False)
        restart.start()
        self.addCleanup(restart.stop)

    def tearDown(self):
        self.server.stop()  # while the IO loop is still open
        super().tearDown()

    async def connect(self, challenge):
        self.challenge = challenge
        client = MjpgClient(1, self.port, 'user', 'pw', 'digest')
        await client.do_connect()
        await asyncio.sleep(0.5)
        client.close()

    @gen_test
    async def test_the_challenge_is_answered(self):
        await self.connect('Digest realm="cam", qop="auth", nonce="n0nce"')

        self.assertEqual(2, len(self.requests))
        authorization = self.requests[1].split('Authorization: ')[1].split('\r\n')[0]
        params = digest_params(authorization)
        self.assertEqual('/', params['uri'])
        self.assertEqual(digest_response(params, 'GET', 'pw'), params['response'])

    @gen_test
    async def test_a_challenge_it_cannot_answer_is_not_answered(self):
        with self.assertLogs(level='ERROR') as logs:
            await self.connect('Digest realm="cam", nonce="n", algorithm=SHA-512-256')

        self.assertEqual(1, len(self.requests))
        self.assertIn('unknown authentication header', logs.output[0])
