import json

import tornado.testing

from motioneye.handlers.login import LoginHandler
from tests.test_handlers import HandlerTestCase


class LoginHandlerTest(HandlerTestCase):
    handler_cls = LoginHandler

    def test_get_login_no_params(self):
        response = self.fetch('/login')
        self.assertEqual(200, response.code)
        self.assertEqual({}, json.loads(response.body))

    def test_get_login_success(self):
        url = '/login/?_=1587216975186&_username=admin&_login=true&_signature=f430e0da555b7714792e9cf9553c22536d00cfc0'
        response = self.fetch(url)
        self.assertEqual(200, response.code)
        self.assertEqual({}, json.loads(response.body))

    def test_get_login_fail(self):
        response = self.fetch('/login?_admin=true')
        self.assertEqual(403, response.code)
        self.assertEqual('application/json', response.headers.get('Content-Type'))
        self.assertEqual(
            {'error': 'unauthorized', 'prompt': True}, json.loads(response.body)
        )

    def test_post(self):
        response = self.fetch('/login', method='POST', body='')
        self.assertEqual(0, len(response.body))
        self.assertEqual('text/html', response.headers.get('Content-Type'))


if __name__ == '__main__':
    tornado.testing.main()
