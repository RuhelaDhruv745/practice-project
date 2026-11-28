"""Review state machine: list, edit, approve, reject (docs/API_CONTRACTS.md)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.settings import Settings
from backend.app.models import GeneratedMessageRow, OutboxRecordRow
from backend.tests.fakes import FakePolicyEngine
from contracts.api import ApproveResponse, Page
from contracts.enums import BlockReason, MessageStatus, ReviewAction
from contracts.models import ReviewItem

EDIT = {
    "reviewer_id": "reviewer-1",
    "draft": {"subject": "Edited subject", "body": "Hi Asha, edited body."},
    "comment": "Tightened wording.",
}
APPROVE = {"reviewer_id": "reviewer-1"}
REJECT = {"reviewer_id": "reviewer-1", "comment": "Tone does not fit."}
RUBRIC = {
    "relevance": 5,
    "clarity": 4,
    "personalisation": 4,
    "call_to_action": 3,
    "tone": 5,
}


def _generate(client: TestClient, customer_id: str = "CUST-001") -> ReviewItem:
    response = client.post("/api/messages/generate", json={"customer_id": customer_id})
    assert response.status_code == 201
    return ReviewItem.model_validate(response.json())


def _error(response) -> tuple[int, str]:  # type: ignore[no-untyped-def]
    return response.status_code, response.json()["error"]["code"]


def _events(client: TestClient, review_id: str) -> list[str]:
    items = client.get("/api/audit", params={"review_id": review_id}).json()["items"]
    return [e["event_type"] for e in reversed(items)]


# --- list --------------------------------------------------------------------


def test_list_pending_and_blocked(
    client: TestClient, policy_engine: FakePolicyEngine
) -> None:
    pending = _generate(client, "CUST-001")
    blocked = _generate(client, "CUST-004")

    default = Page[ReviewItem].model_validate(client.get("/api/reviews/pending").json())
    only_blocked = client.get("/api/reviews/pending", params={"status": "blocked"})

    assert [i.review_id for i in default.items] == [pending.review_id]
    assert default.total == 1
    assert [i["review_id"] for i in only_blocked.json()["items"]] == [blocked.review_id]


def test_list_rejects_other_statuses_and_bad_paging(client: TestClient) -> None:
    for params in ({"status": "delivered"}, {"limit": 0}, {"offset": -1}):
        response = client.get("/api/reviews/pending", params=params)
        assert _error(response) == (422, "validation_error")


# --- edit --------------------------------------------------------------------


def test_edit_revalidates_and_stores_new_revision(
    client: TestClient, policy_engine: FakePolicyEngine
) -> None:
    item = _generate(client)
    calls_before = policy_engine.calls.count(("validate", "CUST-001"))

    response = client.patch(f"/api/reviews/{item.review_id}", json=EDIT)

    assert response.status_code == 200
    edited = ReviewItem.model_validate(response.json())
    assert edited.revision == 2
    assert edited.status is MessageStatus.PENDING_REVIEW
    assert edited.message is not None
    assert edited.message.source == "reviewer_edit"
    assert edited.message.draft.subject == "Edited subject"
    assert edited.message.message_id != item.message.message_id  # type: ignore[union-attr]
    assert [d.action for d in edited.decisions] == [ReviewAction.EDIT]
    assert policy_engine.calls.count(("validate", "CUST-001")) == calls_before + 1
    assert _events(client, item.review_id)[-2:] == ["review_edited", "draft_validated"]
    validated = client.get(
        "/api/audit",
        params={"review_id": item.review_id, "event_type": "draft_validated"},
    ).json()["items"][0]
    assert validated["details"]["message_id"] == edited.message.message_id
    assert validated["details"]["revision"] == 2
    assert validated["actor"] == "reviewer-1"


def test_edit_keeps_every_revision(client: TestClient) -> None:
    item = _generate(client)
    client.patch(f"/api/reviews/{item.review_id}", json=EDIT)

    with client.app.state.session_factory() as session:
        rows = session.scalars(
            select(GeneratedMessageRow).where(
                GeneratedMessageRow.review_id == item.review_id
            )
        ).all()
    assert sorted((r.revision, r.source) for r in rows) == [
        (1, "llm"),
        (2, "reviewer_edit"),
    ]


def test_failing_edit_blocks_and_passing_edit_unblocks(
    client: TestClient, policy_engine: FakePolicyEngine
) -> None:
    item = _generate(client)

    policy_engine.validation_passes = False
    failed = client.patch(f"/api/reviews/{item.review_id}", json=EDIT).json()
    policy_engine.validation_passes = True
    fixed = client.patch(f"/api/reviews/{item.review_id}", json=EDIT).json()

    assert failed["status"] == "blocked"
    assert failed["validation"]["passed"] is False
    assert fixed["status"] == "pending_review"
    assert fixed["revision"] == 3


def test_policy_blocked_item_is_not_editable(client: TestClient) -> None:
    item = _generate(client, "CUST-004")

    response = client.patch(f"/api/reviews/{item.review_id}", json=EDIT)

    assert _error(response) == (409, "review_not_editable")


def test_decided_item_is_not_editable(client: TestClient) -> None:
    item = _generate(client)
    client.post(f"/api/reviews/{item.review_id}/reject", json=REJECT)

    response = client.patch(f"/api/reviews/{item.review_id}", json=EDIT)

    assert _error(response) == (409, "review_not_editable")


def test_edit_unknown_and_invalid(client: TestClient) -> None:
    item = _generate(client)

    assert _error(client.patch("/api/reviews/rev-missing", json=EDIT)) == (
        404,
        "review_not_found",
    )
    bad = client.patch(
        f"/api/reviews/{item.review_id}", json={**EDIT, "reviewer_id": "A@B"}
    )
    assert _error(bad) == (422, "validation_error")


# --- approve -----------------------------------------------------------------


def test_approve_passing_item_delivers_to_mock_outbox(
    client: TestClient, settings: Settings
) -> None:
    item = _generate(client)

    response = client.post(
        f"/api/reviews/{item.review_id}/approve",
        json={**APPROVE, "comment": "Looks good.", "rubric": RUBRIC},
    )

    assert response.status_code == 200
    body = ApproveResponse.model_validate(response.json())
    assert body.review.status is MessageStatus.DELIVERED
    assert [d.action for d in body.review.decisions] == [ReviewAction.APPROVE]
    assert body.review.decisions[0].rubric is not None
    assert body.outbox.review_id == item.review_id
    assert body.outbox.message_id == item.message.message_id  # type: ignore[union-attr]
    assert body.outbox.approved_by == "reviewer-1"
    assert body.outbox.channel.value == "email"
    lines = Path(settings.outbox_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["review_id"] == item.review_id
    with client.app.state.session_factory() as session:
        assert len(session.scalars(select(OutboxRecordRow)).all()) == 1
    assert _events(client, item.review_id)[-3:] == [
        "draft_validated",
        "review_approved",
        "message_delivered",
    ]


def test_approve_twice_is_already_decided(client: TestClient) -> None:
    item = _generate(client)
    client.post(f"/api/reviews/{item.review_id}/approve", json=APPROVE)

    response = client.post(f"/api/reviews/{item.review_id}/approve", json=APPROVE)

    assert _error(response) == (409, "review_already_decided")


def test_approve_policy_blocked_is_409_and_audited(
    client: TestClient, settings: Settings
) -> None:
    item = _generate(client, "CUST-004")

    response = client.post(f"/api/reviews/{item.review_id}/approve", json=APPROVE)

    assert _error(response) == (409, "review_not_approvable")
    assert "decision_blocked" in response.json()["error"]["details"]["reasons"]
    assert _events(client, item.review_id)[-1] == "delivery_refused"
    assert not Path(settings.outbox_path).exists()


def test_approve_after_failing_edit_is_409(
    client: TestClient, policy_engine: FakePolicyEngine, settings: Settings
) -> None:
    item = _generate(client)
    policy_engine.validation_passes = False
    client.patch(f"/api/reviews/{item.review_id}", json=EDIT)

    response = client.post(f"/api/reviews/{item.review_id}/approve", json=APPROVE)

    assert _error(response) == (409, "review_not_approvable")
    details = response.json()["error"]["details"]
    assert details["status"] == "blocked"
    assert details["blocking_findings"] == ["blocked_term"]
    assert _events(client, item.review_id)[-1] == "delivery_refused"
    assert not Path(settings.outbox_path).exists()


def test_approve_revalidates_before_delivery(
    client: TestClient, policy_engine: FakePolicyEngine, settings: Settings
) -> None:
    item = _generate(client)
    policy_engine.validation_passes = False  # stale "passed" state on the item

    response = client.post(f"/api/reviews/{item.review_id}/approve", json=APPROVE)

    assert _error(response) == (409, "review_not_approvable")
    assert response.json()["error"]["details"]["status"] == "blocked"
    stored = client.get("/api/reviews/pending", params={"status": "blocked"}).json()
    assert [i["review_id"] for i in stored["items"]] == [item.review_id]
    assert not Path(settings.outbox_path).exists()


def test_approve_refused_when_policy_now_blocks(
    client: TestClient, policy_engine: FakePolicyEngine, settings: Settings
) -> None:
    item = _generate(client)
    policy_engine.blocked["CUST-001"] = [BlockReason.CONTACTED_TOO_RECENTLY]

    response = client.post(f"/api/reviews/{item.review_id}/approve", json=APPROVE)

    assert _error(response) == (409, "review_not_approvable")
    details = response.json()["error"]["details"]
    assert details["block_reasons"] == ["contacted_too_recently"]
    assert not Path(settings.outbox_path).exists()


def test_approve_unknown_is_404(client: TestClient) -> None:
    response = client.post("/api/reviews/rev-missing/approve", json=APPROVE)

    assert _error(response) == (404, "review_not_found")


# --- reject ------------------------------------------------------------------


def test_reject_requires_reason(client: TestClient) -> None:
    item = _generate(client)
    url = f"/api/reviews/{item.review_id}/reject"

    for body in ({"reviewer_id": "reviewer-1"}, {**REJECT, "comment": "   "}):
        assert _error(client.post(url, json=body)) == (422, "validation_error")
    assert client.get("/api/reviews/pending").json()["total"] == 1


def test_reject_pending_then_decided(client: TestClient) -> None:
    item = _generate(client)
    url = f"/api/reviews/{item.review_id}/reject"

    response = client.post(url, json={**REJECT, "rubric": RUBRIC})

    assert response.status_code == 200
    rejected = ReviewItem.model_validate(response.json())
    assert rejected.status is MessageStatus.REJECTED
    assert rejected.decisions[-1].comment == "Tone does not fit."
    assert _events(client, item.review_id)[-1] == "review_rejected"
    assert _error(client.post(url, json=REJECT)) == (409, "review_already_decided")
    assert _error(
        client.post(f"/api/reviews/{item.review_id}/approve", json=APPROVE)
    ) == (409, "review_already_decided")


def test_reject_blocked_item(client: TestClient) -> None:
    item = _generate(client, "CUST-004")

    response = client.post(f"/api/reviews/{item.review_id}/reject", json=REJECT)

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_reject_unknown_is_404(client: TestClient) -> None:
    response = client.post("/api/reviews/rev-missing/reject", json=REJECT)

    assert _error(response) == (404, "review_not_found")
