import tornado.testing

from motioneye.utils.rtmp import test_rtmp_url


class UtilsRtmpTest(tornado.testing.AsyncTestCase):
    def test_test_rtmp_url(self):
        result = test_rtmp_url({})
        self.assertEqual([{'id': 'tcp', 'name': 'RTMP/TCP Camera'}], result.cameras)
        self.assertIsNone(result.error)


if __name__ == '__main__':
    tornado.testing.main()
