from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.modules.documents.extraction import extract
from app.modules.documents.models import DocumentJob, DocumentPageText
from app.modules.documents.processing import claim, dispatch_once, finish, run_document
from app.modules.documents.storage import LocalStorage
from tests.conftest import csrf, login, register
from tests.pdf_fixture import pdf_bytes
from tests.test_documents import upload
from tests.test_projects import authenticated, create


def setup(client, content=None):
    authenticated(client)
    project = create(client)["id"]
    result = upload(client, project, content or pdf_bytes())
    assert result.status_code == 200, result.text
    document = result.json()["document"]
    return (
        project,
        UUID(document["id"]),
        client.app.state.session_factory,
        LocalStorage(client.app.state.settings.storage_root),
    )


def test_real_pdf_extraction_provenance_and_idempotence(client):
    p, d, factory, storage = setup(client)
    run_document(factory, storage, d)
    run_document(factory, storage, d)
    path = f"/api/v1/projects/{p}/documents/{d}"
    result = client.get(path).json()
    assert result["status"] == "extracted" and result["processing"]["attempts"] == 1
    assert result["processing"]["page_count"] == 2
    page = client.get(path + "/pages/2").json()
    assert "second page reports" in page["text"] and page["page_number"] == 2
    assert len(page["source_sha256"]) == 64 and "page-text-v1" in page["extractor_version"]
    assert client.get(path + "/pages/3").status_code == 404
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(DocumentPageText)) == 2
    events = client.get(f"/api/v1/projects/{p}/activity").json()["items"]
    assert sum(e["action"] == "paper_extracted" for e in events) == 1


@pytest.mark.parametrize(
    "content,code",
    [
        (b"%PDF-1.4\nbroken", "invalid_pdf"),
        (pdf_bytes(encrypted=True), "encrypted_pdf"),
        (pdf_bytes([""]), "insufficient_text"),
        (pdf_bytes(["tiny"] * 301), "page_limit"),
    ],
)
def test_honest_terminal_parser_outcomes(client, content, code):
    p, d, factory, storage = setup(client, content)
    run_document(factory, storage, d)
    path = f"/api/v1/projects/{p}/documents/{d}"
    result = client.get(path).json()
    assert result["status"] == "failed" and result["processing"]["error_code"] == code
    assert client.get(path + "/pages/1").status_code == 409
    assert client.post(path + "/retry", headers=csrf(client)).status_code == 409


def test_durable_dispatch_failure_redelivery_and_concurrent_claim(client):
    _, d, factory, _ = setup(client)

    def unavailable(_):
        raise RuntimeError("synthetic broker outage")

    with pytest.raises(RuntimeError):
        dispatch_once(factory, unavailable)
    with factory() as db:
        assert db.get(DocumentJob, d).state == "queued"
    published = []
    assert dispatch_once(factory, published.append) == 1
    assert published == [str(d)]
    with factory() as db:
        # Simulate a broker accepting but losing the message: still queued after dispatch.
        db.get(DocumentJob, d).dispatch_after = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert dispatch_once(factory, published.append) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(factory, d), range(2)))
    assert sum(r is not None for r in results) == 1


def test_worker_lease_recovery_and_fenced_stale_result(client):
    _, d, factory, _ = setup(client)
    old = claim(factory, d)[0]
    with factory() as db:
        db.get(DocumentJob, d).lease_until = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert not finish(factory, d, old, ["stale evidence"], None)
    dispatch_once(factory, lambda _: None)
    new = claim(factory, d)[0]
    assert new != old
    assert not finish(factory, d, old, ["stale evidence"], None)
    assert finish(factory, d, new, ["fresh evidence"], None)
    with factory() as db:
        assert db.get(DocumentPageText, (d, 1)).text == "fresh evidence"


def test_transient_retry_budget_csrf_and_foreign_scope(client):
    p, d, factory, _ = setup(client)
    path = f"/api/v1/projects/{p}/documents/{d}"
    for _n in range(3):
        token = claim(factory, d)[0]
        finish(factory, d, token, None, "storage_unavailable")
    result = client.get(path).json()
    assert result["status"] == "failed" and result["processing"]["attempts"] == 3
    assert client.post(path + "/retry").status_code == 403
    register(client, "outsider@example.com")
    login(client, "outsider@example.com")
    assert client.post(path + "/retry", headers=csrf(client)).status_code == 404
    assert client.get(path + "/pages/1").status_code == 404
    login(client)
    for _n in range(2):
        assert client.post(path + "/retry", headers=csrf(client)).json()["status"] == "queued"
        token = claim(factory, d)[0]
        finish(factory, d, token, None, "storage_unavailable")
    assert client.post(path + "/retry", headers=csrf(client)).status_code == 409


def test_removed_project_cancels_inflight_and_archives_reject_retry(client):
    p, d, factory, _ = setup(client)
    token = claim(factory, d)[0]
    base = f"/api/v1/projects/{p}"
    assert (
        client.request(
            "DELETE", base, headers=csrf(client), json={"expected_revision": 1}
        ).status_code
        == 204
    )
    assert finish(factory, d, token, ["must not publish this text"], None)
    with factory() as db:
        assert db.get(DocumentJob, d).state == "cancelled"
        assert db.scalar(select(func.count()).select_from(DocumentPageText)) == 0


def test_atomic_page_publication_rolls_back_on_activity_failure(client):
    _, d, factory, _ = setup(client)
    token = claim(factory, d)[0]
    with patch(
        "app.modules.documents.processing.projects.record", side_effect=RuntimeError("synthetic")
    ):
        with pytest.raises(RuntimeError):
            finish(factory, d, token, ["new page one", "new page two"], None)
    with factory() as db:
        assert db.get(DocumentJob, d).state == "processing"
        assert db.scalar(select(func.count()).select_from(DocumentPageText)) == 0


def test_integrity_and_subprocess_timeout(client):
    import subprocess

    _, d, factory, storage = setup(client)
    with patch(
        "app.modules.documents.extraction.subprocess.run",
        side_effect=subprocess.TimeoutExpired("parser", 60),
    ):
        pages, code = extract(
            storage.path(d), __import__("hashlib").sha256(storage.path(d).read_bytes()).hexdigest()
        )
    assert pages is None and code == "parser_timeout"
    storage.path(d).write_bytes(b"%PDF-tampered original")
    run_document(factory, storage, d)
    with factory() as db:
        assert db.get(DocumentJob, d).error_code == "integrity_mismatch"


def test_archived_retry_is_denied_but_accepted_extraction_can_finish(client):
    p, d, factory, storage = setup(client)
    base = f"/api/v1/projects/{p}"
    client.post(base + "/archive", headers=csrf(client), json={"expected_revision": 1})
    # Archiving freezes user edits, not an upload already accepted for processing.
    run_document(factory, storage, d)
    assert client.get(base + f"/documents/{d}/pages/1").status_code == 200
    with factory() as db:
        job = db.get(DocumentJob, d)
        job.state = "failed"
        job.error_code = "worker_failure"
        db.commit()
    assert client.post(base + f"/documents/{d}/retry", headers=csrf(client)).status_code == 409


def test_lease_crashes_exhaust_automatic_budget_and_removed_queued_job_cancels(client):
    p, d, factory, _ = setup(client)
    for _ in range(3):
        assert claim(factory, d) is not None
        with factory() as db:
            db.get(DocumentJob, d).lease_until = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        dispatch_once(factory, lambda _: None)
    with factory() as db:
        job = db.get(DocumentJob, d)
        assert job.state == "failed" and job.attempts == 3 and job.error_code == "worker_failure"
    client.post(f"/api/v1/projects/{p}/documents/{d}/retry", headers=csrf(client))
    client.request(
        "DELETE", f"/api/v1/projects/{p}", headers=csrf(client), json={"expected_revision": 1}
    )
    assert claim(factory, d) is None
    with factory() as db:
        assert db.get(DocumentJob, d).state == "cancelled"
