"""Local built-app HTTP check using synthetic accounts; no browser automation."""
import http.cookiejar
import json
import secrets
import urllib.error
import urllib.request
from uuid import uuid4

BASE = 'http://127.0.0.1:3100'
ORIGIN = 'http://localhost:3100'


class LocalClient:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, path, method='GET', body=None, csrf=True):
        headers = {'Content-Type': 'application/json', 'Host': 'localhost:3100'}
        if method != 'GET' and csrf:
            code, value = self.request('/api/v1/auth/csrf')
            assert code == 200
            headers.update({'Origin': ORIGIN, 'X-CSRF-Token': value['csrf_token']})
        req = urllib.request.Request(BASE + path, method=method, headers=headers, data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(req, timeout=10) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw and response.headers.get_content_type() == 'application/json' else raw
        except urllib.error.HTTPError as error:
            return error.code, None

    def authenticate(self):
        email = f'project-smoke-{uuid4().hex}@example.com'
        password = secrets.token_urlsafe(24)
        assert self.request('/api/v1/auth/register', 'POST', {'email': email, 'password': password, 'display_name': 'Synthetic project smoke account'})[0] == 201
        assert self.request('/api/v1/auth/login', 'POST', {'email': email, 'password': password})[0] == 200


owner, outsider = LocalClient(), LocalClient()
assert owner.request('/api/v1/health/ready')[0] == 200
assert owner.request('/projects')[0] == 200
assert owner.request('/api/v1/projects')[0] == 401
owner.authenticate()
payload = {'title': 'Synthetic local project smoke', 'description': 'Synthetic boundary test. ' + 'x' * 3900, 'research_questions': ['Q' + 'x' * 499] * 20, 'objectives': ['O' + 'x' * 499] * 20, 'request_id': str(uuid4())}
code, project = owner.request('/api/v1/projects', 'POST', payload)
assert code == 201
path = '/api/v1/projects/' + project['id']
assert owner.request('/api/v1/projects', 'POST', payload)[1]['id'] == project['id']
assert owner.request(path)[1]['revision'] == 1
assert owner.request(path + '/activity')[1]['items'][0]['action'] == 'created'
print('PASS built-app project creation, persistence and retry idempotency', flush=True)

assert owner.request(path, 'PATCH', {'title': 'Updated synthetic smoke project', 'expected_revision': 1})[0] == 200
assert owner.request(path, 'PATCH', {'title': 'Stale overwrite', 'expected_revision': 1})[0] == 409
assert owner.request(path, 'PATCH', {'title': 'No CSRF', 'expected_revision': 2}, csrf=False)[0] == 403
assert owner.request(path + '/archive', 'POST', {'expected_revision': 2})[1]['archived_at']
assert owner.request('/api/v1/projects')[1]['total'] == 0
assert owner.request('/api/v1/projects?status=archived')[1]['total'] == 1
assert owner.request(path, 'PATCH', {'title': 'Archived overwrite', 'expected_revision': 3})[0] == 409
assert owner.request(path + '/restore', 'POST', {'expected_revision': 3})[1]['archived_at'] is None
assert len(owner.request(path + '/activity')[1]['items']) == 4
print('PASS stale-write protection, CSRF, archive/restore and activity', flush=True)

outsider.authenticate()
assert outsider.request(path)[0] == 404
assert outsider.request(path + '/activity')[0] == 404
assert outsider.request(path, 'PATCH', {'title': 'Foreign overwrite', 'expected_revision': 4})[0] == 404
assert owner.request(path, 'DELETE', {'expected_revision': 4})[0] == 204
assert owner.request(path, 'DELETE', {'expected_revision': 4})[0] == 204
assert owner.request(path)[0] == 404
assert owner.request('/api/v1/projects?status=all')[1]['total'] == 0
assert owner.request('/api/v1/auth/logout', 'POST')[0] == 204
assert outsider.request('/api/v1/auth/logout', 'POST')[0] == 204
print('PASS cross-account denial and idempotent soft removal', flush=True)
print('Synthetic account records retained; no real project or uploaded file was removed.', flush=True)
