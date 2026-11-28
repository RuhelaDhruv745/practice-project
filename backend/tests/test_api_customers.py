from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.fakes import FakePolicyEngine
from contracts.api import CustomerSummary, Page
from contracts.models import CustomerProfile, ErrorResponse


def test_list_customers_returns_page_of_summaries(client: TestClient) -> None:
    response = client.get("/api/customers")

    assert response.status_code == 200
    page = Page[CustomerSummary].model_validate(response.json())
    assert page.total == 4
    assert [s.customer_id for s in page.items] == [
        "CUST-001",
        "CUST-002",
        "CUST-003",
        "CUST-004",
    ]
    assert set(response.json()["items"][0]) == set(CustomerSummary.model_fields)


def test_primary_segment_comes_from_policy_engine(
    client: TestClient, policy_engine: FakePolicyEngine
) -> None:
    items = client.get("/api/customers").json()["items"]

    segments = {i["customer_id"]: i["primary_segment"] for i in items}
    assert segments == {
        "CUST-001": "loyalty_candidate",
        "CUST-002": "declining",
        "CUST-003": "payment_reminder",
        "CUST-004": None,
    }
    assert ("classify", "CUST-004") in policy_engine.calls


def test_list_customers_paginates(client: TestClient) -> None:
    body = client.get("/api/customers", params={"limit": 2, "offset": 1}).json()

    assert body["total"] == 4
    assert [i["customer_id"] for i in body["items"]] == ["CUST-002", "CUST-003"]


def test_list_customers_filters_by_segment(client: TestClient) -> None:
    body = client.get("/api/customers", params={"segment": "declining"}).json()

    assert body["total"] == 1
    assert [i["customer_id"] for i in body["items"]] == ["CUST-002"]


def test_list_customers_rejects_bad_query(client: TestClient) -> None:
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"segment": "vip"}):
        response = client.get("/api/customers", params=params)
        assert response.status_code == 422, params
        error = ErrorResponse.model_validate(response.json()).error
        assert error.code == "validation_error"
        assert error.details["errors"]


def test_list_customers_empty_database(empty_client: TestClient) -> None:
    assert empty_client.get("/api/customers").json() == {"items": [], "total": 0}


def test_get_customer_returns_profile(client: TestClient) -> None:
    response = client.get("/api/customers/CUST-003")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == set(CustomerProfile.model_fields)
    assert body["amount_due"] == "2000.00"  # money is a decimal string
    assert body["due_date"] == "2026-01-03"
    assert body["bill_status"] == "overdue"
    assert body["consent_marketing"] is False
    profile = CustomerProfile.model_validate(body)
    assert profile.days_overdue == 12


def test_get_customer_keeps_nulls_and_contradictions(client: TestClient) -> None:
    """Contradictory billing data is stored as-is so policy can block it."""
    body = client.get("/api/customers/CUST-004").json()

    assert body["bill_status"] == "paid"
    assert body["days_overdue"] == 4
    assert body["due_date"] is None
    assert (
        client.get("/api/customers/CUST-002").json()["last_contacted_days_ago"] is None
    )


def test_get_customer_has_no_email_field(client: TestClient) -> None:
    body = client.get("/api/customers/CUST-001").json()

    assert not any("mail" in key for key in body)
    assert "@" not in response_text(client, "/api/customers/CUST-001")


def test_get_unknown_customer_is_404_with_error_shape(client: TestClient) -> None:
    response = client.get("/api/customers/CUST-999")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "customer_not_found",
            "message": "Customer not found.",
            "details": {},
        }
    }


def response_text(client: TestClient, path: str) -> str:
    return client.get(path).text
