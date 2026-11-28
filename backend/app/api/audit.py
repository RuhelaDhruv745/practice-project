"""GET /api/audit: append-only audit events, newest first."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.repositories import AuditRepository
from contracts.api import Page
from contracts.enums import AuditEventType
from contracts.models import AuditEvent, ErrorResponse

router = APIRouter(prefix="/api", tags=["audit"])


@router.get(
    "/audit",
    response_model=Page[AuditEvent],
    responses={422: {"model": ErrorResponse}},
)
def list_audit(
    session: Annotated[Session, Depends(get_session)],
    customer_id: Annotated[str | None, Query()] = None,
    review_id: Annotated[str | None, Query()] = None,
    event_type: Annotated[AuditEventType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditEvent]:
    items, total = AuditRepository(session).list(
        customer_id=customer_id,
        review_id=review_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return Page[AuditEvent](items=items, total=total)
