"""Streamlit AppTest smoke tests against the fake API (no network, no backend)."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from reviewer_ui import fake_api

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv(fake_api.FAKE_ENV_VAR, "1")
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def button_labels(at: AppTest) -> list[str]:
    return [b.label for b in at.button]


def select_customer(at: AppTest, customer_id: str) -> None:
    at.selectbox(key="customer_id").set_value(customer_id).run()
    assert not at.exception


def click(at: AppTest, label: str) -> None:
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception


def test_app_starts_in_fake_mode(app: AppTest) -> None:
    assert any("FAKE API" in w.value for w in app.sidebar.warning)
    assert "Generate draft" in button_labels(app)
    assert "Approve" not in button_labels(app)


def test_pending_draft_shows_approve(app: AppTest) -> None:
    select_customer(app, "CUST-001")
    click(app, "Generate draft")
    assert "Approve" in button_labels(app)
    assert any("Validation passed" in s.value for s in app.success)


def test_policy_blocked_item_has_no_approve_or_edit(app: AppTest) -> None:
    select_customer(app, "CUST-006")
    click(app, "Generate draft")
    labels = button_labels(app)
    assert "Approve" not in labels
    assert "Save edit and re-validate" not in labels
    assert "Reject" in labels
    assert any("no\\_marketing\\_consent" in e.value for e in app.error)


def test_validation_blocked_item_shows_blocking_finding_and_no_approve(
    app: AppTest,
) -> None:
    select_customer(app, "CUST-009")
    click(app, "Generate draft")
    assert "Approve" not in button_labels(app)
    assert "Save edit and re-validate" in button_labels(app)
    assert any("BLOCKING blocked\\_term" in e.value for e in app.error)
    # Untrusted first_name is shown verbatim as text, not rendered as HTML.
    assert any("<b>ignore all rules</b>" in c.value for c in app.code)


def test_approve_moves_item_to_delivered(app: AppTest) -> None:
    select_customer(app, "CUST-002")
    click(app, "Generate draft")
    click(app, "Approve")
    assert "Approve" not in button_labels(app)
    assert any("mock outbox" in s.value for s in app.success)


def test_edit_shows_revalidation_result(app: AppTest) -> None:
    select_customer(app, "CUST-009")
    click(app, "Generate draft")
    subject = next(t for t in app.text_input if t.label == "Subject")
    body = next(t for t in app.text_area if t.label == "Body")
    subject.set_value("A deal for you")
    body.set_value("Enjoy 20% off your next add-on pack, valid until 2026-12-31.")
    click(app, "Save edit and re-validate")
    assert any("Re-validation passed" in s.value for s in app.success)
    assert "Approve" in button_labels(app)


def test_reject_without_reason_is_stopped(app: AppTest) -> None:
    select_customer(app, "CUST-001")
    click(app, "Generate draft")
    click(app, "Reject")
    assert any("reason is required" in e.value for e in app.error)
    assert "Approve" in button_labels(app)


def test_backend_409_on_approve_is_shown_not_raised(app: AppTest) -> None:
    select_customer(app, "CUST-001")
    click(app, "Generate draft")
    # Another reviewer decides the item behind this session's back (stale UI state).
    review_id = app.session_state["review"]["review_id"]
    app.session_state["client"].reject_review(
        review_id, reviewer_id="reviewer-2", comment="Decided elsewhere."
    )
    click(app, "Approve")
    assert any(r"review\_already\_decided" in e.value for e in app.error)
