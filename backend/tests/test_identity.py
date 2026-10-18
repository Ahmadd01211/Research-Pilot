from datetime import UTC, datetime, timedelta

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.security import hash_token
from app.infrastructure.database.base import Base
from app.modules.identity.models import User, UserSession
from tests.conftest import csrf, login, register


def test_complete_identity_lifecycle(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401
    register(client)
    login(client)
    raw = client.cookies["rp_session"]
    old_csrf = client.cookies["rp_csrf"]
    assert client.get("/api/v1/me").json()["display_name"] == "Researcher"
    result = client.patch("/api/v1/me", headers=csrf(client), json={"display_name": "Dr. Researcher"})
    assert result.status_code == 200
    assert client.get("/api/v1/me").json()["display_name"] == "Dr. Researcher"
    with client.app.state.session_factory() as db:  # type: ignore[union-attr]
        user = db.scalar(select(User))
        assert user and user.password_hash.startswith("$argon2id$")
        session = db.scalar(select(UserSession))
        assert session and session.token_hash == hash_token(raw) and session.token_hash != raw
    assert client.post("/api/v1/auth/logout", headers=csrf(client)).status_code == 204
    assert client.get("/api/v1/me").status_code == 401
    client.cookies.set("rp_session", raw, domain="testserver.local", path="/")
    client.cookies.set("rp_csrf", old_csrf, domain="testserver.local", path="/")
    assert client.get("/api/v1/me").status_code == 401


def test_csrf_origin_and_session_binding(client: TestClient) -> None:
    payload = {"email": "researcher@example.com", "display_name": "R", "password": "Synthetic-password-123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 403
    headers = csrf(client)
    assert client.post("/api/v1/auth/register", headers={**headers, "origin": "https://evil.example"}, json=payload).status_code == 403
    register(client)
    login(client)
    assert client.patch("/api/v1/me", json={"display_name": "Attack"}).status_code == 403
    client.cookies.set("rp_csrf", "forged", domain="testserver.local", path="/")
    assert client.patch("/api/v1/me", headers={"origin": "http://localhost:3100", "x-csrf-token": "forged"}, json={"display_name": "Attack"}).status_code == 403


def test_validation_duplicate_and_credential_redaction(client: TestClient) -> None:
    result = client.post("/api/v1/auth/register", headers=csrf(client), json={"email": "bad", "display_name": " ", "password": "secret"})
    assert result.status_code == 422 and "secret" not in result.text
    assert result.headers["content-type"].startswith("application/problem+json")
    register(client)
    result = client.post("/api/v1/auth/register", headers=csrf(client), json={"email": "RESEARCHER@example.com", "display_name": "R", "password": "Synthetic-password-123"})
    assert result.status_code == 409
    for email in ("researcher@example.com", "missing@example.com"):
        result = client.post("/api/v1/auth/login", headers=csrf(client), json={"email": email, "password": "wrong"})
        assert result.status_code == 401 and result.json()["detail"] == "Email or password is incorrect"


def test_rate_limit(client: TestClient) -> None:
    for _ in range(10):
        assert client.post("/api/v1/auth/login", headers=csrf(client), json={"email": "missing@example.com", "password": "wrong"}).status_code == 401
    result = client.post("/api/v1/auth/login", headers=csrf(client), json={"email": "missing@example.com", "password": "wrong"})
    assert result.status_code == 429 and result.headers["retry-after"] == "900"


@pytest.mark.parametrize("field", ["expires_at", "last_seen_at"])
def test_session_expiration(client: TestClient, field: str) -> None:
    register(client)
    login(client)
    with client.app.state.session_factory() as db:  # type: ignore[union-attr]
        session = db.scalar(select(UserSession))
        assert session
        setattr(session, field, datetime.now(UTC) - timedelta(days=2))
        db.commit()
    assert client.get("/api/v1/me").status_code == 401


def test_session_rotation_and_profile_isolation(client: TestClient) -> None:
    register(client)
    login(client)
    old = client.cookies["rp_session"]
    login(client)
    fresh = client.cookies["rp_session"]
    assert old != fresh
    client.cookies.set("rp_session", old, domain="testserver.local", path="/")
    assert client.get("/api/v1/me").status_code == 401
    client.cookies.set("rp_session", fresh, domain="testserver.local", path="/")
    assert client.post("/api/v1/auth/logout", headers=csrf(client)).status_code == 204
    register(client, "other@example.com")
    login(client, "other@example.com")
    assert client.patch("/api/v1/me", headers=csrf(client), json={"display_name": "Other"}).status_code == 200
    assert client.patch("/api/v1/me", headers=csrf(client), json={"display_name": "Other", "id": "another-user"}).status_code == 422
    client.post("/api/v1/auth/logout", headers=csrf(client))
    login(client)
    assert client.get("/api/v1/me").json()["display_name"] == "Researcher"


def test_database_schema_readiness_and_cookie_flags(client: TestClient) -> None:
    assert client.get("/api/v1/health/ready").status_code == 200
    with client.app.state.engine.connect() as connection:  # type: ignore[union-attr]
        assert not compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert connection.scalar(text("SELECT extname FROM pg_extension WHERE extname='vector'")) == "vector"
    register(client)
    result = client.post("/api/v1/auth/login", headers=csrf(client), json={"email": "researcher@example.com", "password": "Synthetic-password-123"})
    for value in result.headers.get_list("set-cookie"):
        assert "HttpOnly" in value and "SameSite=lax" in value and "Path=/" in value
    with pytest.raises(ValueError):
        Settings(environment="production", cookie_secure=False)
