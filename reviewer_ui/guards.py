"""Visual guards for reviewer actions.

These only decide which buttons the UI shows. They are a second, cosmetic line of
defence: the backend is the only gate and re-validates before delivery, so a ``409``
from the API is still possible and is handled by the UI. Nothing here computes a
segment, an amount or a validation result; it reads fields the backend returned.
"""

from __future__ import annotations

from typing import Any

PENDING_REVIEW = "pending_review"
BLOCKED = "blocked"
DRAFT_ALLOWED = "draft_allowed"
DECIDED_STATUSES = frozenset({"approved", "rejected", "delivered"})


def can_approve(review: dict[str, Any] | None) -> bool:
    """Show Approve only for a pending item whose latest validation passed.

    A blocked item (by policy or by validation) never gets an Approve button.
    """
    if not isinstance(review, dict):
        return False
    if review.get("status") != PENDING_REVIEW:
        return False
    validation = review.get("validation")
    if not isinstance(validation, dict) or validation.get("passed") is not True:
        return False
    decision = review.get("decision")
    return isinstance(decision, dict) and decision.get("status") == DRAFT_ALLOWED


def can_edit(review: dict[str, Any] | None) -> bool:
    """Show the editor only when there is a draft and the item is not decided.

    An item blocked by policy has no message, so there is nothing to edit.
    """
    if not isinstance(review, dict):
        return False
    return review.get("status") in {PENDING_REVIEW, BLOCKED} and isinstance(
        review.get("message"), dict
    )


def can_reject(review: dict[str, Any] | None) -> bool:
    """Show Reject while the item is still open (pending or blocked)."""
    if not isinstance(review, dict):
        return False
    return review.get("status") in {PENDING_REVIEW, BLOCKED}
