import json
from unittest.mock import MagicMock

import tornado.testing

from motioneye.handlers.base import BaseHandler
from tests.test_handlers import HandlerTestCase


class BaseHandlerTest(HandlerTestCase):

    handler_cls = BaseHandler

    def test_get_argument(self):
        handler = self.get_handler(MagicMock(body='{"myarg":5}'))
        result = handler.get_argument('myarg')
        self.assertEqual(5, result)

    def test_get_argument_no_object_in_json(self):
        handler = self.get_handler(MagicMock(body='"{{{"'))
        with self.assertRaises(AttributeError):
            handler.get_argument('myarg')

    def test_get_argument_empty_json(self):
        handler = self.get_handler(MagicMock(body='""'))
        result = handler.get_argument('myarg')
        self.assertIsNone(result)

    def test_get_argument_invalid_json(self):
        handler = self.get_handler(MagicMock(body='{{{{'))
        with self.assertRaises(json.decoder.JSONDecodeError):
            handler.get_argument('myarg')

    def test_get_current_user(self):
        handler = self.get_handler(MagicMock(body='""'))
        result = handler.get_current_user()
        self.assertEqual('normal', result)


if __name__ == '__main__':
    tornado.testing.main()
