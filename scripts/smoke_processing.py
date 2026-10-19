"""Local HTTP smoke: real dispatcher/Celery/parser/DB, no mocked completion."""
import secrets
import time
from uuid import uuid4
from smoke_documents import request


def pdf_bytes():
    # Minimal two-page PDF with a correct cross-reference table; no host PDF dependency.
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for text in [b"The first page provides a traceable academic source statement for evidence testing.", b"The second page reports a different finding with its own physical page number."]:
        content = b"BT /F1 12 Tf 72 720 Td (" + text + b") Tj ET"
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    output = b"%PDF-1.4\n"
    offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        output += f"{offset:010d} 00000 n \n".encode()
    output += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return output


if __name__ == "__main__":
    email = "processing-smoke-" + uuid4().hex + "@example.com"
    password = secrets.token_urlsafe(24)
    request("/auth/register", "POST", {"email": email, "display_name": "Processing smoke fixture", "password": password})
    request("/auth/login", "POST", {"email": email, "password": password})
    p = request("/projects", "POST", {"title": "Synthetic extraction check", "description": "", "research_questions": [], "objectives": [], "request_id": str(uuid4())})
    path = "/projects/" + p["id"] + "/documents"
    original = pdf_bytes()
    result = request(path + "?filename=Processing-source.pdf", "POST", original, True)
    document = path + "/" + result["document"]["id"]
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        data = request(document)
        if data["status"] in {"extracted", "failed", "cancelled"}:
            break
        time.sleep(1)
    assert data["status"] == "extracted", data.get("processing", {}).get("error_code")
    assert data["processing"]["page_count"] == 2
    assert "second page reports" in request(document + "/pages/2")["text"]
    assert request(document + "/download") == original
    assert request(path + "?filename=Same-content.pdf", "POST", original, True)["duplicate"] is True
    assert request(document)["processing"]["attempts"] == 1
    # Malformed files are stored safely but must never be reported as extracted.
    bad = request(path + "?filename=Malformed.pdf", "POST", b"%PDF-1.4 invalid structure", True)
    bad_path = path + "/" + bad["document"]["id"]
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        failure = request(bad_path)
        if failure["status"] == "failed":
            break
        time.sleep(1)
    assert failure["status"] == "failed" and failure["processing"]["error_code"] == "invalid_pdf"
    print("Processing smoke passed: real background extraction, page provenance, exact original, duplicate stability and honest malformed-PDF failure.")
