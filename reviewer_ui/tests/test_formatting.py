"""Presentation helpers: copy API values, never derive facts; escape untrusted text."""

from __future__ import annotations

from reviewer_ui.formatting import (
    approve_unavailable_reason,
    audit_rows,
    blocking_findings,
    customer_option_label,
    escape_markdown,
    finding_rows,
    offer_check_rows,
    rubric_payload,
    to_text,
)


def test_escape_markdown_neutralises_markup_and_html() -> None:
    raw = "Sam <b>ignore</b> [link](http://x) **bold**"
    escaped = escape_markdown(raw)
    assert "<b>" not in escaped
    assert "\\<b\\>" in escaped
    assert "\\[link\\]" in escaped
    assert "\\*\\*bold\\*\\*" in escaped


def test_to_text_handles_json_values() -> None:
    assert to_text(None) == ""
    assert to_text({"b": 1, "a": "x"}) == '{"a": "x", "b": 1}'
    assert to_text(["a"]) == '["a"]'
    assert to_text(0.5) == "0.5"


def test_customer_label_uses_api_segment() -> None:
    summary = {"customer_id": "CUST-001", "first_name": "Asha", "primary_segment": None}
    assert customer_option_label(summary) == "CUST-001 | Asha | no segment"


def test_findings_blocking_first() -> None:
    validation = {
        "passed": False,
        "findings": [
            {"code": "unsupported_claim", "severity": "warning", "message": "w"},
            {"code": "blocked_term", "severity": "blocking", "message": "b"},
        ],
    }
    rows = finding_rows(validation)
    assert [r["code"] for r in rows] == ["blocked_term", "unsupported_claim"]
    assert [f["code"] for f in blocking_findings(validation)] == ["blocked_term"]
    assert finding_rows(None) == []


def test_offer_check_rows_copy_failed_rules() -> None:
    decision = {
        "offer_checks": [
            {
                "offer_id": "REENGAGE-20",
                "eligible": False,
                "failed_rules": ["min_tenure"],
            }
        ]
    }
    assert offer_check_rows(decision) == [
        {"offer_id": "REENGAGE-20", "eligible": "no", "failed_rules": "min_tenure"}
    ]


def test_rubric_payload_optional() -> None:
    scores = {
        "relevance": 5,
        "clarity": 4,
        "personalisation": 3,
        "call_to_action": 2,
        "tone": 1,
    }
    assert rubric_payload(False, scores) is None
    assert rubric_payload(True, scores) == scores


def test_approve_unavailable_reason_explains_from_api_fields() -> None:
    policy_blocked = {
        "status": "blocked",
        "validation": None,
        "decision": {"block_reasons": ["no_marketing_consent"]},
    }
    assert "no_marketing_consent" in approve_unavailable_reason(policy_blocked)
    failed = {"status": "blocked", "validation": {"passed": False}, "decision": {}}
    assert "Validation failed" in approve_unavailable_reason(failed)
    done = {"status": "delivered", "validation": {"passed": True}, "decision": {}}
    assert "delivered" in approve_unavailable_reason(done)


def test_audit_rows_flatten_details() -> None:
    rows = audit_rows([{"event_type": "policy_decided", "details": {"status": "x"}}])
    assert rows[0]["event_type"] == "policy_decided"
    assert rows[0]["details"] == '{"status": "x"}'
