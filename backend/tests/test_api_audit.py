"""GET /api/audit and the audit trail's privacy guarantees."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.repositories import AuditRepository
from contracts.api import Page
from contracts.enums import AuditEventType
from contracts.models import AuditEvent


def _run_full_workflow(client: TestClient) -> str:
    review_id = client.post(
        "/api/messages/generate", json={"customer_id": "CUST-001"}
    ).json()["review_id"]
    client.patch(
        f"/api/reviews/{review_id}",
        json={
            "reviewer_id": "reviewer-1",
            "draft": {"subject": "Hello", "body": "Write to someone@example.com"},
            "comment": "cc reviewer@example.com",
        },
    )
    client.post(
        f"/api/reviews/{review_id}/approve",
        json={"reviewer_id": "reviewer-2", "comment": "ok boss@example.com"},
    )
    client.post("/api/messages/generate", json={"customer_id": "CUST-004"})
    return review_id


def test_audit_is_newest_first_and_filterable(client: TestClient) -> None:
    review_id = _run_full_workflow(client)

    everything = Page[AuditEvent].model_validate(
        client.get("/api/audit", params={"limit": 500}).json()
    )
    times = [e.occurred_at for e in everything.items]
    assert times == sorted(times, reverse=True)
    assert everything.total == len(everything.items)

    by_review = client.get("/api/audit", params={"review_id": review_id}).json()
    assert {e["review_id"] for e in by_review["items"]} == {review_id}
    by_customer = client.get("/api/audit", params={"customer_id": "CUST-004"}).json()
    assert {e["customer_id"] for e in by_customer["items"]} == {"CUST-004"}
    by_type = client.get("/api/audit", params={"event_type": "message_delivered"})
    assert by_type.json()["total"] == 1

    page = client.get("/api/audit", params={"limit": 2, "offset": 1}).json()
    assert len(page["items"]) == 2
    assert page["items"][0]["event_id"] == everything.items[1].event_id


def test_audit_contains_no_email_addresses(client: TestClient) -> None:
    _run_full_workflow(client)

    response = client.get("/api/audit", params={"limit": 500})

    assert response.json()["total"] > 0
    assert "@" not in response.text


def test_audit_query_validation(client: TestClient) -> None:
    for params in ({"limit": 0}, {"limit": 501}, {"event_type": "nope"}):
        response = client.get("/api/audit", params=params)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_audit_event_contract_rejects_emails_before_storage() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(
            event_id="evt-1",
            event_type=AuditEventType.REVIEW_EDITED,
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
            actor="reviewer-1",
            details={"note": "someone@example.com"},
        )


def test_audit_repository_is_append_only() -> None:
    public = {name for name in dir(AuditRepository) if not name.startswith("_")}

    assert public == {"append", "list"}
