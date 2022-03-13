from typing import Type, TypeVar
from unittest.mock import MagicMock

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, RequestHandler

from motioneye.server import make_app

__all__ = ('HandlerTestCase',)


T = TypeVar('T', bound=RequestHandler)


class HandlerTestCase(AsyncHTTPTestCase):

    handler_cls = NotImplemented  # type: Type[T]

    def get_app(self) -> Application:
        self.app = make_app()
        return self.app

    def get_handler(self, request: MagicMock = None) -> T:
        req = request or MagicMock()
        return self.handler_cls(self.app, req)
