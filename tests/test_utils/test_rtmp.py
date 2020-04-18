import tornado.testing

from motioneye.utils.rtmp import test_rtmp_url


class UtilsRtmpTest(tornado.testing.AsyncTestCase):

    def test_test_rtmp_url(self):

        def mock_on_response(cameras=None, error=None) -> None:
            self.assertEqual([{'id': 'tcp', 'name': 'RTMP/TCP Camera'}], cameras)
            self.assertIsNone(error)

        result = test_rtmp_url({}, mock_on_response)
        self.assertIsNone(result)


if __name__ == '__main__':
    tornado.testing.main()
