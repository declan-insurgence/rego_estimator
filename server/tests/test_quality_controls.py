from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vic_rego_estimator.main import app
import vic_rego_estimator.main as main_module


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_unsupported_method_returns_400_with_recovery_steps(client: TestClient):
    main_module.rate_limiter._requests.clear()

    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 11, "method": "bad/method"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "Unsupported MCP method: bad/method"
    assert payload["recovery_steps"] == [
        "Retry with a supported MCP method: initialize, tools/list, or tools/call."
    ]
    assert payload["request_id"]


def test_unknown_tool_returns_404_with_recovery_steps(client: TestClient):
    main_module.rate_limiter._requests.clear()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {"name": "not_a_real_tool", "arguments": {}},
        },
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "Unknown tool not_a_real_tool"
    assert payload["recovery_steps"] == ["Retry using a tool name returned by tools/list."]


def test_rate_limit_returns_429_retry_after_and_recovery_steps(monkeypatch, client: TestClient):
    monkeypatch.setattr(main_module, "authenticator", None)
    monkeypatch.setattr(main_module.rate_limiter, "max_requests", 1)
    monkeypatch.setattr(main_module.rate_limiter, "window_seconds", 60)
    main_module.rate_limiter._requests.clear()

    first = client.post("/mcp", json={"jsonrpc": "2.0", "id": 13, "method": "tools/list"})
    second = client.post("/mcp", json={"jsonrpc": "2.0", "id": 14, "method": "tools/list"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    payload = second.json()
    assert payload["recovery_steps"] == ["Wait for Retry-After seconds, then retry the request."]


def test_internal_error_returns_500_with_recovery_steps(monkeypatch, client: TestClient):
    async def failing_handler(_: dict):
        raise RuntimeError("boom")

    original_handler = main_module.TOOLS["estimate_registration_cost"].handler
    monkeypatch.setattr(main_module.TOOLS["estimate_registration_cost"], "handler", failing_handler)
    main_module.rate_limiter._requests.clear()

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "estimate_registration_cost",
                "arguments": {"transaction_type": "renewal", "vehicle_category": "passenger_car"},
            },
        },
    )

    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"] == "Internal error while handling MCP request"
    assert payload["recovery_steps"] == [
        "Retry the request. If the issue persists, contact support with X-Request-ID."
    ]

    monkeypatch.setattr(main_module.TOOLS["estimate_registration_cost"], "handler", original_handler)


def test_request_id_generated_when_missing(client: TestClient):
    main_module.rate_limiter._requests.clear()

    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 16, "method": "tools/list"})

    assert response.status_code == 200
    header_request_id = response.headers["X-Request-ID"]
    assert header_request_id


def test_www_authenticate_header_contains_actionable_details(monkeypatch):
    class RejectingAuthenticator:
        def validate_authorization_header(self, header: str | None) -> dict:
            raise main_module.AuthError("Missing bearer token", error="invalid_request")

        def challenge_header(self, error: str, description: str) -> str:
            return (
                'Bearer realm="vic-rego-estimator", '
                'authorization_uri="https://example.auth0.com/authorize", '
                'resource="api://vic-rego", '
                'client_id="chatgpt-connector", '
                f'error="{error}", '
                f'error_description="{description}"'
            )

    monkeypatch.setattr(main_module, "authenticator", RejectingAuthenticator())
    main_module.rate_limiter._requests.clear()
    client = TestClient(app)

    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 17, "method": "tools/list"})

    assert response.status_code == 401
    challenge = response.headers["WWW-Authenticate"]
    assert 'authorization_uri="https://example.auth0.com/authorize"' in challenge
    assert 'resource="api://vic-rego"' in challenge
    assert 'client_id="chatgpt-connector"' in challenge
    assert 'error="invalid_request"' in challenge
