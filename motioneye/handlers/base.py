# Copyright (c) 2020 Vlsarro
# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import logging
from secrets import token_hex
from time import time

from tornado.web import HTTPError, RequestHandler

from motioneye import VERSION, config, template
from motioneye.utils.authstate import verify_hmac_signature

__all__ = ('BaseHandler', 'NotFoundHandler', 'ManifestHandler')

# Session expiry: 24 hours
_SESSION_EXPIRY_SECONDS: int = 86400

# In-memory session store for browser session authentication
# Format: session_id -> {'user': role, 'expires': timestamp}
_session_store: dict = {}


def create_session(user_type):
    """Create a secure session id with expiry."""
    session_id = token_hex(32)
    _session_store[session_id] = {
        'user': user_type,
        'expires': time() + _SESSION_EXPIRY_SECONDS,
    }
    return session_id


def validate_session(session_id):
    """Validate a session id and return associated user type."""
    entry = _session_store.get(session_id)
    if not entry:
        return None
    if time() > entry['expires']:
        del _session_store[session_id]
        return None
    return entry['user']


def invalidate_session(session_id):
    """Invalidate a specific session."""
    if session_id in _session_store:
        del _session_store[session_id]


def invalidate_user_sessions(user_type):
    """Invalidate all sessions for a user type."""
    to_delete = [sid for sid, v in _session_store.items() if v.get('user') == user_type]
    for sid in to_delete:
        del _session_store[sid]


class BaseHandler(RequestHandler):
    def get_all_arguments(self) -> dict:
        keys = list(self.request.arguments.keys())
        arguments = {key: self.get_argument(key) for key in keys}

        for key in self.request.files:
            files = self.request.files[key]
            if len(files) > 1:
                arguments[key] = files

            elif len(files) > 0:
                arguments[key] = files[0]

            else:
                continue

        # consider the json passed in body as well
        data = self.get_json()
        if data and isinstance(data, dict):
            arguments.update(data)

        return arguments

    def get_json(self):
        if not hasattr(self, '_json'):
            self._json = None
            if self.request.headers.get('Content-Type', '').startswith(
                'application/json'
            ):
                self._json = json.loads(self.request.body)

        return self._json

    def get_argument(self, name, default=None, strip=True):
        def_ = {}
        argument = RequestHandler.get_argument(self, name, default=def_)
        if argument is def_:
            # try to find it in json body
            data = self.get_json()
            if data:
                argument = data.get(name, def_)

            if argument is def_:
                argument = default

        return argument

    def finish(self, chunk=None):
        if not self._finished:
            return super().finish(chunk=chunk)
        else:
            logging.debug('Already finished')

    def render(self, template_name, content_type='text/html', **context):
        self.set_header('Content-Type', content_type)

        context.setdefault('version', VERSION)

        content = template.render(template_name, **context)
        self.finish(content)

    def finish_json(self, data=None):
        if data is None:
            data = {}
        self.set_header('Content-Type', 'application/json')
        return self.finish(json.dumps(data))

    def get_current_user(self):
        # Check for session-based authentication (via secure cookie)
        session_id = self.get_secure_cookie('user')
        if session_id:
            try:
                session_id = (
                    session_id.decode() if isinstance(session_id, bytes) else session_id
                )
            except Exception:
                session_id = None

            if session_id:
                session_user = validate_session(session_id)
                if session_user in ['admin', 'normal']:
                    return session_user

        # Check for HMAC-based authentication (for remote requests)
        hmac_signature = self.request.headers.get('X-HMAC-Signature')
        timestamp = self.request.headers.get('X-Timestamp')
        nonce = self.request.headers.get('X-Nonce')

        if hmac_signature and timestamp and nonce:
            try:
                timestamp_int = int(timestamp)
                # Check timestamp is within 10 minutes
                if abs(time() - timestamp_int) > 600:  # 10 minutes
                    return None

                main_config = config.get_main()
                client_secret = main_config.get('@client_secret')
                if not client_secret:
                    return None

                # Reconstruct the request for signature verification
                method = self.request.method
                uri = self.request.uri
                body = self.request.body if self.request.body else None

                if verify_hmac_signature(
                    client_secret, method, uri, timestamp, nonce, hmac_signature, body
                ):
                    # HMAC auth is stateless - return 'peer' user type with no session
                    return 'peer'

            except (ValueError, TypeError):
                return None

        return None

    def _handle_request_exception(self, exception):
        try:
            if isinstance(exception, HTTPError):
                logging.error(str(exception))
                self.set_status(exception.status_code)
                self.finish_json(
                    {
                        'error': exception.log_message
                        or getattr(exception, 'reason', None)
                        or str(exception)
                    }
                )

            else:
                logging.error(str(exception), exc_info=True)
                self.set_status(500)
                self.finish_json({'error': 'internal server error'})

        except RuntimeError:
            pass  # nevermind

    @staticmethod
    def peer_allowed():
        def decorator(func):
            func._peer_allowed = True
            return func

        return decorator

    @staticmethod
    def auth(admin=False, prompt=True):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                _admin = self.get_argument('_admin', None) == 'true'

                user = self.current_user

                if user == 'peer':
                    if not getattr(func, '_peer_allowed', False):
                        self.set_header('Content-Type', 'application/json')
                        self.set_status(403)
                        return self.finish_json({'error': 'unauthorized'})
                    return func(self, *args, **kwargs)

                if (user is None) or (user != 'admin' and (admin or _admin)):
                    self.set_header('Content-Type', 'application/json')
                    self.set_status(403)

                    return self.finish_json({'error': 'unauthorized', 'prompt': prompt})

                return func(self, *args, **kwargs)

            return wrapper

        return decorator

    def get(self, *args, **kwargs):
        raise HTTPError(400, 'method not allowed')

    def post(self, *args, **kwargs):
        raise HTTPError(400, 'method not allowed')

    def head(self, *args, **kwargs):
        self.finish()


class NotFoundHandler(BaseHandler):
    def get(self, *args, **kwargs):
        raise HTTPError(404, 'not found')

    post = head = get


class ManifestHandler(BaseHandler):
    def get(self):
        self.set_header('Content-Type', 'application/manifest+json')
        self.set_header('Cache-Control', 'max-age=2592000')  # 30 days
        self.render('manifest.json')
