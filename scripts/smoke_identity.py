"""Check a local built deployment over HTTP, without browser/screenshot automation.

Creates one synthetic development account per run; never points at production.
Passwords and cookies live in memory and are not printed or saved.
"""
import http.cookiejar
import json
import secrets
import sys
import urllib.error
import urllib.request
from uuid import uuid4

origin = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:3100'
if origin != 'http://localhost:3100':
    raise SystemExit('This check is restricted to the local development origin')
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path, method='GET', data=None, extra=None, opener=client):
    headers = {'Content-Type': 'application/json'}
    headers.update(extra or {})
    payload = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(origin + path, data=payload, method=method, headers=headers)
    try:
        with opener.open(req, timeout=10) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


def mutation(path, method='POST', data=None, override=None):
    code, body, _ = request('/api/v1/auth/csrf')
    assert code == 200
    headers = {'Origin': origin, 'X-CSRF-Token': json.loads(body)['csrf_token']}
    headers.update(override or {})
    return request(path, method, data, headers)


for path in ['/register', '/login', '/profile', '/dashboard']:
    code, body, headers = request(path)
    assert code == 200 and b'<div id="root">' in body
    assert headers['X-Content-Type-Options'] == 'nosniff'
    assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
print('PASS built-app client-route reloads and security headers')

code, body, _ = request('/api/v1/health/ready')
assert code == 200 and json.loads(body)['status'] == 'ready'
assert request('/api/v1/me')[0] == 401
print('PASS same-origin API proxy and unauthorized profile denial')

email = f'local-smoke-{uuid4().hex}@example.com'
password = secrets.token_urlsafe(24)
code, _, _ = mutation('/api/v1/auth/register', data={
    'email': email, 'password': password, 'display_name': 'Synthetic local smoke account',
})
assert code == 201
code, body, headers = mutation('/api/v1/auth/login', data={'email': email, 'password': password})
assert code == 200 and json.loads(body)['email'] == email
assert all('HttpOnly' in value and 'SameSite=lax' in value for value in headers.get_all('Set-Cookie'))
assert any(cookie.name == 'rp_session' for cookie in jar)
print('PASS registration and login through the built frontend proxy')

code, _, _ = request('/api/v1/me', 'PATCH', {'display_name': 'Not allowed'})
assert code == 403
assert mutation('/api/v1/me', 'PATCH', {'display_name': 'Not allowed'}, {'Origin': 'https://untrusted.example'})[0] == 403
code, body, _ = mutation('/api/v1/me', 'PATCH', {'display_name': 'Reviewed local smoke account'})
assert code == 200 and json.loads(body)['display_name'] == 'Reviewed local smoke account'
code, body, _ = request('/api/v1/me')
assert code == 200 and json.loads(body)['display_name'] == 'Reviewed local smoke account'
print('PASS persisted profile edit and CSRF/origin rejection')

raw_session = next(cookie.value for cookie in jar if cookie.name == 'rp_session')
assert mutation('/api/v1/auth/logout')[0] == 204
assert request('/api/v1/me')[0] == 401
anonymous = urllib.request.build_opener()
assert request('/api/v1/me', extra={'Cookie': 'rp_session=' + raw_session}, opener=anonymous)[0] == 401
print('PASS logout revocation including replay of the old session')
print('Verified local identity foundation. No visual UI test or RAG inference performed.')
