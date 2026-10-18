from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.modules.projects import service
from app.modules.projects.models import ProjectActivity, ResearchProject
from app.modules.projects.schemas import ProjectCreate, ProjectPatch
from tests.conftest import csrf, login, register


def create(
    client: TestClient, title: str = "AI-supported learning", request_id: str | None = None
) -> dict:
    result = client.post(
        "/api/v1/projects",
        headers=csrf(client),
        json={
            "title": title,
            "description": "A focused research review",
            "research_questions": ["What does the evidence support?"],
            "objectives": ["Compare methods"],
            "request_id": request_id or str(uuid4()),
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def authenticated(client: TestClient) -> None:
    register(client)
    login(client)


def test_project_lifecycle_activity_and_soft_delete(client: TestClient) -> None:
    assert client.get("/api/v1/projects").status_code == 401
    authenticated(client)
    p = create(client)
    path = "/api/v1/projects/" + p["id"]
    assert p["revision"] == 1
    assert client.get(path).json()["research_questions"] == ["What does the evidence support?"]
    assert client.get("/api/v1/projects").json()["total"] == 1
    result = client.patch(
        path,
        headers=csrf(client),
        json={"expected_revision": 1, "title": "Revised question", "objectives": []},
    )
    assert result.status_code == 200 and result.json()["revision"] == 2
    archive = client.post(path + "/archive", headers=csrf(client), json={"expected_revision": 2})
    assert archive.status_code == 200 and archive.json()["archived_at"]
    assert client.get("/api/v1/projects").json()["items"] == []
    assert client.get("/api/v1/projects?status=archived").json()["total"] == 1
    assert (
        client.patch(
            path, headers=csrf(client), json={"expected_revision": 3, "title": "Forbidden edit"}
        ).status_code
        == 409
    )
    restore = client.post(path + "/restore", headers=csrf(client), json={"expected_revision": 3})
    assert restore.status_code == 200 and restore.json()["archived_at"] is None
    events = client.get(path + "/activity").json()["items"]
    assert [e["action"] for e in events] == ["restored", "archived", "updated", "created"]
    assert (
        client.request(
            "DELETE", path, headers=csrf(client), json={"expected_revision": 4}
        ).status_code
        == 204
    )
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/projects?status=all").json()["total"] == 0
    assert (
        client.request(
            "DELETE", path, headers=csrf(client), json={"expected_revision": 4}
        ).status_code
        == 204
    )
    with client.app.state.session_factory() as db:
        retained = db.get(ResearchProject, UUID(p["id"]))
        assert retained and retained.deleted_at
        assert (
            db.scalar(
                select(func.count())
                .select_from(ProjectActivity)
                .where(ProjectActivity.project_id == retained.id)
            )
            == 5
        )


def test_project_ownership_all_operations_and_csrf(client: TestClient) -> None:
    authenticated(client)
    p = create(client)
    path = "/api/v1/projects/" + p["id"]
    assert client.patch(path, json={"expected_revision": 1, "title": "No CSRF"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=csrf(client)).status_code == 204
    register(client, "outsider@example.com")
    login(client, "outsider@example.com")
    assert client.get("/api/v1/projects").json()["total"] == 0
    for method, suffix, body in [
        ("GET", "", None),
        ("GET", "/activity", None),
        ("PATCH", "", {"title": "Attack", "expected_revision": 1}),
        ("POST", "/archive", {"expected_revision": 1}),
        ("POST", "/restore", {"expected_revision": 1}),
        ("DELETE", "", {"expected_revision": 1}),
    ]:
        assert (
            client.request(method, path + suffix, headers=csrf(client), json=body).status_code
            == 404
        )


def test_stale_edits_and_validation_do_not_overwrite(client: TestClient) -> None:
    authenticated(client)
    p = create(client)
    path = "/api/v1/projects/" + p["id"]
    assert (
        client.patch(
            path, headers=csrf(client), json={"title": "New title", "expected_revision": 1}
        ).status_code
        == 200
    )
    stale = client.patch(
        path, headers=csrf(client), json={"title": "Stale overwrite", "expected_revision": 1}
    )
    assert stale.status_code == 409
    for fields in [
        {"title": " "},
        {"title": None},
        {"owner_id": str(uuid4())},
        {"research_questions": [" "]},
        {"objectives": ["x"] * 21},
        {},
    ]:
        assert (
            client.patch(
                path, headers=csrf(client), json={"expected_revision": 2, **fields}
            ).status_code
            == 422
        )
    assert client.get(path).json()["title"] == "New title"
    assert len(client.get(path + "/activity").json()["items"]) == 2


def test_retried_create_is_idempotent_and_scoped_to_user(client: TestClient) -> None:
    authenticated(client)
    key = str(uuid4())
    first = create(client, request_id=key)
    assert create(client, request_id=key)["id"] == first["id"]
    result = client.post(
        "/api/v1/projects",
        headers=csrf(client),
        json={"title": "Different payload", "request_id": key},
    )
    assert result.status_code == 409
    assert len(client.get("/api/v1/projects/" + first["id"] + "/activity").json()["items"]) == 1
    client.post("/api/v1/auth/logout", headers=csrf(client))
    register(client, "other@example.com")
    login(client, "other@example.com")
    assert create(client, request_id=key)["id"] != first["id"]


def test_pagination_literal_search_and_activity_pages(client: TestClient) -> None:
    authenticated(client)
    for title in ["Study one", "Study two", "100% confidence", "Study three"]:
        create(client, title)
    first = client.get("/api/v1/projects?limit=2").json()
    second = client.get(
        "/api/v1/projects", params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert (
        len({p["id"] for p in first["items"] + second["items"]}) == 4
        and second["next_cursor"] is None
    )
    assert client.get("/api/v1/projects", params={"search": "%"}).json()["total"] == 1
    assert client.get("/api/v1/projects?cursor=broken").status_code == 400
    p = first["items"][0]
    path = "/api/v1/projects/" + p["id"]
    client.patch(path, headers=csrf(client), json={"title": "Updated", "expected_revision": 1})
    page = client.get(path + "/activity?limit=1").json()
    assert page["items"][0]["action"] == "updated"
    assert (
        client.get(path + "/activity", params={"cursor": page["next_cursor"]}).json()["items"][0][
            "action"
        ]
        == "created"
    )


def test_concurrent_creation_creates_one_project_and_one_event(client: TestClient) -> None:
    authenticated(client)
    owner = UUID(client.get("/api/v1/me").json()["id"])
    data = ProjectCreate(title="Concurrent project", request_id=uuid4())

    def work() -> UUID:
        with client.app.state.session_factory() as db:
            return service.create(db, owner, data).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: work(), range(2)))
    assert results[0] == results[1]
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProjectActivity)) == 1


def test_concurrent_edits_reject_one_stale_writer(client: TestClient) -> None:
    authenticated(client)
    p = create(client)
    owner = UUID(client.get("/api/v1/me").json()["id"])

    def work(title: str) -> int:
        with client.app.state.session_factory() as db:
            try:
                service.update(
                    db, owner, UUID(p["id"]), ProjectPatch(title=title, expected_revision=1)
                )
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(work, ["First writer", "Second writer"]))
    assert sorted(outcomes) == [200, 409]
    assert client.get("/api/v1/projects/" + p["id"]).json()["revision"] == 2
    assert len(client.get("/api/v1/projects/" + p["id"] + "/activity").json()["items"]) == 2


def test_failed_activity_rolls_back_project_creation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticated(client)

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic activity persistence failure")

    monkeypatch.setattr(service, "record", fail)
    with pytest.raises(RuntimeError, match="Synthetic activity"):
        client.post(
            "/api/v1/projects",
            headers=csrf(client),
            json={"title": "Must roll back", "request_id": str(uuid4())},
        )
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ResearchProject)) == 0
        assert db.scalar(select(func.count()).select_from(ProjectActivity)) == 0
