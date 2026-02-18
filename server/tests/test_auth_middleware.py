from fastapi.testclient import TestClient

from vic_rego_estimator.auth import AuthError
from vic_rego_estimator.main import app
import vic_rego_estimator.main as main_module


class StubAuthenticator:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def validate_authorization_header(self, header: str | None) -> dict:
        if self.should_fail:
            raise AuthError("Missing bearer token", error="invalid_request")
        if not header:
            raise AuthError("Missing bearer token", error="invalid_request")
        return {"sub": "tester"}

    def challenge_header(self, error: str, description: str) -> str:
        return (
            'Bearer realm="vic-rego-estimator", '
            'authorization_uri="https://example.auth0.com/authorize", '
            f'error="{error}", '
            f'error_description="{description}"'
        )


def test_mcp_missing_token_returns_401(monkeypatch):
    monkeypatch.setattr(main_module, "authenticator", StubAuthenticator(should_fail=True))
    client = TestClient(app)

    res = client.post('/mcp', json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert res.status_code == 401
    assert 'WWW-Authenticate' in res.headers
    assert 'authorization_uri="https://example.auth0.com/authorize"' in res.headers['WWW-Authenticate']


def test_mcp_with_token_passes_auth(monkeypatch):
    monkeypatch.setattr(main_module, "authenticator", StubAuthenticator())
    client = TestClient(app)

    res = client.post(
        '/mcp',
        headers={"Authorization": "Bearer test-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    assert res.status_code == 200
    assert "tools" in res.json()["result"]


def test_mcp_rate_limit_enforced(monkeypatch):
    monkeypatch.setattr(main_module, "authenticator", None)
    monkeypatch.setattr(main_module.rate_limiter, "max_requests", 1)
    monkeypatch.setattr(main_module.rate_limiter, "window_seconds", 60)
    main_module.rate_limiter._requests.clear()

    client = TestClient(app)

    first = client.post('/mcp', json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    second = client.post('/mcp', json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]


def test_request_id_is_echoed_in_response_header(monkeypatch):
    monkeypatch.setattr(main_module, "authenticator", None)
    main_module.rate_limiter._requests.clear()
    client = TestClient(app)

    response = client.post(
        '/mcp',
        headers={"X-Request-ID": "req-123"},
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
