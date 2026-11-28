"""FastAPI dependencies: injected collaborators live on ``app.state``."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.core.settings import Settings
from contracts.interfaces import DraftGenerator, PolicyEngine


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_policy_engine(request: Request) -> PolicyEngine:
    return request.app.state.policy_engine


def get_generator(request: Request) -> DraftGenerator:
    return request.app.state.generator


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_policy_versions(request: Request) -> dict[str, str]:
    return request.app.state.policy_versions
