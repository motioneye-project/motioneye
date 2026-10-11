import socket
from unittest import mock

import tornado.testing
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.testing import bind_unused_port

from motioneye import settings
from motioneye.utils.rtsp import test_rtsp_url


class RtspCamera(TCPServer):
    # answers the OPTIONS request with a fixed reply, then keeps the connection open
    def __init__(self, reply: bytes):
        super().__init__()
        self.reply = reply

    async def handle_stream(self, stream, address):
        try:
            await stream.read_until(b'\r\n\r\n')
            await stream.write(self.reply)
            await stream.read_until_close()
        except StreamClosedError:
            pass


class UtilsRtspTest(tornado.testing.AsyncTestCase):
    async def check(self, reply: bytes, **data):
        sock, port = bind_unused_port()
        camera = RtspCamera(reply)
        camera.add_sockets([sock])
        try:
            return await test_rtsp_url({'port': port, **data})
        finally:
            camera.stop()

    @tornado.testing.gen_test
    async def test_test_rtsp_url_camera(self):
        resp = await self.check(b'RTSP/1.0 200 OK\r\nCSeq: 1\r\nServer: Cam\r\n\r\n')
        self.assertIsNone(resp.error)
        self.assertEqual(['tcp', 'udp'], [c['id'] for c in resp.cameras])

    @tornado.testing.gen_test
    async def test_test_rtsp_url_connect_timeout(self):
        # Linux drops new connections to a listener whose accept queue is full,
        # so connect() hangs like with a camera that does not answer
        sock, port = bind_unused_port()
        sock.listen(0)
        queued = socket.create_connection(('127.0.0.1', port))
        try:
            with mock.patch.object(settings, 'MJPG_CLIENT_TIMEOUT', 1):
                resp = await test_rtsp_url({'port': port})
        finally:
            queued.close()
            sock.close()

        self.assertIsNone(resp.cameras)
        self.assertEqual('timeout connecting to rtsp netcam', resp.error)

    @tornado.testing.gen_test
    async def test_test_rtsp_url_401_without_auth_scheme(self):
        resp = await self.check(
            b'RTSP/1.0 401 Unauthorized\r\nCSeq: 1\r\n\r\n', username='u'
        )
        self.assertIsNone(resp.cameras)
        self.assertEqual('timeout waiting for rtsp netcam response', resp.error)


if __name__ == '__main__':
    tornado.testing.main()
