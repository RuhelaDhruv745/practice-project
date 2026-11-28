"""The visual approve/edit/reject guards. The backend stays the only real gate."""

from __future__ import annotations

from typing import Any

import pytest

from reviewer_ui.guards import can_approve, can_edit, can_reject


def review(
    status: str = "pending_review",
    passed: bool | None = True,
    decision_status: str = "draft_allowed",
    has_message: bool = True,
) -> dict[str, Any]:
    return {
        "review_id": "REV-0001",
        "status": status,
        "decision": {"status": decision_status},
        "message": {"draft": {"subject": "s", "body": "b"}} if has_message else None,
        "validation": None if passed is None else {"passed": passed, "findings": []},
    }


def test_pending_and_passed_can_be_approved() -> None:
    assert can_approve(review()) is True


@pytest.mark.parametrize(
    "item",
    [
        review(
            status="blocked", passed=None, decision_status="blocked", has_message=False
        ),
        review(status="blocked", passed=False),
        review(status="pending_review", passed=False),
        review(status="pending_review", passed=None),
        review(status="pending_review", decision_status="blocked"),
        review(status="delivered"),
        review(status="approved"),
        review(status="rejected"),
    ],
    ids=[
        "policy-blocked",
        "validation-blocked",
        "pending-but-failed",
        "pending-no-validation",
        "decision-blocked",
        "delivered",
        "approved",
        "rejected",
    ],
)
def test_everything_else_cannot_be_approved(item: dict[str, Any]) -> None:
    assert can_approve(item) is False


@pytest.mark.parametrize("bad", [None, {}, [], "pending_review"])
def test_malformed_input_cannot_be_approved(bad: Any) -> None:
    assert can_approve(bad) is False


def test_passed_must_be_literally_true() -> None:
    item = review()
    item["validation"]["passed"] = "true"
    assert can_approve(item) is False


def test_edit_needs_a_draft_and_an_open_item() -> None:
    assert can_edit(review()) is True
    assert can_edit(review(status="blocked", passed=False)) is True
    assert can_edit(review(status="blocked", passed=None, has_message=False)) is False
    assert can_edit(review(status="delivered")) is False
    assert can_edit(review(status="rejected")) is False
    assert can_edit(None) is False


def test_reject_only_while_open() -> None:
    assert can_reject(review()) is True
    assert can_reject(review(status="blocked", passed=None, has_message=False)) is True
    for status in ("approved", "rejected", "delivered"):
        assert can_reject(review(status=status)) is False
    assert can_reject(None) is False
