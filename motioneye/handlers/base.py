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

import hashlib
import json
import logging

from tornado.web import HTTPError, RequestHandler

from motioneye import config, prefs, settings, template, utils

__all__ = ('BaseHandler', 'NotFoundHandler', 'ManifestHandler')


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
            import motioneye

            self.set_header('Server', f'motionEye/{motioneye.VERSION}')

            return super().finish(chunk=chunk)
        else:
            logging.debug('Already finished')

    def render(self, template_name, content_type='text/html', **context):
        import motioneye

        self.set_header('Content-Type', content_type)

        context.setdefault('version', motioneye.VERSION)

        content = template.render(template_name, **context)
        self.finish(content)

    def finish_json(self, data=None):
        if data is None:
            data = {}
        self.set_header('Content-Type', 'application/json')
        return self.finish(json.dumps(data))

    def get_current_user(self):
        main_config = config.get_main()

        username = self.get_argument('_username', None)
        signature = self.get_argument('_signature', None)
        login = self.get_argument('_login', None) == 'true'

        admin_username = main_config.get('@admin_username')
        normal_username = main_config.get('@normal_username')

        admin_password = main_config.get('@admin_password')
        normal_password = main_config.get('@normal_password')

        admin_hash = hashlib.sha1(
            main_config['@admin_password'].encode('utf-8')
        ).hexdigest()
        normal_hash = hashlib.sha1(
            main_config['@normal_password'].encode('utf-8')
        ).hexdigest()

        if settings.HTTP_BASIC_AUTH and 'Authorization' in self.request.headers:
            up = utils.parse_basic_header(self.request.headers['Authorization'])
            if up:
                if up['username'] == admin_username and admin_password in (
                    up['password'],
                    hashlib.sha1(up['password'].encode('utf-8')).hexdigest(),
                ):
                    return 'admin'

                if up['username'] == normal_username and normal_password in (
                    up['password'],
                    hashlib.sha1(up['password'].encode('utf-8')).hexdigest(),
                ):
                    return 'normal'

        if username == admin_username and (
            signature
            == utils.compute_signature(
                self.request.method, self.request.uri, self.request.body, admin_password
            )
            or signature
            == utils.compute_signature(
                self.request.method, self.request.uri, self.request.body, admin_hash
            )
        ):
            return 'admin'

        # no authentication required for normal user
        if not username and not normal_password:
            return 'normal'

        if username == normal_username and (
            signature
            == utils.compute_signature(
                self.request.method,
                self.request.uri,
                self.request.body,
                normal_password,
            )
            or signature
            == utils.compute_signature(
                self.request.method, self.request.uri, self.request.body, normal_hash
            )
        ):
            return 'normal'

        if username and username != '_' and login:
            logging.error(f'authentication failed for user {username}')

        return None

    def get_pref(self, key):
        return prefs.get(self.current_user or 'anonymous', key)

    def set_pref(self, key, value):
        return prefs.set(self.current_user or 'anonymous', key, value)

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
    def auth(admin=False, prompt=True):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                _admin = self.get_argument('_admin', None) == 'true'

                user = self.current_user
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
