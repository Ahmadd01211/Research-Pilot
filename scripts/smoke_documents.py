"""Local built-app upload roundtrip, synthetic account and private fixture only."""
import http.cookiejar
import json
import secrets
import urllib.parse
import urllib.request
from uuid import uuid4

base = "http://127.0.0.1:3100/api/v1"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path, method="GET", data=None, binary=False):
    headers = {"Host": "localhost:3100", "Origin": "http://localhost:3100"}
    if method != "GET":
        token = request("/auth/csrf")["csrf_token"]
        headers["x-csrf-token"] = token
        headers["content-type"] = "application/pdf" if binary else "application/json"
    body = data if binary else json.dumps(data).encode() if data is not None else None
    with opener.open(urllib.request.Request(base + path, data=body, method=method, headers=headers), timeout=20) as response:
        if binary or path.endswith("/download"):
            return response.read() if path.endswith("/download") else json.load(response)
        return json.load(response) if response.status != 204 else None


if __name__ == "__main__":
    email = "storage-smoke-" + uuid4().hex + "@example.com"
    password = secrets.token_urlsafe(24)
    request("/auth/register", "POST", {"email": email, "display_name": "Storage smoke fixture", "password": password})
    request("/auth/login", "POST", {"email": email, "password": password})
    project = request("/projects", "POST", {"title": "Synthetic storage check", "description": "", "research_questions": [], "objectives": [], "request_id": str(uuid4())})
    path = "/projects/" + project["id"] + "/documents"
    # Larger than the normal metadata body cap; storage-only fixture, not a parser test.
    pdf = b"%PDF-1.4\n" + b"synthetic storage fixture\n" * 15000 + b"%%EOF"
    result = request(path + "?filename=" + urllib.parse.quote("Synthetic original.pdf"), "POST", pdf, True)
    assert result["duplicate"] is False
    doc = result["document"]
    assert request(path + "/" + doc["id"] + "/download") == pdf
    assert request(path + "?filename=Renamed.pdf", "POST", pdf, True)["duplicate"] is True
    assert request(path)["total"] == 1
    assert request(path)["items"][0]["status"] == "stored"
    # Retain the synthetic fixture so the persistence probe can run after container recreation.
    print("Built-app storage smoke passed: private upload, >256 KiB proxy body, roundtrip, duplicate, list and honest status.")
