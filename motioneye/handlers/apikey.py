from __future__ import annotations

from tornado.web import HTTPError

from motioneye import apikeys
from motioneye.handlers.base import BaseHandler

__all__ = ('ApiKeyHandler',)


class ApiKeyHandler(BaseHandler):
    """Lists, adds and removes API keys.

    Only the admin, signed in through the web UI, manages keys: a request made
    with a key is refused here, so a leaked key cannot mint new ones. Failures
    are answered with an "error" field, which the web UI shows.
    """

    @BaseHandler.auth(admin=True, api_key=False)
    def get(self, op, key_id=None):
        if op != 'list':
            raise HTTPError(400, 'unknown operation')

        try:
            self.finish_json({'keys': apikeys.list_keys()})

        except apikeys.ApiKeyError as e:
            self.finish_json({'error': str(e)})

    @BaseHandler.auth(admin=True, api_key=False)
    def post(self, op, key_id=None):
        try:
            if op == 'add':
                key, token = apikeys.add(
                    self.get_argument('name'), self.get_argument('role')
                )
                self.finish_json({'key': key, 'token': token})

            elif op == 'rem':
                if apikeys.remove(key_id):
                    self.finish_json()

                else:
                    self.finish_json({'error': 'no such API key'})

            else:
                raise HTTPError(400, 'unknown operation')

        except apikeys.ApiKeyError as e:
            self.finish_json({'error': str(e)})
