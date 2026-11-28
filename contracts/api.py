"""HTTP request and response bodies for docs/API_CONTRACTS.md. Architect-owned.

Member 1 uses these in FastAPI routes; Member 4 generates TypeScript types from the
resulting OpenAPI schema. Canonical domain models live in contracts.models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from contracts.enums import BillStatus, SegmentName
from contracts.models import (
    Contract,
    CustomerId,
    DraftContent,
    OutboxRecord,
    ReviewItem,
    ReviewRubric,
)

ReviewerId = str
_REVIEWER_ID = Field(pattern=r"^[a-z0-9-]{3,40}$")


class Page[T](Contract):
    items: list[T]
    total: int = Field(ge=0)


class HealthResponse(Contract):
    status: Literal["ok"]
    version: str
    policy_versions: dict[str, str]
    llm_provider: str
    llm_mode: Literal["live", "mock"]


class CustomerSummary(Contract):
    customer_id: CustomerId
    first_name: str
    plan: str
    bill_status: BillStatus
    consent_marketing: bool
    primary_segment: SegmentName | None


class CustomerRequest(Contract):
    """Body of POST /api/classification/evaluate and POST /api/messages/generate."""

    customer_id: CustomerId


class ValidateRequest(Contract):
    customer_id: CustomerId
    draft: DraftContent


class EditReviewRequest(Contract):
    reviewer_id: ReviewerId = _REVIEWER_ID
    draft: DraftContent
    comment: str | None = Field(default=None, max_length=1000)


class ApproveRequest(Contract):
    reviewer_id: ReviewerId = _REVIEWER_ID
    comment: str | None = Field(default=None, max_length=1000)
    rubric: ReviewRubric | None = None


class RejectRequest(Contract):
    reviewer_id: ReviewerId = _REVIEWER_ID
    comment: str = Field(min_length=1, max_length=1000)
    rubric: ReviewRubric | None = None

    @model_validator(mode="after")
    def _comment_not_blank(self) -> RejectRequest:
        if not self.comment.strip():
            raise ValueError("a rejection needs a reason in comment")
        return self


class ApproveResponse(Contract):
    review: ReviewItem
    outbox: OutboxRecord
