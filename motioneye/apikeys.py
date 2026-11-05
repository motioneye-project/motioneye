"""API keys, for scripts and integrations that cannot keep a login session.

A key is shown once, when it is created, and only its SHA-256 hash is kept, in
its own file next to the camera configs. Each key carries the role of one of
the two motionEye users, admin or normal, and is accepted wherever a session of
that user would be.
"""

from __future__ import annotations

import json
import logging
import os
from hashlib import sha256
from secrets import compare_digest, token_hex, token_urlsafe
from time import time
from typing import Any

from motioneye import settings

__all__ = (
    'ROLES',
    'TOKEN_PREFIX',
    'ApiKeyError',
    'add',
    'list_keys',
    'remove',
    'verify',
)

ROLES = ('admin', 'normal')
TOKEN_PREFIX = 'meye_'

_FILE_NAME = 'api_keys.json'
_MAX_KEYS = 100
_MAX_NAME_LENGTH = 64
# last use is recorded to the hour, so a camera polled every second does not
# rewrite the file every second
_LAST_USED_RESOLUTION = 3600

_keys: list[dict[str, Any]] | None = None
# why the file could not be read, logged once while it stays that way
_load_error: str | None = None


class ApiKeyError(ValueError):
    pass


def _file_path() -> str:
    return os.path.join(settings.CONF_PATH, _FILE_NAME)


def _load() -> list[dict[str, Any]]:
    """Return the keys, read from the file the first time.

    Raises ApiKeyError while the file exists but cannot be read, so that it is
    never overwritten with what little could be read; no key is accepted then.
    Each call tries again, so fixing or removing the file needs no restart.
    """

    global _keys, _load_error

    if _keys is not None:
        return _keys

    file_path = _file_path()
    if not os.path.exists(file_path):
        _keys = []
        return _keys

    try:
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise TypeError('expected a list of keys')

    except Exception as e:
        error = f'could not read API keys from "{file_path}": {e}'
        if error != _load_error:
            logging.error(error)
            _load_error = error

        raise ApiKeyError(
            f'the API keys file "{file_path}" cannot be read; fix or remove it'
        ) from e

    _keys = [
        k
        for k in data
        if isinstance(k, dict)
        and isinstance(k.get('id'), str)
        and k.get('role') in ROLES
        and k.get('hash')
    ]
    _load_error = None

    return _keys


def _save(keys: list[dict[str, Any]]) -> None:
    """Write the keys to the file, replacing it only once they are all written."""

    file_path = _file_path()
    tmp_path = file_path + '.tmp'

    try:
        # created private from the start: the file holds no tokens, but its
        # hashes are still worth keeping from other local users
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(keys, f, indent=4)

        os.replace(tmp_path, file_path)

    except OSError as e:
        logging.error(f'could not save API keys to "{file_path}": {e}')
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        raise ApiKeyError('the API keys could not be saved') from e


def _hash(token: str) -> str:
    return sha256(token.encode('utf-8')).hexdigest()


def _public(key: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in key.items() if k != 'hash'}


def list_keys() -> list[dict[str, Any]]:
    return [_public(k) for k in _load()]


def add(name: Any, role: Any) -> tuple[dict[str, Any], str]:
    """Create a key and return its record and the token, which is not kept."""

    if not isinstance(name, str) or not name.strip():
        raise ApiKeyError('a name is required')

    name = name.strip()
    if len(name) > _MAX_NAME_LENGTH:
        raise ApiKeyError(f'the name is longer than {_MAX_NAME_LENGTH} characters')

    if role not in ROLES:
        raise ApiKeyError(f'the role must be one of: {", ".join(ROLES)}')

    keys = _load()
    if len(keys) >= _MAX_KEYS:
        raise ApiKeyError(f'there are already {_MAX_KEYS} API keys')

    token = TOKEN_PREFIX + token_urlsafe(32)
    key_ids = {k['id'] for k in keys}
    key_id = token_hex(4)
    while key_id in key_ids:
        key_id = token_hex(4)

    key = {
        'id': key_id,
        'name': name,
        'role': role,
        'hint': token[-4:],
        'created': int(time()),
        'last_used': None,
        'hash': _hash(token),
    }
    # the list in use changes only once the file has it, so a failed save
    # leaves no key that nobody holds the token of
    keys = [*keys, key]
    _save(keys)
    _set_keys(keys)

    logging.info(f'added API key "{name}" ({key_id}) with the {role} role')

    return _public(key), token


def remove(key_id: str) -> bool:
    keys = _load()
    removed = [k for k in keys if k['id'] == key_id]
    if not removed:
        return False

    # as in add(): a key that could not be removed from the file stays listed,
    # rather than coming back after a restart
    keys = [k for k in keys if k['id'] != key_id]
    _save(keys)
    _set_keys(keys)

    logging.info(f'removed API key "{removed[0]["name"]}" ({key_id})')

    return True


def verify(token: str) -> str | None:
    """Return the role of the key with this token, or None."""

    if not token.startswith(TOKEN_PREFIX):
        return None

    try:
        keys = _load()

    except ApiKeyError:
        return None

    token_hash = _hash(token)
    for key in keys:
        if compare_digest(token_hash, key['hash']):
            now = int(time())
            if not key['last_used'] or now - key['last_used'] >= _LAST_USED_RESOLUTION:
                key['last_used'] = now
                try:
                    _save(keys)

                except ApiKeyError:
                    pass  # only the time of last use is lost, and save logged why

            return key['role']

    return None


def _set_keys(keys: list[dict[str, Any]]) -> None:
    global _keys
    _keys = keys


def reset() -> None:
    """Forget the cached keys, so they are read from the file again."""

    global _keys, _load_error
    _keys = None
    _load_error = None
