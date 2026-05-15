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

import logging
from hashlib import sha1
from secrets import compare_digest

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from motioneye import config
from motioneye.handlers.base import BaseHandler, create_session
from motioneye.utils.authstate import (
    build_password_hash_state,
    mark_user_migrated,
    set_password_hash_state,
)

__all__ = ('LoginHandler',)

ph = PasswordHasher()


def verify_argon2_password(stored_hash, plaintext_password):
    try:
        return ph.verify(stored_hash, plaintext_password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def verify_legacy_sha1_password(stored_hash, plaintext_password):
    candidate = sha1(plaintext_password.encode()).hexdigest()
    return compare_digest(candidate, stored_hash)


def should_use_secure_cookie(handler):
    proto = handler.request.headers.get("X-Forwarded-Proto")
    if proto:
        return proto.lower() == "https"
    return handler.request.protocol == "https"


class LoginHandler(BaseHandler):
    @BaseHandler.auth()
    def get(self):
        user = self.current_user
        if user:
            main_config = config.get_main()
            username = (
                main_config.get('@admin_username')
                if user == 'admin'
                else main_config.get('@normal_username')
            )
            self.finish_json({'user': user, 'username': username or user})
        else:
            self.set_status(401)
            self.finish_json({'error': 'not authenticated'})

    def post(self):
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)

        body = self.get_json() or {}
        if not username:
            username = body.get('username')
        if not password:
            password = body.get('password')

        main_config = config.get_main()

        # Always rebuild from current config so hash state is not stale
        hash_state = build_password_hash_state(main_config)
        set_password_hash_state(hash_state)

        admin_username = main_config.get('@admin_username')
        normal_username = main_config.get('@normal_username')
        admin_password = main_config.get('@admin_password')
        normal_password = main_config.get('@normal_password')

        if not username:
            self.set_status(400)
            return self.finish_json({'error': 'username is required'})

        if username == admin_username and admin_password and not password:
            self.set_status(400)
            return self.finish_json({'error': 'invalid credentials'})
        else:
            pass

        user_type = None
        stored_hash = None
        user_state = None

        if username == admin_username:
            user_type = 'admin'
            stored_hash = admin_password
            user_state = hash_state.admin

        elif username == normal_username:
            user_type = 'normal'
            stored_hash = normal_password
            user_state = hash_state.normal
        else:
            self.set_status(401)
            return self.finish_json({'error': 'invalid credentials'})

        if stored_hash is None:
            self.set_status(401)
            return self.finish_json({'error': 'invalid credentials'})

        try:
            if user_state.hash_type == 'argon2':
                if not verify_argon2_password(stored_hash, password):
                    self.set_status(401)
                    return self.finish_json({'error': 'invalid credentials'})

            elif user_state.hash_type == 'legacy':
                if (
                    user_type == 'admin'
                    and admin_password
                    and not verify_legacy_sha1_password(stored_hash, password)
                ):
                    self.set_status(401)
                    return self.finish_json({'error': 'invalid credentials'})
                elif user_type == 'normal':
                    if password != stored_hash:
                        self.set_status(401)
                        return self.finish_json({'error': 'invalid credentials'})
                if user_type == 'admin':
                    config.set_admin_password(password)
                else:
                    config.set_normal_password(password)

                mark_user_migrated(user_type)

            elif user_state.hash_type == 'missing':
                if password not in (None, ''):
                    self.set_status(401)
                    return self.finish_json({'error': 'invalid credentials'})
            else:
                self.set_status(401)
                return self.finish_json({'error': 'invalid credentials'})

        except Exception as e:
            logging.error(f'{user_type} authentication error: {e}')
            self.set_status(401)
            return self.finish_json({'error': 'invalid credentials'})

        session_id = create_session(user_type)
        self.set_secure_cookie(
            "user",
            session_id,
            expires_days=1,
            httponly=True,
            secure=should_use_secure_cookie(self),
            samesite="Strict",
        )

        response = {'user': user_type}

        if user_state.hash_type == 'missing':
            response['force_password_change'] = True

        self.finish_json(response)
