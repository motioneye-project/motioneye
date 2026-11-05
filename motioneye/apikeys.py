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


class ApiKeyError(ValueError):
    pass


def _file_path() -> str:
    return os.path.join(settings.CONF_PATH, _FILE_NAME)


def _load() -> list[dict[str, Any]]:
    global _keys

    if _keys is not None:
        return _keys

    _keys = []
    file_path = _file_path()
    if not os.path.exists(file_path):
        return _keys

    try:
        with open(file_path) as f:
            data = json.load(f)

    except Exception as e:
        logging.error(f'could not read API keys from "{file_path}": {e}')
        return _keys

    if isinstance(data, list):
        _keys = [
            k
            for k in data
            if isinstance(k, dict) and k.get('role') in ROLES and k.get('hash')
        ]

    return _keys


def _save() -> None:
    file_path = _file_path()
    tmp_path = file_path + '.tmp'

    # created private from the start: the file holds no tokens, but its hashes
    # are still worth keeping from other local users
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(_load(), f, indent=4)

    os.replace(tmp_path, file_path)


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
    keys.append(key)
    _save()

    logging.info(f'added API key "{name}" ({key_id}) with the {role} role')

    return _public(key), token


def remove(key_id: str) -> bool:
    keys = _load()
    for i, key in enumerate(keys):
        if key['id'] == key_id:
            del keys[i]
            _save()
            logging.info(f'removed API key "{key["name"]}" ({key_id})')
            return True

    return False


def verify(token: str) -> str | None:
    """Return the role of the key with this token, or None."""

    if not token.startswith(TOKEN_PREFIX):
        return None

    token_hash = _hash(token)
    for key in _load():
        if compare_digest(token_hash, key['hash']):
            now = int(time())
            if not key['last_used'] or now - key['last_used'] >= _LAST_USED_RESOLUTION:
                key['last_used'] = now
                try:
                    _save()

                except Exception as e:
                    logging.error(f'could not record the use of an API key: {e}')

            return key['role']

    return None


def reset() -> None:
    """Forget the cached keys, so they are read from the file again."""

    global _keys
    _keys = None
