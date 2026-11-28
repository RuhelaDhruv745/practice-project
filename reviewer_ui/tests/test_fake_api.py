"""The fake API returns contract-shaped data and follows the review state machine.

Payloads are parsed with the architect's contract models, so a drift from
contracts/ fails here rather than in the demo.
"""

from __future__ import annotations

import pytest

from contracts.api import ApproveResponse, CustomerSummary, HealthResponse, Page
from contracts.models import (
    AuditEvent,
    CustomerProfile,
    ErrorResponse,
    PolicyDecision,
    ReviewItem,
    ValidationResult,
)
from reviewer_ui import fake_api
from reviewer_ui.api_client import ApiClient, ApiError
from reviewer_ui.guards import can_approve

ALL_CUSTOMERS = [f"CUST-{n:03d}" for n in range(1, 11)]


@pytest.fixture
def client() -> ApiClient:
    return ApiClient(fake_api.FAKE_BASE_URL, transport=fake_api.make_transport())


def assert_error(info: pytest.ExceptionInfo[ApiError], status: int, code: str) -> None:
    assert (info.value.status, info.value.code) == (status, code)


def test_fake_enabled_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(fake_api.FAKE_ENV_VAR, raising=False)
    assert fake_api.fake_enabled() is False
    monkeypatch.setenv(fake_api.FAKE_ENV_VAR, "1")
    assert fake_api.fake_enabled() is True
    monkeypatch.setenv(fake_api.FAKE_ENV_VAR, "0")
    assert fake_api.fake_enabled() is False


def test_health_and_customers_match_contract(client: ApiClient) -> None:
    HealthResponse.model_validate(client.health())
    page = Page[CustomerSummary].model_validate(client.list_customers())
    assert [c.customer_id for c in page.items] == ALL_CUSTOMERS
    assert page.total == len(ALL_CUSTOMERS)
    for customer_id in ALL_CUSTOMERS:
        CustomerProfile.model_validate(client.get_customer(customer_id))


def test_customer_filter_by_segment(client: ApiClient) -> None:
    page = client.list_customers(segment="dormant")
    assert [c["customer_id"] for c in page["items"]] == ["CUST-004"]


@pytest.mark.parametrize("customer_id", ALL_CUSTOMERS)
def test_every_decision_and_review_is_contract_valid(
    client: ApiClient, customer_id: str
) -> None:
    PolicyDecision.model_validate(client.evaluate(customer_id))
    ReviewItem.model_validate(client.generate(customer_id))


def test_six_ps_scenarios_are_covered(client: ApiClient) -> None:
    primaries = {
        cid: client.evaluate(cid)["classification"]["primary_segment"]
        for cid in ALL_CUSTOMERS
    }
    for segment in (
        "consistent",
        "loyalty_candidate",
        "declining",
        "dormant",
        "payment_reminder",
    ):
        assert segment in primaries.values()
    blocked = client.evaluate("CUST-006")
    assert blocked["status"] == "blocked"
    assert blocked["block_reasons"] == ["no_marketing_consent"]
    assert client.evaluate("CUST-007")["block_reasons"] == ["contacted_too_recently"]
    reminder = client.evaluate("CUST-005")["facts"]["reminder"]
    assert reminder["stage"] == "courteous"


def test_policy_blocked_generate_has_no_message(client: ApiClient) -> None:
    review = client.generate("CUST-006")
    assert review["status"] == "blocked"
    assert review["message"] is None and review["validation"] is None
    assert can_approve(review) is False


def test_approve_happy_path_writes_outbox_and_audit(client: ApiClient) -> None:
    review = client.generate("CUST-001")
    assert review["status"] == "pending_review" and can_approve(review)
    rubric = dict.fromkeys(
        ("relevance", "clarity", "personalisation", "call_to_action", "tone"), 5
    )
    result = ApproveResponse.model_validate(
        client.approve_review(
            review["review_id"], reviewer_id="reviewer-1", rubric=rubric
        )
    )
    assert result.review.status == "delivered"
    assert result.outbox.approved_by == "reviewer-1"
    with pytest.raises(ApiError) as info:
        client.approve_review(review["review_id"], reviewer_id="reviewer-1")
    assert_error(info, 409, "review_already_decided")
    ErrorResponse.model_validate(
        {
            "error": {
                "code": info.value.code,
                "message": info.value.message,
                "details": info.value.details,
            }
        }
    )
    events = client.list_audit(review_id=review["review_id"])["items"]
    for event in events:
        AuditEvent.model_validate(event)
    types = [e["event_type"] for e in events]
    assert types[0] == "message_delivered"
    assert "review_approved" in types


def test_approving_a_blocked_item_is_refused_with_409(client: ApiClient) -> None:
    review = client.generate("CUST-009")
    assert review["status"] == "blocked"
    assert review["validation"]["passed"] is False
    with pytest.raises(ApiError) as info:
        client.approve_review(review["review_id"], reviewer_id="reviewer-1")
    assert_error(info, 409, "review_not_approvable")
    assert info.value.details["blocking_findings"] == ["blocked_term"]


def test_edit_revalidates_and_can_unblock(client: ApiClient) -> None:
    review = client.generate("CUST-009")
    fixed = client.edit_review(
        review["review_id"],
        reviewer_id="reviewer-1",
        subject="A deal for you",
        body="Enjoy 20% off your next add-on pack, valid until 2026-12-31.",
    )
    ReviewItem.model_validate(fixed)
    assert fixed["status"] == "pending_review"
    assert fixed["revision"] == 2
    assert fixed["message"]["source"] == "reviewer_edit"
    assert fixed["decisions"][-1]["action"] == "edit"
    broken = client.edit_review(
        review["review_id"],
        reviewer_id="reviewer-1",
        subject="Guaranteed savings",
        body="b",
    )
    assert broken["status"] == "blocked" and broken["revision"] == 3
    assert can_approve(broken) is False


def test_policy_blocked_item_cannot_be_edited(client: ApiClient) -> None:
    review = client.generate("CUST-007")
    with pytest.raises(ApiError) as info:
        client.edit_review(
            review["review_id"], reviewer_id="reviewer-1", subject="s", body="b"
        )
    assert_error(info, 409, "review_not_editable")


def test_reject_needs_reason_and_closes_item(client: ApiClient) -> None:
    review = client.generate("CUST-002")
    with pytest.raises(ApiError) as info:
        client.reject_review(review["review_id"], reviewer_id="reviewer-1", comment=" ")
    assert_error(info, 422, "validation_error")
    rejected = client.reject_review(
        review["review_id"], reviewer_id="reviewer-1", comment="Tone too salesy."
    )
    assert ReviewItem.model_validate(rejected).status == "rejected"
    with pytest.raises(ApiError) as info:
        client.edit_review(
            review["review_id"], reviewer_id="reviewer-1", subject="s", body="b"
        )
    assert_error(info, 409, "review_not_editable")


def test_queue_lists_by_status(client: ApiClient) -> None:
    client.generate("CUST-001")
    client.generate("CUST-006")
    pending = client.list_reviews()
    blocked = client.list_reviews(status="blocked")
    assert [r["customer_id"] for r in pending["items"]] == ["CUST-001"]
    assert [r["customer_id"] for r in blocked["items"]] == ["CUST-006"]


def test_validate_dry_run(client: ApiClient) -> None:
    ok = ValidationResult.model_validate(client.validate("CUST-001", "Hi", "Thanks"))
    assert ok.passed is True
    blocked = client.validate("CUST-006", "Hi", "Thanks")
    assert blocked["passed"] is False
    assert blocked["findings"][0]["code"] == "consent_gap"


def test_unknown_ids_are_404(client: ApiClient) -> None:
    with pytest.raises(ApiError) as info:
        client.get_customer("CUST-999")
    assert_error(info, 404, "customer_not_found")
    with pytest.raises(ApiError) as info:
        client.reject_review("REV-9999", reviewer_id="reviewer-1", comment="x")
    assert_error(info, 404, "review_not_found")


def test_fake_data_has_no_email_addresses(client: ApiClient) -> None:
    for customer_id in ALL_CUSTOMERS:
        client.generate(customer_id)
    dump = str(client.list_customers()) + str(client.list_audit(limit=500))
    assert "@" not in dump
