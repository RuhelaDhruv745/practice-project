"""Canonical enumerations shared by every module. Architect-owned: change only by PR
with architect approval, and update docs/DATA_DICTIONARY.md in the same PR."""

from __future__ import annotations

from enum import StrEnum


class SegmentName(StrEnum):
    """Segments are rule-based; the rules live in policy_engine, thresholds in YAML."""

    CONSISTENT = "consistent"
    LOYALTY_CANDIDATE = "loyalty_candidate"
    DECLINING = "declining"
    DORMANT = "dormant"
    PAYMENT_REMINDER = "payment_reminder"


class BillStatus(StrEnum):
    PAID = "paid"
    DUE = "due"
    OVERDUE = "overdue"


class OfferUnit(StrEnum):
    PERCENT = "percent"
    INR = "inr"
    GB = "gb"


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"


class DecisionStatus(StrEnum):
    """Outcome of the deterministic policy gate, before any LLM call."""

    DRAFT_ALLOWED = "draft_allowed"
    BLOCKED = "blocked"


class BlockReason(StrEnum):
    """Why outreach was refused. Every blocked decision carries at least one."""

    NO_MARKETING_CONSENT = "no_marketing_consent"
    CONTACTED_TOO_RECENTLY = "contacted_too_recently"
    CONTRADICTORY_BILLING_DATA = "contradictory_billing_data"
    MISSING_EVIDENCE = "missing_evidence"
    NO_ACTIONABLE_SEGMENT = "no_actionable_segment"


class FindingCode(StrEnum):
    """Validator check identifiers (FR-07). A blocking finding blocks the draft."""

    SCHEMA_INVALID = "schema_invalid"
    AMOUNT_MISMATCH = "amount_mismatch"
    DATE_MISMATCH = "date_mismatch"
    UNKNOWN_OFFER = "unknown_offer"
    INELIGIBLE_OFFER = "ineligible_offer"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    BLOCKED_TERM = "blocked_term"
    MISSING_SUPPORT_PATH = "missing_support_path"
    CONSENT_GAP = "consent_gap"
    DUPLICATE_OUTREACH = "duplicate_outreach"
    SENSITIVE_DATA = "sensitive_data"


class Severity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"


class MessageStatus(StrEnum):
    """Lifecycle of a review item. Only PENDING_REVIEW can be approved.

    The mock-delivery flow never stores APPROVED: approve moves straight to DELIVERED
    in one transaction. APPROVED is reserved for a future draft-only delivery mode.
    """

    BLOCKED = "blocked"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DELIVERED = "delivered"


class ReviewAction(StrEnum):
    EDIT = "edit"
    APPROVE = "approve"
    REJECT = "reject"


class AuditEventType(StrEnum):
    PROFILE_ASSEMBLED = "profile_assembled"
    CLASSIFIED = "classified"
    POLICY_DECIDED = "policy_decided"
    OUTREACH_BLOCKED = "outreach_blocked"
    DRAFT_GENERATED = "draft_generated"
    GENERATION_FAILED = "generation_failed"
    DRAFT_VALIDATED = "draft_validated"
    REVIEW_EDITED = "review_edited"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    MESSAGE_DELIVERED = "message_delivered"
    DELIVERY_REFUSED = "delivery_refused"
