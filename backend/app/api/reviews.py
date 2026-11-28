"""Review endpoints: list, edit, approve, reject (state machine in services.reviews)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_policy_engine, get_session, get_settings
from backend.app.core.settings import Settings
from backend.app.services.reviews import ReviewService
from contracts.api import (
    ApproveRequest,
    ApproveResponse,
    EditReviewRequest,
    Page,
    RejectRequest,
)
from contracts.enums import MessageStatus
from contracts.interfaces import PolicyEngine
from contracts.models import ErrorResponse, ReviewItem

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

_ERRORS = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _service(
    session: Annotated[Session, Depends(get_session)],
    engine: Annotated[PolicyEngine, Depends(get_policy_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReviewService:
    return ReviewService(session, engine, Path(settings.outbox_path))


Service = Annotated[ReviewService, Depends(_service)]


@router.get(
    "/pending",
    response_model=Page[ReviewItem],
    responses={422: {"model": ErrorResponse}},
)
def list_pending(
    service: Service,
    status: Annotated[Literal["pending_review", "blocked"], Query()] = (
        "pending_review"
    ),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ReviewItem]:
    items, total = service.list(MessageStatus(status), limit, offset)
    return Page[ReviewItem](items=items, total=total)


@router.patch("/{review_id}", response_model=ReviewItem, responses=_ERRORS)
def edit_review(
    review_id: str, body: EditReviewRequest, service: Service
) -> ReviewItem:
    return service.edit(review_id, body)


@router.post("/{review_id}/approve", response_model=ApproveResponse, responses=_ERRORS)
def approve_review(
    review_id: str, body: ApproveRequest, service: Service
) -> ApproveResponse:
    review, outbox = service.approve(review_id, body)
    return ApproveResponse(review=review, outbox=outbox)


@router.post("/{review_id}/reject", response_model=ReviewItem, responses=_ERRORS)
def reject_review(review_id: str, body: RejectRequest, service: Service) -> ReviewItem:
    return service.reject(review_id, body)
