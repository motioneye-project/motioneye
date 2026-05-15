import hmac
from dataclasses import dataclass
from hashlib import sha256
from secrets import token_hex
from time import time

# Replay cache: stores (nonce, timestamp) pairs to prevent replay attacks
# Format: nonce -> timestamp
_replay_cache = {}
_replay_cache_max_age = 3600  # 1 hour


def _cleanup_replay_cache():
    """Remove old entries from replay cache."""
    current_time = time()
    expired = [
        nonce
        for nonce, ts in _replay_cache.items()
        if current_time - ts > _replay_cache_max_age
    ]
    for nonce in expired:
        del _replay_cache[nonce]


def add_to_replay_cache(nonce):
    """Add a nonce to the replay cache."""
    _cleanup_replay_cache()
    _replay_cache[nonce] = time()


def check_replay_cache(nonce):
    """Check if nonce has been seen before. Returns True if it's a replay."""
    _cleanup_replay_cache()
    return nonce in _replay_cache


def generate_nonce():
    """Generate a random nonce for request authentication."""
    return token_hex(16)


@dataclass
class UserHashState:
    hash_type: str
    needs_migration: bool


@dataclass
class PasswordHashState:
    admin: UserHashState
    normal: UserHashState


_password_hash_state = None


def set_password_hash_state(state):
    global _password_hash_state
    _password_hash_state = state


def get_password_hash_state():
    return _password_hash_state


def looks_like_argon2_hash(value):
    return isinstance(value, str) and value.startswith('$argon2')


def looks_like_normal_plaintext(value):
    return (
        isinstance(value, str)
        and value
        and not looks_like_argon2_hash(value)
        and not looks_like_legacy_sha1_hash(value)
    )


def looks_like_legacy_sha1_hash(value):
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(c in '0123456789abcdefABCDEF' for c in value)
    )


def detect_hash_type(value):
    if not value or not isinstance(value, str):
        return 'missing'

    if looks_like_argon2_hash(value):
        return 'argon2'

    if looks_like_normal_plaintext(value):
        return 'legacy'

    if looks_like_legacy_sha1_hash(value):
        return 'legacy'

    return 'invalid'


def build_password_hash_state(main_config):
    admin_type = detect_hash_type(main_config.get('@admin_password'))
    normal_type = detect_hash_type(main_config.get('@normal_password'))

    return PasswordHashState(
        admin=UserHashState(
            hash_type=admin_type,
            needs_migration=(admin_type in ('legacy')),
        ),
        normal=UserHashState(
            hash_type=normal_type,
            needs_migration=(normal_type in ('legacy')),
        ),
    )


def validate_password_hash_state(state):
    bad_states = {'invalid'}

    if state.admin.hash_type in bad_states or state.normal.hash_type in bad_states:
        raise RuntimeError(
            'password configuration is incomplete or invalid; '
            'run "sudo appname_init" to set or repair passwords'
        )


def mark_user_migrated(username):
    state = get_password_hash_state()
    if username == 'admin':
        state.admin.hash_type = 'argon2'
        state.admin.needs_migration = False
    elif username == 'normal':
        state.normal.hash_type = 'argon2'
        state.normal.needs_migration = False
    else:
        raise ValueError('unknown user: %s' % username)


def generate_hmac_signature(secret, method, path, timestamp, nonce, body=None):
    """Generate HMAC signature for request authentication."""
    message = f"{method}{path}{timestamp}{nonce}"
    if body:
        message += body.decode('utf-8') if isinstance(body, bytes) else str(body)

    return hmac.new(secret.encode('utf-8'), message.encode('utf-8'), sha256).hexdigest()


def verify_hmac_signature(secret, method, path, timestamp, nonce, signature, body=None):
    """Verify HMAC signature for request authentication."""
    # Check for replay
    if check_replay_cache(nonce):
        return False

    expected_signature = generate_hmac_signature(
        secret, method, path, timestamp, nonce, body
    )
    if not hmac.compare_digest(expected_signature, signature):
        return False

    # Add to replay cache after successful verification
    add_to_replay_cache(nonce)
    return True
