import hmac
from dataclasses import dataclass
from hashlib import sha256
from secrets import token_hex
from time import time

# Replay cache: stores (nonce, timestamp) pairs to prevent replay attacks
# Format: nonce -> timestamp
_replay_cache: dict = {}
_replay_cache_max_age: int = 3600  # 1 hour


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


_password_hash_state: PasswordHashState | None = None


def set_password_hash_state(state: PasswordHashState) -> None:
    global _password_hash_state
    _password_hash_state = state


def get_password_hash_state() -> PasswordHashState:
    if _password_hash_state is None:
        raise RuntimeError('_password_hash_state has not been assigned yet')
    return _password_hash_state


def _build_user_hash_state(hash: str | None) -> UserHashState:
    hash_type: str = 'legacy'
    if not hash:
        hash_type = 'missing'

    elif hash.startswith('$argon2'):
        hash_type = 'argon2'

    return UserHashState(
        hash_type=hash_type,
        needs_migration=(hash_type == 'legacy'),
    )


def build_password_hash_state(main_config: dict) -> PasswordHashState:
    return PasswordHashState(
        admin=_build_user_hash_state(main_config.get("@admin_password")),
        normal=_build_user_hash_state(main_config.get("@normal_password")),
    )


def validate_password_hash_state(state: PasswordHashState) -> bool:
    if state.admin.hash_type == 'missing' or state.normal.hash_type == 'missing':
        return False

    return True


def mark_user_migrated(user_type: str) -> None:
    state: PasswordHashState = get_password_hash_state()
    if user_type == 'admin':
        state.admin.hash_type = 'argon2'
        state.admin.needs_migration = False
    elif user_type == 'normal':
        state.normal.hash_type = 'argon2'
        state.normal.needs_migration = False
    else:
        raise ValueError(f'unknown user type: {user_type}')


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
