from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import DUMMY_HASH, hash_token, password_hasher, random_token, verify_password
from app.modules.identity.models import User, UserSession
from app.modules.identity.schemas import LoginInput, RegisterInput

RATE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


def limit(redis: Redis, settings: Settings, action: str, subject: str, maximum: int) -> None:
    key = f"{settings.rate_namespace}:{action}:{hash_token(subject)}"
    count = redis.eval(RATE_SCRIPT, 1, key, "900")
    if int(count) > maximum:  # type: ignore[arg-type]
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": "900"})


def register(db: Session, data: RegisterInput) -> User:
    now = datetime.now(UTC)
    user = User(email=str(data.email).casefold(), display_name=data.display_name,
                password_hash=password_hasher.hash(data.password.get_secret_value()),
                created_at=now, updated_at=now)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to register with these details") from None
    return user


def login(db: Session, data: LoginInput, settings: Settings, existing: str | None) -> tuple[User, str, str]:
    user = db.scalar(select(User).where(User.email == str(data.email).casefold()))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, data.password.get_secret_value())
    if user is None or not valid:
        raise HTTPException(401, "Email or password is incorrect")
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(data.password.get_secret_value())
    now = datetime.now(UTC)
    if existing:
        previous = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(existing)))
        if previous:
            previous.revoked_at = now
    raw, csrf = random_token(), random_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_token(raw), csrf_hash=hash_token(csrf),
                       created_at=now, last_seen_at=now,
                       expires_at=now + timedelta(hours=settings.session_hours)))
    db.commit()
    return user, raw, csrf
