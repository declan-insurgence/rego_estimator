from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vic_rego_estimator.auth import AuthError
from vic_rego_estimator.main import app
import vic_rego_estimator.main as main_module


class RejectingAuthenticator:
    def validate_authorization_header(self, header: str | None) -> dict:
        raise AuthError("Missing bearer token", error="invalid_request")

    def challenge_header(self, error: str, description: str) -> str:
        return (
            'Bearer realm="vic-rego-estimator", '
            'authorization_uri="https://example.auth0.com/authorize", '
            f'error="{error}", '
            f'error_description="{description}"'
        )


class AcceptingAuthenticator:
    def validate_authorization_header(self, header: str | None) -> dict:
        if not header:
            raise AuthError("Missing bearer token", error="invalid_request")
        return {"sub": "tester"}

    def challenge_header(self, error: str, description: str) -> str:
        return f'Bearer error="{error}", error_description="{description}"'


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(
    "method,payload",
    [
        ("initialize", {"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
        ("tools/list", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        (
            "tools/call",
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "estimate_registration_cost",
                    "arguments": {
                        "transaction_type": "renewal",
                        "vehicle_category": "passenger_car",
                    },
                },
            },
        ),
    ],
)
def test_auth_required_for_all_mcp_methods(monkeypatch, client: TestClient, method: str, payload: dict):
    monkeypatch.setattr(main_module, "authenticator", RejectingAuthenticator())

    response = client.post("/mcp", json=payload)

    assert response.status_code == 401, f"expected auth challenge for {method}"
    assert "WWW-Authenticate" in response.headers


def test_initialize_advertises_oauth_security_scheme_when_auth_enabled(monkeypatch, client: TestClient):
    monkeypatch.setattr(main_module, "authenticator", AcceptingAuthenticator())

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer token"},
        json={"jsonrpc": "2.0", "id": 10, "method": "initialize"},
    )

    assert response.status_code == 200
    schemes = response.json()["result"]["securitySchemes"]
    assert schemes == [
        {
            "type": "oauth2",
            "description": "Bearer token required for calling protected MCP methods.",
        }
    ]


def test_tool_output_contains_widget_metadata_for_apps_sdk(monkeypatch, client: TestClient):
    monkeypatch.setattr(main_module, "authenticator", None)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "estimate_registration_cost",
                "arguments": {
                    "transaction_type": "renewal",
                    "vehicle_category": "passenger_car",
                },
            },
        },
    )

    assert response.status_code == 200
    meta = response.json()["result"]["meta"]
    assert meta["openai_output_template"] == "ui://widget/index.html"
    assert "widgetDescription" in meta
    assert meta["data_freshness"]["refresh_policy"] == "monthly"


def test_widget_source_contains_host_bridge_compatibility_hooks():
    widget_source = Path(__file__).resolve().parents[2] / "ui" / "src" / "widget.ts"
    source = widget_source.read_text(encoding="utf-8")

    # Bridge APIs used by Apps SDK runtimes.
    assert "window.openai" in source
    assert "bridge.invokeTool ?? bridge.callTool" in source
    assert "bridge.on('toolOutput', updateHandler)" in source

    # Legacy/fallback host updates for embedded environments.
    assert "window.addEventListener('message'" in source
    assert "openai.toolOutput" in source

    # Host state bridge used to share estimates.
    assert "setWidgetState" in source
    assert "sharedQuote" in source
