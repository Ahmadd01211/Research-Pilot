import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
# Equalize the missing-user verification path without storing a usable account.
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def random_token() -> str:
    return secrets.token_urlsafe(32)


def verify_password(stored: str, candidate: str) -> bool:
    try:
        return password_hasher.verify(stored, candidate)
    except (VerificationError, InvalidHashError):
        return False
