from unittest import mock

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

__all__ = ('AsyncMock', 'WebTestCase')


class AsyncMock(mock.MagicMock):
    def __call__(self, *args, **kwargs):
        sup = super()

        async def coro():
            return sup.__call__(*args, **kwargs)

        return coro()

    def __await__(self):
        return self().__await__()


class WebTestCase(AsyncHTTPTestCase):

    handler: type = None

    def get_app(self):
        self.app = Application(self.get_handlers(), **self.get_app_kwargs())
        return self.app

    def get_handlers(self):
        return [('/', self.handler)]

    def get_app_kwargs(self):
        return {}
