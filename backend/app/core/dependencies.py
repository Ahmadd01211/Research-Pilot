import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_token
from app.modules.identity.models import User, UserSession


def settings_for(request: Request) -> Settings:
    value: Settings = request.app.state.settings
    return value


def database(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as db:
        yield db


def redis_for(request: Request) -> Redis:
    value: Redis = request.app.state.redis
    return value


def csrf_guard(request: Request, settings: Settings = Depends(settings_for)) -> None:
    if request.headers.get("origin") != settings.public_origin:
        raise HTTPException(403, "Request origin is not allowed")
    cookie = request.cookies.get(settings.csrf_cookie, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(403, "CSRF verification failed")


def authenticated_session(
    request: Request, db: Session = Depends(database), settings: Settings = Depends(settings_for),
) -> UserSession:
    raw = request.cookies.get(settings.session_cookie, "")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw))) if raw else None
    now = datetime.now(UTC)
    if session is None or session.revoked_at is not None or session.expires_at <= now or (
        session.last_seen_at + timedelta(minutes=settings.session_idle_minutes) <= now
    ):
        raise HTTPException(401, "Please sign in to continue")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_guard(request, settings)
        if not secrets.compare_digest(session.csrf_hash, hash_token(request.headers.get("x-csrf-token", ""))):
            raise HTTPException(403, "CSRF verification failed")
    session.last_seen_at = now
    db.commit()
    return session


def current_user(
    session: UserSession = Depends(authenticated_session), db: Session = Depends(database),
) -> User:
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Please sign in to continue")
    return user
