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

from __future__ import annotations

import logging
from hashlib import sha1
from ipaddress import IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network
from math import ceil
from secrets import compare_digest
from time import monotonic
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from tornado.httputil import HTTPServerRequest

from motioneye import config
from motioneye.handlers.base import BaseHandler, create_session, session_expiry_seconds
from motioneye.settings import TRUSTED_PROXIES
from motioneye.utils.authstate import (
    PasswordHashState,
    build_password_hash_state,
    mark_user_migrated,
    set_password_hash_state,
)

__all__ = ('LoginHandler',)

ph = PasswordHasher()

_FREE_ATTEMPTS = 5
_FIRST_DELAY_SECONDS = 5
_MAX_DELAY_SECONDS = 900
_FORGET_AFTER_SECONDS = 3600
_MAX_ENTRIES = 1000


def parse_trusted_proxies(value: str) -> tuple[IPv4Network | IPv6Network, ...]:
    try:
        return tuple(
            ip_network(proxy) for proxy in map(str.strip, value.split(',')) if proxy
        )
    except ValueError as e:
        logging.warning(f'ignoring invalid trusted_proxies: {e}')
        return ()


_TRUSTED_PROXIES = parse_trusted_proxies(TRUSTED_PROXIES)

# Client IP or IPv6 /64 -> (last failure time, failure count), oldest first.
_failed_logins: dict[str | None, tuple[float, int]] = {}


def get_login_address(request: HTTPServerRequest) -> str | None:
    address: str | None = request.remote_ip
    if not address or not _TRUSTED_PROXIES:
        return address

    forwarded_for = request.headers.get('X-Forwarded-For')
    if not forwarded_for:
        return address

    try:
        # Check the TCP peer before trusting any forwarded addresses.
        for index, candidate in enumerate(
            [address] + list(reversed(forwarded_for.split(',')))
        ):
            ip = ip_address(candidate.strip())
            ipv4 = ip.ipv4_mapped if isinstance(ip, IPv6Address) else None
            if not any(
                ip in proxy or (ipv4 is not None and ipv4 in proxy)
                for proxy in _TRUSTED_PROXIES
            ):
                return candidate.strip() if index else address
    except ValueError as e:
        logging.warning(f'ignoring X-Forwarded-For, using {address} as client: {e}')

    return address


# Normalize IPv4-mapped addresses and group other IPv6 addresses by /64.
def normalize_address(address: str | None) -> str | None:
    if not address:
        return address

    try:
        ip = ip_address(address)
        if isinstance(ip, IPv6Address):
            if ip.ipv4_mapped:
                return str(ip.ipv4_mapped)

            return str(ip_network((ip, 64), strict=False))
    except ValueError:
        pass

    return address


def entry_wait(entry: tuple[float, int], now: float) -> int:
    last, failures = entry
    if failures < _FREE_ATTEMPTS:
        return 0

    delay: int = min(
        _FIRST_DELAY_SECONDS * 2 ** (failures - _FREE_ATTEMPTS), _MAX_DELAY_SECONDS
    )
    return max(0, ceil(last + delay - now))


def forget_old_failures(now: float) -> None:
    while _failed_logins:
        oldest = next(iter(_failed_logins))
        if now - _failed_logins[oldest][0] <= _FORGET_AFTER_SECONDS:
            break

        del _failed_logins[oldest]


def record_failed_login(client: str | None) -> None:
    now = monotonic()
    failures = _failed_logins.pop(client, (now, 0))[1] + 1
    if len(_failed_logins) >= _MAX_ENTRIES:
        logging.warning(
            f'more than {_MAX_ENTRIES} clients with failed logins, dropping one'
        )
        # Drop the oldest entry that is not blocked, or the oldest if all are.
        victim = next(
            (k for k, e in _failed_logins.items() if not entry_wait(e, now)),
            next(iter(_failed_logins)),
        )
        del _failed_logins[victim]

    _failed_logins[client] = (now, failures)


def verify_argon2_password(stored_hash, plaintext_password):
    try:
        return ph.verify(stored_hash, plaintext_password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def verify_legacy_sha1_password(stored_hash, plaintext_password):
    candidate = sha1(plaintext_password.encode()).hexdigest()  # nosec: B324
    return compare_digest(candidate, stored_hash)


def should_use_secure_cookie(handler):
    proto = handler.request.headers.get("X-Forwarded-Proto")
    if proto:
        return proto.lower() == "https"
    return handler.request.protocol == "https"


class LoginHandler(BaseHandler):
    login_key: str | None = None

    @BaseHandler.auth()
    def get(self) -> None:
        user = self.current_user
        if user:
            main_config: dict = config.get_main()
            username = (
                main_config.get('@admin_username')
                if user == 'admin'
                else main_config.get('@normal_username')
            )
            self.finish_json({'user': user, 'username': username or user})
        else:
            self.set_status(401)
            self.finish_json({'error': 'not authenticated'})

    def on_finish(self) -> None:
        if self.request.method == 'POST' and self.get_status() == 401:
            record_failed_login(self.login_key)

    def post(self) -> None:
        now = monotonic()
        forget_old_failures(now)
        self.login_key = normalize_address(get_login_address(self.request))
        entry = _failed_logins.get(self.login_key)
        wait = entry_wait(entry, now) if entry else 0
        if wait:
            self.set_header('Retry-After', str(wait))
            self.set_status(429)
            return self.finish_json(
                {'error': 'too many failed login attempts', 'retry_after': wait}
            )

        body = self.get_json() or {}
        username: str = self.get_argument('username', body.get('username') or '')
        password: str = self.get_argument('password', body.get('password') or '')

        if username == '':
            self.set_status(400)
            return self.finish_json({'error': 'username is required'})

        main_config: dict = config.get_main()

        # Always rebuild from current config so hash state is not stale
        hash_state: PasswordHashState = build_password_hash_state(main_config)
        set_password_hash_state(hash_state)

        user_type: str
        stored_hash: str
        hash_type: str

        if username == main_config.get('@admin_username'):
            user_type = 'admin'
            stored_hash = main_config.get('@admin_password') or ''
            hash_type = hash_state.admin.hash_type

        elif username == main_config.get('@normal_username'):
            user_type = 'normal'
            stored_hash = main_config.get('@normal_password') or ''
            hash_type = hash_state.normal.hash_type

        else:
            self.set_status(401)
            return self.finish_json({'error': 'invalid credentials'})

        try:
            if hash_type == 'argon2':
                if not verify_argon2_password(stored_hash, password):
                    self.set_status(401)
                    return self.finish_json({'error': 'invalid credentials'})

            elif hash_type == 'legacy':
                if password != stored_hash and not verify_legacy_sha1_password(
                    stored_hash, password
                ):
                    self.set_status(401)
                    return self.finish_json({'error': 'invalid credentials'})

                if user_type == 'admin':
                    config.set_admin_password(password)
                else:
                    config.set_normal_password(password)

                mark_user_migrated(user_type)

            elif hash_type == 'missing':
                if password != '':  # nosec: B105
                    self.set_status(401)
                    return self.finish_json({'error': 'invalid credentials'})

            else:
                self.set_status(401)
                return self.finish_json({'error': 'invalid credentials'})

        except Exception as e:
            logging.error(f'{user_type} authentication error: {e}')
            self.set_status(401)
            return self.finish_json({'error': 'invalid credentials'})

        # Only an admin login clears the counter, so a normal user cannot reset admin guesses.
        if user_type == 'admin':
            _failed_logins.pop(self.login_key, None)

        session_id = create_session(user_type)
        self.set_signed_cookie(
            'user',
            session_id,
            expires_days=session_expiry_seconds(user_type) / 86400,
            httponly=True,
            secure=should_use_secure_cookie(self),
            samesite='Strict',
        )

        response: dict[str, Any] = {'user': user_type}

        if hash_type == 'missing':
            response['force_password_change'] = True

        self.finish_json(response)

        return None
