import logging
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from uuid import UUID

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import DUMMY_HASH, hash_token, password_hasher, random_token, verify_password
from app.infrastructure.mail import MailSender
from app.modules.identity.models import PasswordResetToken, User, UserSession
from app.modules.identity.schemas import (
    LoginInput,
    PasswordChangeInput,
    PasswordResetInput,
    RegisterInput,
)

logger = logging.getLogger("researchpilot")
INVALID_RESET = "This reset link is invalid or has expired. Request a new one."

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


def _revoke_sessions(db: Session, user_id: UUID, now: datetime, keep: UUID | None = None) -> None:
    query = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if keep is not None:
        query = query.where(UserSession.id != keep)
    db.execute(query.values(revoked_at=now))


def _consume_reset_tokens(db: Session, user_id: UUID, now: datetime) -> None:
    db.execute(update(PasswordResetToken).where(
        PasswordResetToken.user_id == user_id, PasswordResetToken.consumed_at.is_(None),
    ).values(consumed_at=now))


def change_password(db: Session, user: User, session: UserSession, data: PasswordChangeInput) -> None:
    current, new = data.current_password.get_secret_value(), data.new_password.get_secret_value()
    if not verify_password(user.password_hash, current):
        raise HTTPException(400, "Your current password is incorrect")
    if current == new:
        raise HTTPException(400, "Choose a new password that differs from your current one")
    now = datetime.now(UTC)
    user.password_hash = password_hasher.hash(new)
    user.updated_at = now
    # This device stays signed in; every other session must sign in again.
    _revoke_sessions(db, user.id, now, keep=session.id)
    _consume_reset_tokens(db, user.id, now)
    db.commit()


def request_password_reset(db: Session, email: str, settings: Settings) -> tuple[User, str] | None:
    user = db.scalar(select(User).where(User.email == email.casefold()))
    if user is None:
        return None
    now = datetime.now(UTC)
    _consume_reset_tokens(db, user.id, now)  # only the newest link works
    raw = random_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw), created_at=now,
                              expires_at=now + timedelta(minutes=settings.password_reset_minutes)))
    db.commit()
    return user, raw


def send_reset_email(mail: MailSender, settings: Settings, user: User, raw: str) -> None:
    # The token travels in the URL fragment, which browsers never send to servers or in Referer.
    message = EmailMessage()
    message["To"] = user.email
    message["Subject"] = "Reset your ResearchPilot password"
    message.set_content(
        f"Hello {user.display_name},\n\n"
        "Someone asked to reset the password for your ResearchPilot account. "
        f"Open this link within {settings.password_reset_minutes} minutes to choose a new password:\n\n"
        f"{settings.public_origin}/reset-password#token={raw}\n\n"
        "The link works once. If you did not ask for this, ignore this email; your password will not change.\n"
    )
    try:
        mail.send(message)
    except Exception as error:  # noqa: BLE001 - runs after the response; log without token or address
        logger.warning("password_reset_email_failed category=%s", type(error).__name__)


def reset_password(db: Session, data: PasswordResetInput) -> None:
    now = datetime.now(UTC)
    # A conditional UPDATE makes the token single-use even under concurrent submissions.
    user_id = db.scalar(update(PasswordResetToken).where(
        PasswordResetToken.token_hash == hash_token(data.token.get_secret_value()),
        PasswordResetToken.consumed_at.is_(None), PasswordResetToken.expires_at > now,
    ).values(consumed_at=now).returning(PasswordResetToken.user_id))
    user = db.get(User, user_id, with_for_update=True) if user_id else None
    if user is None:
        db.rollback()
        raise HTTPException(400, INVALID_RESET)
    user.password_hash = password_hasher.hash(data.new_password.get_secret_value())
    user.updated_at = now
    _revoke_sessions(db, user.id, now)
    _consume_reset_tokens(db, user.id, now)
    db.commit()
