from __future__ import annotations

from tornado.web import HTTPError

from motioneye import apikeys
from motioneye.handlers.base import BaseHandler

__all__ = ('ApiKeyHandler',)


class ApiKeyHandler(BaseHandler):
    """Lists, adds and removes API keys.

    Only the admin, signed in through the web UI, manages keys. A request made
    with a key is refused here even when that key has the admin role, so a
    leaked key cannot mint new ones and removing it is the end of it.
    """

    def check_session(self) -> None:
        if self.api_key_used:
            raise HTTPError(403, 'API keys cannot be managed with an API key')

    @BaseHandler.auth(admin=True)
    def get(self, op, key_id=None):
        self.check_session()

        if op != 'list':
            raise HTTPError(400, 'unknown operation')

        self.finish_json({'keys': apikeys.list_keys()})

    @BaseHandler.auth(admin=True)
    def post(self, op, key_id=None):
        self.check_session()

        if op == 'add':
            try:
                key, token = apikeys.add(
                    self.get_argument('name'), self.get_argument('role')
                )

            except apikeys.ApiKeyError as e:
                raise HTTPError(400, str(e)) from e

            self.finish_json({'key': key, 'token': token})

        elif op == 'rem':
            if not apikeys.remove(key_id):
                raise HTTPError(404, 'no such API key')

            self.finish_json()

        else:
            raise HTTPError(400, 'unknown operation')
