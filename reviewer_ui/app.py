"""Streamlit reviewer app (PS deliverable #1).

Run from the repo root: ``python -m streamlit run reviewer_ui/app.py``.
Set ``API_BASE_URL`` for the backend (default ``http://localhost:8000``) or
``REVIEWER_UI_FAKE_API=1`` to use the in-memory fake until the backend merges.

Thin client: it shows what the API returns and sends reviewer actions. It computes no
segment, eligibility, amount, date or validation result. Customer and draft text is
always rendered as plain text (``st.code`` / tables / escaped markdown), never HTML.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# `streamlit run reviewer_ui/app.py` puts reviewer_ui/ on sys.path, not the repo root.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import streamlit as st  # noqa: E402

from reviewer_ui import fake_api  # noqa: E402
from reviewer_ui.api_client import ApiClient, ApiError  # noqa: E402
from reviewer_ui.formatting import (  # noqa: E402
    RUBRIC_FIELDS,
    approve_unavailable_reason,
    audit_rows,
    blocking_findings,
    customer_option_label,
    decision_rows,
    escape_markdown,
    finding_rows,
    offer_check_rows,
    profile_rows,
    reason_rows,
    rubric_payload,
)
from reviewer_ui.guards import can_approve, can_edit, can_reject  # noqa: E402

AUDIT_EVENT_TYPES = (
    "",
    "profile_assembled",
    "classified",
    "policy_decided",
    "outreach_blocked",
    "draft_generated",
    "generation_failed",
    "draft_validated",
    "review_edited",
    "review_approved",
    "review_rejected",
    "message_delivered",
    "delivery_refused",
)
QUEUE_STATUSES = ("pending_review", "blocked")


# --- session helpers -------------------------------------------------------------


def get_client() -> ApiClient:
    """One client per browser session; the fake keeps its state per session."""
    if "client" not in st.session_state:
        if fake_api.fake_enabled():
            st.session_state.client = ApiClient(
                fake_api.FAKE_BASE_URL, transport=fake_api.make_transport()
            )
        else:
            st.session_state.client = ApiClient()
    return st.session_state.client


def show_api_error(error: ApiError) -> None:
    status = f"HTTP {error.status}" if error.status else "no response"
    st.error(
        f"{escape_markdown(error.code)} ({status}): {escape_markdown(error.message)}"
    )
    if error.details:
        with st.expander("Error details"):
            st.json(error.details)


def call_api(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run one API call; show ``error.code`` / ``error.message`` instead of raising."""
    try:
        return func(*args, **kwargs)
    except ApiError as error:
        show_api_error(error)
        return None


def flash(kind: str, text: str) -> None:
    st.session_state.flash = (kind, text)


def show_flash() -> None:
    message = st.session_state.pop("flash", None)
    if message:
        kind, text = message
        getattr(st, kind)(text)


def plain(label: str, value: Any) -> None:
    """A label plus untrusted text shown verbatim."""
    st.caption(label)
    st.code("" if value is None else str(value), language=None, wrap_lines=True)


# --- panels -------------------------------------------------------------------------


def render_decision(decision: dict[str, Any]) -> None:
    classification = decision.get("classification") or {}
    if decision.get("status") == "blocked":
        reasons = ", ".join(decision.get("block_reasons") or [])
        st.error(f"Policy decision: blocked ({escape_markdown(reasons)})")
    else:
        st.success("Policy decision: draft allowed")

    cols = st.columns(3)
    cols[0].metric("Primary segment", classification.get("primary_segment") or "none")
    cols[1].metric("As of", str(classification.get("as_of_date") or ""))
    cols[2].metric("Segments matched", len(classification.get("segments") or []))

    st.markdown("**Segments, reason codes and evidence**")
    segments = classification.get("segments") or []
    if not segments:
        st.info("No segment matched.")
    for assignment in segments:
        st.markdown(
            f"`{escape_markdown(assignment.get('segment'))}` "
            f"confidence {escape_markdown(assignment.get('confidence'))}"
        )
        st.dataframe(reason_rows(assignment), hide_index=True)

    strategy = decision.get("strategy")
    st.markdown("**Strategy**")
    if strategy:
        st.dataframe(profile_rows(strategy), hide_index=True)
    else:
        st.info("No strategy.")

    st.markdown("**Offer checks**")
    checks = offer_check_rows(decision)
    if checks:
        st.dataframe(checks, hide_index=True)
    else:
        st.info("No offers were checked.")

    facts = decision.get("facts") or {}
    if facts.get("offer"):
        st.markdown("**Eligible offer (verified)**")
        st.dataframe(profile_rows(facts["offer"]), hide_index=True)
    if facts.get("reminder"):
        st.markdown("**Reminder stage (verified)**")
        st.dataframe(profile_rows(facts["reminder"]), hide_index=True)
    # Plain caption + collapsed JSON: render_decision runs inside an expander and
    # Streamlit does not allow nested expanders.
    st.caption("Policy versions")
    st.json(classification.get("policy_versions") or {}, expanded=False)


def render_validation(review: dict[str, Any]) -> None:
    validation = review.get("validation")
    st.markdown("**Validation**")
    if validation is None:
        st.info("No validation: there is no draft for this item.")
        return
    if validation.get("passed"):
        st.success("Validation passed")
    else:
        st.error("Validation failed")
    for finding in blocking_findings(validation):
        st.error(
            f"BLOCKING {escape_markdown(finding.get('code'))}: "
            f"{escape_markdown(finding.get('message'))}"
        )
    rows = finding_rows(validation)
    if rows:
        st.dataframe(rows, hide_index=True)
    st.caption(f"Validator {escape_markdown(validation.get('validator_version'))}")


def render_review(review: dict[str, Any]) -> None:
    show_flash()
    st.subheader(f"Review {review.get('review_id')}")
    cols = st.columns(3)
    cols[0].metric("Status", str(review.get("status")))
    cols[1].metric("Revision", str(review.get("revision")))
    cols[2].metric("Customer", str(review.get("customer_id")))

    message = review.get("message")
    if message:
        draft = message.get("draft") or {}
        plain("Subject", draft.get("subject"))
        plain("Body", draft.get("body"))
        st.caption(
            "Source: "
            + escape_markdown(
                f"{message.get('source')} / {message.get('provider')} / "
                f"{message.get('model')} / prompt {message.get('prompt_version')}"
            )
        )
    else:
        st.warning("No draft was generated: the item is blocked by policy.")

    render_validation(review)
    with st.expander("Evidence, segment and strategy", expanded=message is None):
        render_decision(review.get("decision") or {})

    history = decision_rows(review)
    if history:
        st.markdown("**Reviewer actions**")
        st.dataframe(history, hide_index=True)

    render_actions(review)


def render_actions(review: dict[str, Any]) -> None:
    client = get_client()
    review_id = str(review.get("review_id"))
    reviewer_id = st.session_state.get("reviewer_id", "reviewer-1")

    st.markdown("**Actions**")
    if can_approve(review):
        with st.form(f"approve-{review_id}"):
            st.write("Approve and deliver to the mock outbox")
            use_rubric = st.checkbox("Add 1-5 rubric scores")
            scores = {
                name: st.slider(name.replace("_", " "), 1, 5, 3)
                for name in RUBRIC_FIELDS
            }
            comment = st.text_input(
                "Comment (optional)", key=f"approve-comment-{review_id}"
            )
            if st.form_submit_button("Approve", type="primary"):
                result = call_api(
                    client.approve_review,
                    review_id,
                    reviewer_id=reviewer_id,
                    comment=comment or None,
                    rubric=rubric_payload(use_rubric, scores),
                )
                if result is not None:
                    st.session_state.review = result["review"]
                    st.session_state.outbox = result["outbox"]
                    flash("success", "Approved and written to the mock outbox.")
                    st.rerun()
                else:
                    st.info(
                        "Nothing was delivered. The backend is the approval gate; "
                        "this item's state may have changed, so reload it from the "
                        "review queue."
                    )
    else:
        st.info(
            f"Approve unavailable: {escape_markdown(approve_unavailable_reason(review))}"
        )

    if can_edit(review):
        draft = (review.get("message") or {}).get("draft") or {}
        with st.form(f"edit-{review_id}-{review.get('revision')}"):
            st.write("Edit draft (the API re-validates it)")
            subject = st.text_input(
                "Subject", value=draft.get("subject", ""), max_chars=150
            )
            body = st.text_area(
                "Body", value=draft.get("body", ""), height=220, max_chars=4000
            )
            comment = st.text_input("Edit comment (optional)")
            if st.form_submit_button("Save edit and re-validate"):
                updated = call_api(
                    client.edit_review,
                    review_id,
                    reviewer_id=reviewer_id,
                    subject=subject,
                    body=body,
                    comment=comment or None,
                )
                if updated is not None:
                    st.session_state.review = updated
                    passed = (updated.get("validation") or {}).get("passed")
                    if passed:
                        flash("success", "Edit saved. Re-validation passed.")
                    else:
                        flash(
                            "error", "Edit saved. Re-validation failed; see findings."
                        )
                    st.rerun()

    if can_reject(review):
        with st.form(f"reject-{review_id}"):
            st.write("Reject")
            reason = st.text_area("Reason (required)", max_chars=1000)
            use_rubric = st.checkbox(
                "Add 1-5 rubric scores", key=f"reject-rubric-{review_id}"
            )
            scores = {
                name: st.slider(
                    name.replace("_", " "), 1, 5, 3, key=f"reject-{name}-{review_id}"
                )
                for name in RUBRIC_FIELDS
            }
            if st.form_submit_button("Reject"):
                if not reason.strip():
                    st.error("A reason is required to reject.")
                else:
                    updated = call_api(
                        client.reject_review,
                        review_id,
                        reviewer_id=reviewer_id,
                        comment=reason,
                        rubric=rubric_payload(use_rubric, scores),
                    )
                    if updated is not None:
                        st.session_state.review = updated
                        flash("success", "Rejected.")
                        st.rerun()

    outbox = st.session_state.get("outbox")
    if outbox and outbox.get("review_id") == review_id:
        with st.expander("Mock outbox record", expanded=True):
            plain("Subject", outbox.get("subject"))
            plain("Body", outbox.get("body"))
            st.caption(
                escape_markdown(
                    f"Approved by {outbox.get('approved_by')} at {outbox.get('delivered_at')}"
                )
            )


# --- pages ----------------------------------------------------------------------------


def page_customer() -> None:
    client = get_client()
    st.header("Review a customer")
    page = call_api(client.list_customers, limit=100)
    if page is None:
        return
    customers = page.get("items") or []
    if not customers:
        st.info("No customers returned by the API.")
        return
    labels = {c["customer_id"]: customer_option_label(c) for c in customers}
    customer_id = st.selectbox(
        "Customer", list(labels), format_func=lambda cid: labels[cid], key="customer_id"
    )
    if st.session_state.get("loaded_customer") != customer_id:
        st.session_state.loaded_customer = customer_id
        for key in ("decision", "review", "outbox"):
            st.session_state.pop(key, None)

    profile = call_api(client.get_customer, customer_id)
    if profile is not None:
        with st.expander("Customer profile (permitted fields only)"):
            st.dataframe(profile_rows(profile), hide_index=True)

    cols = st.columns(2)
    if cols[0].button("Evaluate"):
        decision = call_api(client.evaluate, customer_id)
        if decision is not None:
            st.session_state.decision = decision
    if cols[1].button("Generate draft", type="primary"):
        review = call_api(client.generate, customer_id)
        if review is not None:
            st.session_state.review = review
            st.session_state.pop("outbox", None)

    if st.session_state.get("decision"):
        with st.expander("Evaluation", expanded=not st.session_state.get("review")):
            render_decision(st.session_state.decision)
    review = st.session_state.get("review")
    if review:
        render_review(review)


def page_queue() -> None:
    client = get_client()
    st.header("Review queue")
    status = st.selectbox("Status", QUEUE_STATUSES)
    page = call_api(client.list_reviews, status=status, limit=100)
    if page is None:
        return
    items = page.get("items") or []
    st.caption(f"{page.get('total', len(items))} item(s)")
    if not items:
        st.info("Nothing in this queue.")
        return
    by_id = {item["review_id"]: item for item in items}
    review_id = st.selectbox(
        "Review item",
        list(by_id),
        format_func=lambda rid: f"{rid} | {by_id[rid].get('customer_id')}",
    )
    current = st.session_state.get("review")
    if not current or current.get("review_id") != review_id:
        st.session_state.review = by_id[review_id]
    render_review(st.session_state.review)


def page_audit() -> None:
    client = get_client()
    st.header("Audit trail")
    cols = st.columns(3)
    customer_id = cols[0].text_input("Customer ID")
    review_id = cols[1].text_input("Review ID")
    event_type = cols[2].selectbox("Event type", AUDIT_EVENT_TYPES)
    page = call_api(
        client.list_audit,
        customer_id=customer_id.strip() or None,
        review_id=review_id.strip() or None,
        event_type=event_type or None,
        limit=500,
    )
    if page is None:
        return
    events = page.get("items") or []
    st.caption(f"{page.get('total', len(events))} event(s), newest first")
    if events:
        st.dataframe(audit_rows(events), hide_index=True)
    else:
        st.info("No audit events match.")


def sidebar() -> str:
    client = get_client()
    st.sidebar.title("Reviewer")
    if fake_api.fake_enabled():
        st.sidebar.warning("FAKE API mode: canned synthetic data, nothing is real.")
    st.sidebar.caption(f"API: {escape_markdown(client.base_url)}")
    health = call_api(client.health)
    if health is not None:
        st.sidebar.caption(
            escape_markdown(
                f"Backend {health.get('version')}, LLM {health.get('llm_provider')} "
                f"({health.get('llm_mode')})"
            )
        )
    st.sidebar.text_input(
        "Reviewer ID (pseudonymous)", value="reviewer-1", key="reviewer_id"
    )
    return st.sidebar.radio("Page", ("Customer", "Review queue", "Audit trail"))


def main() -> None:
    st.set_page_config(page_title="Reviewer", layout="wide")
    page = sidebar()
    if page == "Customer":
        page_customer()
    elif page == "Review queue":
        page_queue()
    else:
        page_audit()


if __name__ == "__main__":
    main()
