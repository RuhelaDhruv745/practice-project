"""GET /api/customers and GET /api/customers/{customer_id}.

``primary_segment`` comes from ``PolicyEngine.classify``; the backend never
computes segments itself.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_policy_engine, get_session
from backend.app.middleware.errors import ApiError
from backend.app.repositories import CustomerRepository
from contracts.api import CustomerSummary, Page
from contracts.enums import SegmentName
from contracts.interfaces import PolicyEngine
from contracts.models import CustomerProfile, ErrorResponse

router = APIRouter(prefix="/api", tags=["customers"])


def _summary(profile: CustomerProfile, engine: PolicyEngine) -> CustomerSummary:
    classification = engine.classify(profile)
    return CustomerSummary(
        customer_id=profile.customer_id,
        first_name=profile.first_name,
        plan=profile.plan,
        bill_status=profile.bill_status,
        consent_marketing=profile.consent_marketing,
        primary_segment=classification.primary_segment,
    )


@router.get(
    "/customers",
    response_model=Page[CustomerSummary],
    responses={422: {"model": ErrorResponse}},
)
def list_customers(
    session: Annotated[Session, Depends(get_session)],
    engine: Annotated[PolicyEngine, Depends(get_policy_engine)],
    segment: Annotated[SegmentName | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CustomerSummary]:
    repo = CustomerRepository(session)
    if segment is None:
        items = [_summary(p, engine) for p in repo.list_profiles(limit, offset)]
        return Page[CustomerSummary](items=items, total=repo.count())
    # Filtering by segment needs the policy engine's classification of every
    # customer; fine at hackathon scale (tens to hundreds of rows).
    matching = [
        s
        for s in (_summary(p, engine) for p in repo.list_profiles())
        if s.primary_segment is segment
    ]
    return Page[CustomerSummary](
        items=matching[offset : offset + limit], total=len(matching)
    )


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerProfile,
    responses={404: {"model": ErrorResponse}},
)
def get_customer(
    customer_id: str, session: Annotated[Session, Depends(get_session)]
) -> CustomerProfile:
    profile = CustomerRepository(session).get_profile(customer_id)
    if profile is None:
        raise ApiError(404, "customer_not_found", "Customer not found.")
    return profile
