"""Pure presentation helpers for the reviewer app.

They reshape API JSON into rows and labels for display. They never derive a business
fact: every value shown is copied from what the backend returned.
"""

from __future__ import annotations

import json
import re
from typing import Any

from reviewer_ui.guards import PENDING_REVIEW

RUBRIC_FIELDS = ("relevance", "clarity", "personalisation", "call_to_action", "tone")

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")


def escape_markdown(text: Any) -> str:
    """Escape untrusted text before it goes into a markdown-rendering widget.

    Customer and API text must render as text, never as markup or HTML.
    """
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(text))


def to_text(value: Any) -> str:
    """Render any JSON value as a plain string for table cells."""
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def customer_option_label(summary: dict[str, Any]) -> str:
    segment = summary.get("primary_segment") or "no segment"
    return f"{summary.get('customer_id')} | {summary.get('first_name')} | {segment}"


def profile_rows(profile: dict[str, Any]) -> list[dict[str, str]]:
    return [{"field": key, "value": to_text(value)} for key, value in profile.items()]


def reason_rows(assignment: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "code": to_text(reason.get("code")),
            "description": to_text(reason.get("description")),
            "evidence": to_text(reason.get("evidence")),
        }
        for reason in assignment.get("reasons") or []
    ]


def offer_check_rows(decision: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "offer_id": to_text(check.get("offer_id")),
            "eligible": "yes" if check.get("eligible") else "no",
            "failed_rules": ", ".join(check.get("failed_rules") or []),
        }
        for check in decision.get("offer_checks") or []
    ]


def finding_rows(validation: dict[str, Any] | None) -> list[dict[str, str]]:
    """Findings with blocking ones first so they are seen before warnings."""
    findings = (validation or {}).get("findings") or []
    ordered = sorted(findings, key=lambda f: f.get("severity") != "blocking")
    return [
        {
            "severity": to_text(f.get("severity")),
            "code": to_text(f.get("code")),
            "message": to_text(f.get("message")),
            "evidence": to_text(f.get("evidence")),
        }
        for f in ordered
    ]


def blocking_findings(validation: dict[str, Any] | None) -> list[dict[str, Any]]:
    findings = (validation or {}).get("findings") or []
    return [f for f in findings if f.get("severity") == "blocking"]


def approve_unavailable_reason(review: dict[str, Any]) -> str:
    """Explain, from the backend's own fields, why Approve is not offered."""
    status = review.get("status")
    validation = review.get("validation")
    decision = review.get("decision") or {}
    if status == "blocked" and validation is None:
        reasons = ", ".join(decision.get("block_reasons") or []) or "unspecified"
        return f"Blocked by policy ({reasons}). There is no draft to approve."
    if status == "blocked":
        return (
            "Validation failed. Edit the draft to fix blocking findings, or reject it."
        )
    if status != PENDING_REVIEW:
        return f"This item is already {status}."
    if not (validation or {}).get("passed"):
        return "The latest validation did not pass."
    return "The policy decision does not allow a draft."


def rubric_payload(enabled: bool, scores: dict[str, int]) -> dict[str, int] | None:
    """The optional 1-5 rubric, or ``None`` when the reviewer did not score."""
    if not enabled:
        return None
    return {name: int(scores[name]) for name in RUBRIC_FIELDS}


def decision_rows(review: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "decided_at": to_text(d.get("decided_at")),
            "action": to_text(d.get("action")),
            "reviewer_id": to_text(d.get("reviewer_id")),
            "comment": to_text(d.get("comment")),
            "rubric": to_text(d.get("rubric")),
        }
        for d in review.get("decisions") or []
    ]


def audit_rows(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "occurred_at": to_text(e.get("occurred_at")),
            "event_type": to_text(e.get("event_type")),
            "actor": to_text(e.get("actor")),
            "customer_id": to_text(e.get("customer_id")),
            "review_id": to_text(e.get("review_id")),
            "message_id": to_text(e.get("message_id")),
            "prompt_version": to_text(e.get("prompt_version")),
            "model": to_text(e.get("model")),
            "details": to_text(e.get("details")),
        }
        for e in events
    ]
