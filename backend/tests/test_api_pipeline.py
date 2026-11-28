"""POST /api/classification/evaluate, /api/messages/generate, /api/messages/validate."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.seed import seed_customers
from backend.tests.conftest import CUSTOMERS_CSV
from backend.tests.fakes import (
    FailingDraftGenerator,
    FakeDraftGenerator,
    FakePolicyEngine,
)
from contracts.api import Page
from contracts.enums import BlockReason, DecisionStatus, MessageStatus, SegmentName
from contracts.models import (
    AuditEvent,
    ErrorResponse,
    PolicyDecision,
    ReviewItem,
    ValidationResult,
)

DRAFT = {"subject": "Thanks for staying", "body": "Hi Asha, thank you."}


def _audit_types(client: TestClient, **params: str) -> list[str]:
    page = Page[AuditEvent].model_validate(
        client.get("/api/audit", params={"limit": 500, **params}).json()
    )
    return [e.event_type.value for e in reversed(page.items)]  # oldest first


# --- evaluate ----------------------------------------------------------------


def test_evaluate_returns_decision_without_llm_or_review(
    client: TestClient, generator: FakeDraftGenerator
) -> None:
    response = client.post(
        "/api/classification/evaluate", json={"customer_id": "CUST-001"}
    )

    assert response.status_code == 200
    decision = PolicyDecision.model_validate(response.json())
    assert decision.status is DecisionStatus.DRAFT_ALLOWED
    assert decision.classification.primary_segment is SegmentName.LOYALTY_CANDIDATE
    assert generator.calls == []
    assert client.get("/api/reviews/pending").json()["total"] == 0
    assert _audit_types(client, customer_id="CUST-001") == [
        "profile_assembled",
        "classified",
        "policy_decided",
    ]


def test_evaluate_unknown_customer_is_404(client: TestClient) -> None:
    response = client.post(
        "/api/classification/evaluate", json={"customer_id": "CUST-999"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


def test_evaluate_bad_body_is_422(client: TestClient) -> None:
    response = client.post("/api/classification/evaluate", json={"customer_id": "x"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- generate ----------------------------------------------------------------


def test_generate_passing_draft_is_pending_review(
    client: TestClient, generator: FakeDraftGenerator
) -> None:
    response = client.post("/api/messages/generate", json={"customer_id": "CUST-001"})

    assert response.status_code == 201
    item = ReviewItem.model_validate(response.json())
    assert item.status is MessageStatus.PENDING_REVIEW
    assert item.revision == 1
    assert item.message is not None and item.message.source == "llm"
    assert item.validation is not None and item.validation.passed
    assert len(generator.calls) == 1
    assert _audit_types(client, customer_id="CUST-001") == [
        "profile_assembled",
        "classified",
        "policy_decided",
        "draft_generated",
        "draft_validated",
    ]
    validated = client.get(
        "/api/audit", params={"event_type": "draft_validated"}
    ).json()["items"][0]
    assert validated["review_id"] == item.review_id
    assert validated["message_id"] == item.message.message_id
    assert validated["prompt_version"] == "fake-prompt-1"
    assert validated["model"] == "fake-model"
    assert validated["policy_versions"] == {"policy": "test", "segments": "test"}


def test_policy_blocked_creates_blocked_item_without_message(
    client: TestClient,
    policy_engine: FakePolicyEngine,
    generator: FakeDraftGenerator,
) -> None:
    policy_engine.blocked["CUST-003"] = [BlockReason.NO_MARKETING_CONSENT]

    response = client.post("/api/messages/generate", json={"customer_id": "CUST-003"})

    assert response.status_code == 201
    item = ReviewItem.model_validate(response.json())
    assert item.status is MessageStatus.BLOCKED
    assert item.message is None
    assert item.validation is None
    assert item.decision.block_reasons == [BlockReason.NO_MARKETING_CONSENT]
    assert generator.calls == []
    assert _audit_types(client, customer_id="CUST-003")[-1] == "outreach_blocked"
    assert "draft_generated" not in _audit_types(client, customer_id="CUST-003")


def test_no_segment_is_blocked_not_an_error(client: TestClient) -> None:
    response = client.post("/api/messages/generate", json={"customer_id": "CUST-004"})

    assert response.status_code == 201
    assert response.json()["status"] == "blocked"
    assert response.json()["decision"]["block_reasons"] == ["no_actionable_segment"]


def test_failing_validation_creates_blocked_item_with_message(
    client: TestClient, policy_engine: FakePolicyEngine
) -> None:
    policy_engine.validation_passes = False

    response = client.post("/api/messages/generate", json={"customer_id": "CUST-002"})

    assert response.status_code == 201
    item = ReviewItem.model_validate(response.json())
    assert item.status is MessageStatus.BLOCKED
    assert item.message is not None
    assert item.validation is not None and not item.validation.passed


def test_generate_unknown_customer_is_404(client: TestClient) -> None:
    response = client.post("/api/messages/generate", json={"customer_id": "CUST-999"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


def test_generation_failure_is_502_and_creates_no_item(settings: Settings) -> None:
    engine = FakePolicyEngine(segments={"CUST-001": SegmentName.LOYALTY_CANDIDATE})
    app = create_app(engine, FailingDraftGenerator(), settings, policy_versions={})
    with TestClient(app) as client:
        seed_customers(app.state.session_factory, CUSTOMERS_CSV)
        response = client.post(
            "/api/messages/generate", json={"customer_id": "CUST-001"}
        )

        assert response.status_code == 502
        error = ErrorResponse.model_validate(response.json()).error
        assert error.code == "generation_failed"
        assert "fake provider failure" not in response.text
        for status in ("pending_review", "blocked"):
            listed = client.get("/api/reviews/pending", params={"status": status})
            assert listed.json()["total"] == 0
        failed = client.get(
            "/api/audit", params={"event_type": "generation_failed"}
        ).json()
        assert failed["total"] == 1
        assert failed["items"][0]["review_id"] is None
        assert "fake provider failure" not in str(failed)


def test_generator_only_receives_verified_facts(
    client: TestClient, generator: FakeDraftGenerator
) -> None:
    client.post("/api/messages/generate", json={"customer_id": "CUST-001"})

    facts = generator.calls[0]
    assert type(facts).__name__ == "VerifiedFacts"
    assert not hasattr(facts, "consent_marketing")


# --- validate (dry run) ------------------------------------------------------


def test_validate_dry_run_changes_nothing(client: TestClient) -> None:
    before = client.get("/api/audit").json()["total"]

    response = client.post(
        "/api/messages/validate", json={"customer_id": "CUST-001", "draft": DRAFT}
    )

    assert response.status_code == 200
    assert ValidationResult.model_validate(response.json()).passed
    assert client.get("/api/audit").json()["total"] == before
    assert client.get("/api/reviews/pending").json()["total"] == 0


def test_validate_for_blocked_decision_fails(
    client: TestClient, policy_engine: FakePolicyEngine
) -> None:
    policy_engine.blocked["CUST-001"] = [BlockReason.NO_MARKETING_CONSENT]

    response = client.post(
        "/api/messages/validate", json={"customer_id": "CUST-001", "draft": DRAFT}
    )

    result = ValidationResult.model_validate(response.json())
    assert response.status_code == 200
    assert not result.passed
    assert [f.code.value for f in result.findings] == ["consent_gap"]


def test_validate_errors(client: TestClient) -> None:
    missing = client.post(
        "/api/messages/validate", json={"customer_id": "CUST-999", "draft": DRAFT}
    )
    bad = client.post(
        "/api/messages/validate",
        json={"customer_id": "CUST-001", "draft": {"subject": "", "body": "x"}},
    )

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "customer_not_found"
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"
