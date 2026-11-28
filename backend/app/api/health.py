"""GET /api/health. Reports llm_mode without revealing keys."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app import __version__
from backend.app.api.deps import get_policy_versions, get_settings
from backend.app.core.settings import Settings
from contracts.api import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Annotated[Settings, Depends(get_settings)],
    policy_versions: Annotated[dict[str, str], Depends(get_policy_versions)],
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        policy_versions=policy_versions,
        llm_provider=settings.llm_provider,
        llm_mode=settings.llm_mode,
    )
