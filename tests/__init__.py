from unittest import mock

from tornado.web import Application
from tornado.testing import AsyncHTTPTestCase


__all__ = ('AsyncMock', 'WebTestCase')


class AsyncMock(mock.MagicMock):

    def __call__(self, *args, **kwargs):
        sup = super(AsyncMock, self)

        async def coro():
            return sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


class WebTestCase(AsyncHTTPTestCase):

    handler = None

    def get_app(self):
        self.app = Application(self.get_handlers(), **self.get_app_kwargs())
        return self.app

    def get_handlers(self):
        return [('/', self.handler)]

    def get_app_kwargs(self):
        return {}
