"""Every non-2xx response uses the ErrorResponse shape and leaks nothing."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.seed import seed_customers
from backend.tests.conftest import CUSTOMERS_CSV
from backend.tests.fakes import ExplodingPolicyEngine, FakeDraftGenerator
from contracts.api import CustomerRequest
from contracts.models import ErrorResponse


def test_unknown_route_is_error_response(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert ErrorResponse.model_validate(response.json()).error.code == "not_found"


def test_wrong_method_is_error_response(client: TestClient) -> None:
    response = client.post("/api/health")

    assert response.status_code == 405
    error = ErrorResponse.model_validate(response.json()).error
    assert error.code == "method_not_allowed"


def test_malformed_json_is_400_and_schema_error_is_422(client: TestClient) -> None:
    app = client.app

    @app.post("/api/_test/echo")
    def echo(body: CustomerRequest) -> CustomerRequest:
        return body

    bad_json = client.post(
        "/api/_test/echo",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert bad_json.status_code == 400
    assert bad_json.json()["error"]["code"] == "bad_request"

    bad_schema = client.post(
        "/api/_test/echo", json={"customer_id": "someone@example.com"}
    )
    assert bad_schema.status_code == 422
    error = ErrorResponse.model_validate(bad_schema.json()).error
    assert error.code == "validation_error"
    assert any("customer_id" in str(e) for e in error.details["errors"])
    assert "@" not in bad_schema.text  # input values are never echoed


def test_unexpected_error_is_500_without_internals(settings: Settings) -> None:
    app = create_app(
        ExplodingPolicyEngine(), FakeDraftGenerator(), settings, policy_versions={}
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        seed_customers(app.state.session_factory, CUSTOMERS_CSV)
        response = client.get("/api/customers")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error.",
            "details": {},
        }
    }
    assert "Traceback" not in response.text
    assert "secret-detail" not in response.text
