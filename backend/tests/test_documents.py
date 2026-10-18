from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.modules.documents.models import Document
from app.modules.documents.storage import LocalStorage
from app.modules.projects.models import ProjectActivity
from tests.conftest import csrf, login, register
from tests.test_projects import authenticated, create

PDF = b"%PDF-1.4\nsynthetic storage fixture; deliberately not parseable\n%%EOF"


def upload(client: TestClient, project: str, content: bytes = PDF, name: str = "paper.pdf"):
    return client.post(
        f"/api/v1/projects/{project}/documents",
        params={"filename": name},
        content=content,
        headers={**csrf(client), "content-type": "application/pdf"},
    )


def test_private_storage_roundtrip_duplicates_and_activity(client: TestClient):
    authenticated(client)
    p = create(client)["id"]
    result = upload(client, p)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["duplicate"] is False and data["document"]["status"] == "stored"
    d = data["document"]["id"]
    path = f"/api/v1/projects/{p}/documents"
    assert client.get(path).json()["total"] == 1
    assert upload(client, p, name="renamed.pdf").json()["duplicate"] is True
    response = client.get(path + f"/{d}/download")
    assert response.content == PDF
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["cache-control"] == "no-store"
    assert "sha256" not in client.get(path + f"/{d}").json()
    events = client.get(f"/api/v1/projects/{p}/activity").json()["items"]
    assert sum(e["action"] == "paper_stored" for e in events) == 1
    assert not list((client.app.state.settings.storage_root / "staging").iterdir())


def test_foreign_missing_and_deleted_projects_hide_documents(client: TestClient):
    authenticated(client)
    p = create(client)["id"]
    d = upload(client, p).json()["document"]["id"]
    base = f"/api/v1/projects/{p}"
    register(client, "foreign@example.com")
    login(client, "foreign@example.com")
    for suffix in ["", f"/{d}", f"/{d}/download"]:
        assert client.get(base + "/documents" + suffix).status_code == 404
    assert upload(client, p).status_code == 404
    login(client)
    assert (
        client.request(
            "DELETE", base, headers=csrf(client), json={"expected_revision": 1}
        ).status_code
        == 204
    )
    assert client.get(base + "/documents").status_code == 404
    assert client.get(base + f"/documents/{d}/download").status_code == 404
    # Another account must not learn whether a hash exists in the first account.
    register(client, "other@example.com")
    login(client, "other@example.com")
    for suffix in ["", f"/{d}", f"/{d}/download"]:
        assert client.get(base + "/documents" + suffix).status_code == 404
    assert upload(client, p).status_code == 404


def test_upload_validation_csrf_and_cleanup(client: TestClient):
    authenticated(client)
    p = create(client)["id"]
    path = f"/api/v1/projects/{p}/documents"
    assert (
        client.post(
            path + "?filename=a.pdf", content=PDF, headers={"content-type": "application/pdf"}
        ).status_code
        == 403
    )
    assert upload(client, p, b"not a PDF").status_code == 422
    assert upload(client, p, name="../paper.pdf").status_code == 422
    assert (
        client.post(
            path + "?filename=a.pdf",
            content=PDF,
            headers={**csrf(client), "content-type": "text/plain"},
        ).status_code
        == 415
    )
    with patch("app.modules.documents.service.MAX_BYTES", 10):
        assert upload(client, p).status_code == 413
    assert client.get(path).json()["total"] == 0
    assert not list((client.app.state.settings.storage_root / "staging").iterdir())


def test_archived_project_read_only_and_project_scoped_hash(client: TestClient):
    authenticated(client)
    p, other = create(client)["id"], create(client)["id"]
    d = upload(client, p).json()["document"]["id"]
    assert upload(client, other).json()["duplicate"] is False
    assert client.get(f"/api/v1/projects/{other}/documents/{d}").status_code == 404
    client.post(
        f"/api/v1/projects/{p}/archive", headers=csrf(client), json={"expected_revision": 1}
    )
    assert upload(client, p).status_code == 409
    assert client.get(f"/api/v1/projects/{p}/documents/{d}/download").content == PDF


def test_quota_and_transaction_failure_keep_metadata_atomic(client: TestClient):
    authenticated(client)
    p = create(client)["id"]
    with patch("app.modules.documents.service.MAX_PROJECT_DOCUMENTS", 0):
        assert upload(client, p).status_code == 409
    with patch(
        "app.modules.documents.service.projects.record",
        side_effect=RuntimeError("synthetic failure"),
    ):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            upload(client, p)
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(ProjectActivity)
                .where(ProjectActivity.action == "paper_stored")
            )
            == 0
        )
    assert not list((client.app.state.settings.storage_root / "staging").iterdir())


def test_storage_path_never_uses_user_filename_and_missing_file_is_safe(client: TestClient):
    authenticated(client)
    p = create(client)["id"]
    d = upload(client, p, name="Academic paper — study.pdf").json()["document"]["id"]
    storage = LocalStorage(client.app.state.settings.storage_root)
    assert storage.path(UUID(d)).name == d + ".pdf"
    storage.path(UUID(d)).unlink()
    result = client.get(f"/api/v1/projects/{p}/documents/{d}/download")
    assert result.status_code == 503
    assert str(storage.root) not in result.text


def test_overlapping_upload_retries_store_one_original(client: TestClient):
    from concurrent.futures import ThreadPoolExecutor
    from hashlib import sha256

    from app.modules.documents.service import store
    from app.modules.projects.models import ResearchProject

    authenticated(client)
    p = create(client)["id"]
    storage = LocalStorage(client.app.state.settings.storage_root)
    with client.app.state.session_factory() as db:
        owner = db.get(ResearchProject, UUID(p)).owner_id

    def send(_):
        staged = storage.stage()
        staged.write_bytes(PDF)
        with client.app.state.session_factory() as db:
            return store(
                db, owner, UUID(p), "paper.pdf", staged, sha256(PDF).hexdigest(), len(PDF), storage
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    assert sorted(r.duplicate for r in results) == [False, True]
    assert results[0].document.id == results[1].document.id
    assert len(list((storage.root / "papers").iterdir())) == 1
    assert not list((storage.root / "staging").iterdir())


def test_storage_error_is_safe_and_list_is_paginated(client: TestClient):
    authenticated(client)
    p = create(client)["id"]
    for n in range(3):
        assert upload(client, p, PDF + str(n).encode()).status_code == 200
    path = f"/api/v1/projects/{p}/documents"
    first = client.get(path + "?limit=2").json()
    second = client.get(path + "?limit=2&offset=2").json()
    assert first["total"] == 3 and len(first["items"]) == 2 and len(second["items"]) == 1
    assert {p["id"] for p in first["items"]}.isdisjoint({p["id"] for p in second["items"]})
    with patch(
        "app.modules.documents.storage.LocalStorage.publish", side_effect=OSError("/private/path")
    ):
        response = upload(client, p, PDF + b"other")
    assert response.status_code == 503 and "/private/path" not in response.text
    assert client.get(path).json()["total"] == 3
