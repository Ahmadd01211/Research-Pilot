import logging
import re
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.config import Settings
from app.core.security import hash_token
from app.modules.identity.models import PasswordResetToken
from tests.conftest import csrf, login, register

OLD = "Synthetic-password-123"
NEW = "Another-synthetic-456"


class Outbox:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


@pytest.fixture
def outbox(client: TestClient) -> Outbox:
    value = Outbox()
    client.app.state.mail = value  # type: ignore[attr-defined]
    return value


def sign_in(client: TestClient, password: str, email: str = "researcher@example.com") -> int:
    return client.post("/api/v1/auth/login", headers=csrf(client),
                       json={"email": email, "password": password}).status_code


def forgot(client: TestClient, email: str = "researcher@example.com") -> int:
    return client.post("/api/v1/auth/password/forgot", headers=csrf(client), json={"email": email}).status_code


def reset(client: TestClient, token: str, password: str = NEW) -> int:
    return client.post("/api/v1/auth/password/reset", headers=csrf(client),
                       json={"token": token, "new_password": password}).status_code


def token_from(message: EmailMessage) -> str:
    body = message.get_content()
    match = re.search(r"http://localhost:3100/reset-password#token=(\S+)", body)
    assert match, body
    return match.group(1)


def test_change_password_keeps_this_session_and_revokes_others(client: TestClient) -> None:
    register(client)
    login(client)
    other = dict(client.cookies)
    client.cookies.clear()
    login(client)
    current = dict(client.cookies)
    change = {"current_password": OLD, "new_password": NEW}
    assert client.post("/api/v1/me/password", json=change).status_code == 403
    wrong = client.post("/api/v1/me/password", headers=csrf(client), json={**change, "current_password": "wrong"})
    assert wrong.status_code == 400 and wrong.json()["detail"] == "Your current password is incorrect"
    same = client.post("/api/v1/me/password", headers=csrf(client), json={**change, "new_password": OLD})
    assert same.status_code == 400
    short = client.post("/api/v1/me/password", headers=csrf(client), json={**change, "new_password": "tiny-secret"})
    assert short.status_code == 422 and "tiny-secret" not in short.text
    assert client.post("/api/v1/me/password", headers=csrf(client), json=change).status_code == 204
    assert client.get("/api/v1/me").status_code == 200
    client.cookies.clear()
    for name, value in other.items():
        client.cookies.set(name, value, domain="testserver.local", path="/")
    assert client.get("/api/v1/me").status_code == 401
    client.cookies.clear()
    assert sign_in(client, OLD) == 401
    assert sign_in(client, NEW) == 200
    client.cookies.clear()
    for name, value in current.items():
        client.cookies.set(name, value, domain="testserver.local", path="/")
    assert client.get("/api/v1/me").status_code == 200


def test_change_password_requires_session(client: TestClient) -> None:
    result = client.post("/api/v1/me/password", headers=csrf(client),
                         json={"current_password": OLD, "new_password": NEW})
    assert result.status_code == 401


def test_reset_flow_is_generic_hashed_single_use_and_revokes_sessions(client: TestClient, outbox: Outbox) -> None:
    register(client)
    login(client)
    signed_in = dict(client.cookies)
    assert forgot(client, "missing@example.com") == 204
    assert outbox.messages == []
    assert forgot(client, "RESEARCHER@example.com") == 204
    assert forgot(client) == 204
    assert len(outbox.messages) == 2
    first, latest = (token_from(message) for message in outbox.messages)
    assert outbox.messages[1]["To"] == "researcher@example.com"
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        stored = db.scalars(select(PasswordResetToken.token_hash)).all()
        assert hash_token(latest) in stored and latest not in stored
    assert reset(client, first) == 400  # superseded by the newer link
    assert reset(client, latest, "short") == 422
    assert reset(client, latest) == 204
    assert reset(client, latest, "Third-synthetic-789") == 400
    client.cookies.clear()
    for name, value in signed_in.items():
        client.cookies.set(name, value, domain="testserver.local", path="/")
    assert client.get("/api/v1/me").status_code == 401
    assert sign_in(client, OLD) == 401
    assert sign_in(client, NEW) == 200


def test_reset_rejects_expired_and_unknown_tokens(client: TestClient, outbox: Outbox) -> None:
    register(client)
    assert reset(client, "not-a-real-token-but-long-enough") == 400
    assert client.post("/api/v1/auth/password/reset", json={"token": "x" * 40, "new_password": NEW}).status_code == 403
    forgot(client)
    token = token_from(outbox.messages[0])
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        db.execute(update(PasswordResetToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
        db.commit()
    result = client.post("/api/v1/auth/password/reset", headers=csrf(client), json={"token": token, "new_password": NEW})
    assert result.status_code == 400 and "expired" in result.json()["detail"]
    assert sign_in(client, OLD) == 200


def test_change_password_supersedes_outstanding_reset_link(client: TestClient, outbox: Outbox) -> None:
    register(client)
    forgot(client)
    token = token_from(outbox.messages[0])
    login(client)
    assert client.post("/api/v1/me/password", headers=csrf(client),
                       json={"current_password": OLD, "new_password": NEW}).status_code == 204
    assert reset(client, token, "Third-synthetic-789") == 400


def test_forgot_password_is_rate_limited_per_email(client: TestClient, outbox: Outbox) -> None:
    for _ in range(5):
        assert forgot(client, "missing@example.com") == 204
    result = client.post("/api/v1/auth/password/forgot", headers=csrf(client), json={"email": "missing@example.com"})
    assert result.status_code == 429 and result.headers["retry-after"] == "900"


def test_recovery_reports_missing_mail_configuration(client: TestClient) -> None:
    client.app.state.mail = None  # type: ignore[attr-defined]
    result = client.post("/api/v1/auth/password/forgot", headers=csrf(client), json={"email": "missing@example.com"})
    assert result.status_code == 503 and "not configured" in result.json()["detail"]


def test_mail_failure_is_logged_without_secrets(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    class Broken:
        def send(self, message: EmailMessage) -> None:
            self.body = message.get_content()
            raise ConnectionRefusedError("smtp down")

    broken = Broken()
    client.app.state.mail = broken  # type: ignore[attr-defined]
    register(client)
    with caplog.at_level(logging.WARNING, logger="researchpilot"):
        assert forgot(client) == 204
    token = re.search(r"#token=(\S+)", broken.body)
    assert token and "password_reset_email_failed category=ConnectionRefusedError" in caplog.text
    assert token.group(1) not in caplog.text and "researcher@example.com" not in caplog.text


def test_production_requires_encrypted_smtp() -> None:
    secure = {"environment": "production", "cookie_secure": True, "public_origin": "https://researchpilot.example"}
    with pytest.raises(ValueError):
        Settings(**secure)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(**secure, smtp_host="smtp.example", smtp_security="none")  # type: ignore[arg-type]
    assert Settings(**secure, smtp_host="smtp.example").smtp_security == "starttls"  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(password_reset_minutes=1)
