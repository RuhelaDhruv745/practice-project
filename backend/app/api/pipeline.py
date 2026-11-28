"""POST /api/classification/evaluate, /api/messages/generate, /api/messages/validate."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_generator, get_policy_engine, get_session
from backend.app.services.pipeline import PipelineService
from contracts.api import CustomerRequest, ValidateRequest
from contracts.interfaces import DraftGenerator, PolicyEngine
from contracts.models import (
    ErrorResponse,
    PolicyDecision,
    ReviewItem,
    ValidationResult,
)

router = APIRouter(prefix="/api", tags=["pipeline"])

_ERRORS_404_422 = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _service(
    session: Annotated[Session, Depends(get_session)],
    engine: Annotated[PolicyEngine, Depends(get_policy_engine)],
    generator: Annotated[DraftGenerator, Depends(get_generator)],
) -> PipelineService:
    return PipelineService(session, engine, generator)


Service = Annotated[PipelineService, Depends(_service)]


@router.post(
    "/classification/evaluate",
    response_model=PolicyDecision,
    responses=_ERRORS_404_422,
)
def evaluate(body: CustomerRequest, service: Service) -> PolicyDecision:
    return service.evaluate(body.customer_id)


@router.post(
    "/messages/generate",
    response_model=ReviewItem,
    status_code=201,
    responses={**_ERRORS_404_422, 502: {"model": ErrorResponse}},
)
def generate(body: CustomerRequest, service: Service) -> ReviewItem:
    return service.generate(body.customer_id)


@router.post(
    "/messages/validate",
    response_model=ValidationResult,
    responses=_ERRORS_404_422,
)
def validate(body: ValidateRequest, service: Service) -> ValidationResult:
    return service.validate_draft(body.customer_id, body.draft)
