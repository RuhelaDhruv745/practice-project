"""GET /api/health. Reports llm_mode without revealing keys."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from backend.app import __version__
from backend.app.api.deps import get_generator, get_policy_versions, get_settings
from backend.app.core.settings import Settings
from contracts.api import HealthResponse
from contracts.interfaces import DraftGenerator

router = APIRouter(prefix="/api", tags=["health"])


def _llm_mode(generator: DraftGenerator, settings: Settings) -> Literal["live", "mock"]:
    """Prefer the generator's own view (it knows whether it fell back to the mock);
    fall back to settings for generators without a ``mode`` attribute."""
    mode = getattr(generator, "mode", None)
    if mode in ("live", "mock"):
        return mode
    return settings.llm_mode


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Annotated[Settings, Depends(get_settings)],
    policy_versions: Annotated[dict[str, str], Depends(get_policy_versions)],
    generator: Annotated[DraftGenerator, Depends(get_generator)],
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        policy_versions=policy_versions,
        llm_provider=settings.llm_provider,
        llm_mode=_llm_mode(generator, settings),
    )
