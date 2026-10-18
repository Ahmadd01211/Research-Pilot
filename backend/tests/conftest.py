import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import Settings
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def migrated() -> Iterator[None]:
    url = os.environ.get("RP_DATABASE_URL", "")
    if not url.endswith("/rp_greenfield_test") or os.environ.get("RP_ENVIRONMENT") != "test":
        raise RuntimeError("Tests require an explicitly isolated rp_greenfield_test database")
    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(rate_namespace="rp:test:" + str(uuid4()))
    engine = create_engine(settings.database_url.get_secret_value())
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE sessions, users CASCADE"))
    engine.dispose()
    with TestClient(create_app(settings)) as value:
        yield value


def csrf(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"origin": "http://localhost:3100", "x-csrf-token": token}


def register(client: TestClient, email: str = "researcher@example.com") -> None:
    response = client.post("/api/v1/auth/register", headers=csrf(client), json={
        "email": email, "display_name": "Researcher", "password": "Synthetic-password-123",
    })
    assert response.status_code == 201, response.text


def login(client: TestClient, email: str = "researcher@example.com") -> None:
    response = client.post("/api/v1/auth/login", headers=csrf(client), json={
        "email": email, "password": "Synthetic-password-123",
    })
    assert response.status_code == 200, response.text
