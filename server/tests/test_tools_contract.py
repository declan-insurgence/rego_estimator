import pytest
from fastapi.testclient import TestClient

from vic_rego_estimator.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_initialize(client: TestClient):
    res = client.post('/mcp', json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert res.status_code == 200
    payload = res.json()['result']
    assert payload['serverInfo']['name'] == 'vic-rego-estimator'
    assert payload['capabilities']['tools']['listChanged'] is False
    assert payload['securitySchemes']


def test_tools_list(client: TestClient):
    res = client.post('/mcp', json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert res.status_code == 200
    tools = res.json()['result']['tools']
    names = {tool['name'] for tool in tools}
    assert {"normalize_vehicle_request", "get_fee_snapshot", "estimate_registration_cost", "explain_assumptions"} <= names
    assert all('annotations' in tool for tool in tools)
    assert all('securitySchemes' in tool for tool in tools)


def test_estimate_transfer_unknown_value(client: TestClient):
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "estimate_registration_cost",
            "arguments": {
                "transaction_type": "transfer",
                "vehicle_category": "passenger_car",
                "term_months": 12,
                "concession_flags": {"pensioner": True}
            }
        }
    }
    res = client.post('/mcp', json=payload)
    assert res.status_code == 200
    estimate = res.json()['result']['structuredContent']['estimate']
    assert estimate['total_max'] >= estimate['total_min']
    assert any(line['key'] == 'motor_vehicle_duty' for line in estimate['line_items'])
