import unittest

from motioneye.utils.http import RtspUrl


class TestRTSP(unittest.TestCase):
    def test_url_construction(self):
        host = '102.170.91.135'
        scheme = 'rtsp'
        user = 'user1324'
        password = 'MyPassword1'
        test_data = {
            '_': '1589083749971',
            'scheme': scheme,
            'host': host,
            'port': '',
            'path': '/',
            'username': user,
            'password': password,
            'proto': 'netcam',
            '_username': 'admin',
            '_signature': 'e06ef15af4e73086df6bfa90da0312641a5a2b10',
        }
        url_obj = RtspUrl.from_dict(test_data)
        self.assertEqual(host, url_obj.host)
        self.assertEqual(scheme, url_obj.scheme)
        self.assertEqual(user, url_obj.username)
        self.assertEqual(password, url_obj.password)
        self.assertEqual('554', url_obj.port)


if __name__ == '__main__':
    unittest.main()
