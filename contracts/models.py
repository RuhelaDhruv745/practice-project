"""Canonical data models (docs/DATA_DICTIONARY.md is the prose version).

Architect-owned. Every module imports these; nobody redefines them. Change only by PR
with architect approval and a matching DATA_DICTIONARY.md / API_CONTRACTS.md update.

Design rules encoded here:
- CustomerProfile holds permitted fields only; unknown fields are rejected (FR-01).
- VerifiedFacts is the ONLY thing the LLM sees (FR-06). It is built by policy_engine.
- DraftContent is the ONLY thing the LLM returns: subject and body.
- AuditEvent refuses email addresses anywhere in its details (FR-09).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from contracts.enums import (
    AuditEventType,
    BillStatus,
    BlockReason,
    Channel,
    DecisionStatus,
    FindingCode,
    MessageStatus,
    OfferUnit,
    ReviewAction,
    SegmentName,
    Severity,
)

CUSTOMER_ID_PATTERN = r"^CUST-\d{3,6}$"
CustomerId = Annotated[str, Field(pattern=CUSTOMER_ID_PATTERN)]
Score = Annotated[float, Field(ge=0, le=100)]
Confidence = Annotated[float, Field(ge=0, le=1)]
RubricScore = Annotated[int, Field(ge=1, le=5)]
Primitive = str | int | float | bool | None

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class Contract(BaseModel):
    """Base for all contracts: unknown fields are an error, instances are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# --- FR-01 customer profile --------------------------------------------------


class CustomerProfile(Contract):
    """Minimal permitted profile. No email, age, gender, location or similar fields.

    ``first_name`` is customer-supplied text: treat it as data, never instructions.
    Billing consistency is NOT enforced here: contradictory records must reach the
    policy engine so it can block them with a reason (CONTRADICTORY_BILLING_DATA).
    """

    customer_id: CustomerId
    first_name: str = Field(min_length=1, max_length=60)
    consent_marketing: bool
    plan: str = Field(min_length=1, max_length=40)
    months_active: int = Field(ge=0)
    activity_score_30d: Score
    activity_score_prev_30d: Score
    on_time_payments_12m: int = Field(ge=0, le=12)
    bill_status: BillStatus
    days_overdue: int = Field(ge=0)
    amount_due: Decimal = Field(ge=0, decimal_places=2)
    due_date: date | None
    last_contacted_days_ago: int | None = Field(default=None, ge=0)


# --- FR-02 classification ----------------------------------------------------


class ReasonCode(Contract):
    """Why a segment was assigned, with the evidence fields and values used."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    description: str = Field(min_length=1)
    evidence: dict[str, Primitive]


class SegmentAssignment(Contract):
    segment: SegmentName
    confidence: Confidence
    reasons: list[ReasonCode] = Field(min_length=1)


class ClassificationResult(Contract):
    customer_id: CustomerId
    as_of_date: date
    segments: list[SegmentAssignment]
    primary_segment: SegmentName | None
    policy_versions: dict[str, str]

    @model_validator(mode="after")
    def _primary_is_assigned(self) -> ClassificationResult:
        assigned = {s.segment for s in self.segments}
        if self.primary_segment is None and assigned:
            raise ValueError("primary_segment is required when segments are assigned")
        if self.primary_segment is not None and self.primary_segment not in assigned:
            raise ValueError("primary_segment must be one of the assigned segments")
        return self


# --- FR-03/04/05 strategy, offers, reminders ---------------------------------


class Strategy(Contract):
    segment: SegmentName
    objective: str
    tone: str
    tone_guidance: str
    offer_allowed: bool


class OfferSnapshot(Contract):
    """An offer that passed every eligibility check, exactly as configured."""

    offer_id: str = Field(pattern=r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
    description: str
    value: Decimal = Field(gt=0)
    unit: OfferUnit
    expiry: date
    channel: Channel


class OfferCheck(Contract):
    """Eligibility result for one configured offer, eligible or not (explainability)."""

    offer_id: str
    eligible: bool
    failed_rules: list[str] = Field(default_factory=list)


class ReminderFacts(Contract):
    stage: str
    days_overdue: int = Field(ge=1)
    amount_due: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    due_date: date
    support_path: str = Field(min_length=10)


class VerifiedFacts(Contract):
    """Everything the LLM may use, and nothing else. Built only by policy_engine."""

    customer_id: CustomerId
    first_name: str
    plan: str
    segment: SegmentName
    objective: str
    tone: str
    tone_guidance: str
    offer: OfferSnapshot | None = None
    reminder: ReminderFacts | None = None


class PolicyDecision(Contract):
    """Deterministic gate result. Facts exist only when drafting is allowed."""

    customer_id: CustomerId
    status: DecisionStatus
    block_reasons: list[BlockReason] = Field(default_factory=list)
    classification: ClassificationResult
    strategy: Strategy | None = None
    offer_checks: list[OfferCheck] = Field(default_factory=list)
    facts: VerifiedFacts | None = None

    @model_validator(mode="after")
    def _status_consistent(self) -> PolicyDecision:
        if self.status is DecisionStatus.BLOCKED:
            if not self.block_reasons:
                raise ValueError("a blocked decision needs at least one block reason")
            if self.facts is not None:
                raise ValueError("a blocked decision must not carry facts for drafting")
        else:
            if self.block_reasons:
                raise ValueError("an allowed decision must not carry block reasons")
            if self.facts is None or self.strategy is None:
                raise ValueError(
                    "an allowed decision needs a strategy and verified facts"
                )
        return self


# --- FR-06 generation --------------------------------------------------------


class DraftContent(Contract):
    """The LLM's structured output: subject and body, nothing else."""

    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=4000)


class GeneratedMessage(Contract):
    message_id: str
    customer_id: CustomerId
    draft: DraftContent
    source: Literal["llm", "reviewer_edit"] = "llm"
    provider: str
    model: str
    prompt_version: str
    generated_at: datetime


# --- FR-07 validation --------------------------------------------------------


class ValidationFinding(Contract):
    code: FindingCode
    severity: Severity
    message: str
    evidence: dict[str, Primitive] = Field(default_factory=dict)


class ValidationResult(Contract):
    passed: bool
    findings: list[ValidationFinding] = Field(default_factory=list)
    checks_run: list[FindingCode]
    validator_version: str

    @model_validator(mode="after")
    def _passed_means_no_blocking_findings(self) -> ValidationResult:
        blocking = any(f.severity is Severity.BLOCKING for f in self.findings)
        if self.passed == blocking:
            raise ValueError(
                "passed must be true exactly when there is no blocking finding"
            )
        return self


# --- FR-08 human review ------------------------------------------------------


class ReviewRubric(Contract):
    relevance: RubricScore
    clarity: RubricScore
    personalisation: RubricScore
    call_to_action: RubricScore
    tone: RubricScore


class ReviewDecision(Contract):
    review_id: str
    action: ReviewAction
    reviewer_id: str = Field(pattern=r"^[a-z0-9-]{3,40}$")
    comment: str | None = Field(default=None, max_length=1000)
    rubric: ReviewRubric | None = None
    decided_at: datetime

    @model_validator(mode="after")
    def _reject_needs_reason(self) -> ReviewDecision:
        if self.action is ReviewAction.REJECT and not (self.comment or "").strip():
            raise ValueError("a rejection needs a reason in comment")
        return self


class ReviewItem(Contract):
    review_id: str
    customer_id: CustomerId
    status: MessageStatus
    revision: int = Field(ge=1)
    decision: PolicyDecision
    message: GeneratedMessage | None
    validation: ValidationResult | None
    decisions: list[ReviewDecision] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- FR-09 audit, FR-10 delivery ---------------------------------------------


class AuditEvent(Contract):
    """Append-only audit record. Never contains an email address."""

    event_id: str
    event_type: AuditEventType
    occurred_at: datetime
    actor: str
    customer_id: CustomerId | None = None
    review_id: str | None = None
    message_id: str | None = None
    policy_versions: dict[str, str] = Field(default_factory=dict)
    prompt_version: str | None = None
    model: str | None = None
    details: dict[str, Primitive | list[Primitive]] = Field(default_factory=dict)

    @field_validator("actor")
    @classmethod
    def _actor_not_email(cls, actor: str) -> str:
        if _EMAIL_RE.search(actor):
            raise ValueError(
                "audit actor must be a pseudonymous id, not an email address"
            )
        return actor

    @field_validator("details")
    @classmethod
    def _no_email_addresses(cls, details: dict) -> dict:
        for key, value in details.items():
            values = value if isinstance(value, list) else [value]
            if any(isinstance(v, str) and _EMAIL_RE.search(v) for v in values):
                raise ValueError(f"audit detail {key!r} contains an email address")
        return details


class OutboxRecord(Contract):
    """A mock delivery. Written only for an approved item whose validation passed."""

    message_id: str
    review_id: str
    customer_id: CustomerId
    channel: Channel
    subject: str
    body: str
    approved_by: str
    delivered_at: datetime


# --- API errors --------------------------------------------------------------


class ErrorDetail(Contract):
    code: str
    message: str
    details: dict[str, Primitive | list[Primitive]] = Field(default_factory=dict)


class ErrorResponse(Contract):
    error: ErrorDetail
