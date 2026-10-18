from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import (
    authenticated_session,
    csrf_guard,
    current_user,
    database,
    redis_for,
    settings_for,
)
from app.core.security import random_token
from app.modules.identity import service
from app.modules.identity.models import User, UserSession
from app.modules.identity.schemas import CsrfRead, LoginInput, ProfileInput, RegisterInput, UserRead

router = APIRouter(prefix="/api/v1", tags=["identity"])


def cookie(response: Response, name: str, value: str, settings: Settings) -> None:
    response.set_cookie(name, value, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", max_age=settings.session_hours * 3600, path="/")


@router.get("/auth/csrf", response_model=CsrfRead)
def csrf(request: Request, response: Response, settings: Settings = Depends(settings_for)) -> CsrfRead:
    token = request.cookies.get(settings.csrf_cookie) or random_token()
    cookie(response, settings.csrf_cookie, token, settings)
    return CsrfRead(csrf_token=token)


@router.post("/auth/register", response_model=UserRead, status_code=201, dependencies=[Depends(csrf_guard)])
def register(
    data: RegisterInput, request: Request, db: Session = Depends(database),
    redis: Redis = Depends(redis_for), settings: Settings = Depends(settings_for),
) -> User:
    service.limit(redis, settings, "register-ip", request.client.host if request.client else "unknown", 30)
    service.limit(redis, settings, "register-email", str(data.email).casefold(), 5)
    return service.register(db, data)


@router.post("/auth/login", response_model=UserRead, dependencies=[Depends(csrf_guard)])
def login(
    data: LoginInput, request: Request, response: Response, db: Session = Depends(database),
    redis: Redis = Depends(redis_for), settings: Settings = Depends(settings_for),
) -> User:
    service.limit(redis, settings, "login-ip", request.client.host if request.client else "unknown", 100)
    service.limit(redis, settings, "login-email", str(data.email).casefold(), 10)
    user, raw, csrf = service.login(db, data, settings, request.cookies.get(settings.session_cookie))
    cookie(response, settings.session_cookie, raw, settings)
    cookie(response, settings.csrf_cookie, csrf, settings)
    return user


@router.post("/auth/logout", status_code=204)
def logout(
    response: Response, session: UserSession = Depends(authenticated_session),
    db: Session = Depends(database), settings: Settings = Depends(settings_for),
) -> None:
    session.revoked_at = datetime.now(UTC)
    db.commit()
    for name in (settings.session_cookie, settings.csrf_cookie):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.patch("/me", response_model=UserRead)
def update_me(data: ProfileInput, user: User = Depends(current_user), db: Session = Depends(database)) -> User:
    user.display_name = data.display_name
    user.updated_at = datetime.now(UTC)
    db.commit()
    return user
