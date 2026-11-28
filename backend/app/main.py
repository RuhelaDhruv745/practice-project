"""App factory and module-level ``app`` for ``uvicorn backend.app.main:app``.

``create_app`` takes its collaborators as arguments so tests inject fakes; the real
``PolicyEngine`` / ``DraftGenerator`` are wired here only, for the module-level app.
Configuration comes from the process environment only (pass the local env file to
uvicorn with ``--env-file``); this module never opens it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import __version__
from backend.app.api import audit, customers, health, pipeline, reviews
from backend.app.core.logging import configure_logging
from backend.app.core.settings import Settings
from backend.app.database import create_db_engine, init_db, session_factory
from backend.app.middleware.errors import register_error_handlers
from backend.app.middleware.request_logging import register_request_logging
from contracts.interfaces import DraftGenerator, PolicyEngine


def _load_policy_versions() -> dict[str, str]:
    """Versions of the policy files, read through the validated config loader."""
    from policy_engine.config_loader import load_policy

    return load_policy().versions


def create_app(
    policy_engine: PolicyEngine,
    generator: DraftGenerator,
    settings: Settings,
    *,
    policy_versions: dict[str, str] | None = None,
) -> FastAPI:
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        init_db(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Customer Loyalty and Engagement Assistant API",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.policy_engine = policy_engine
    app.state.generator = generator
    app.state.db_engine = engine
    app.state.session_factory = session_factory(engine)
    app.state.policy_versions = (
        dict(policy_versions)
        if policy_versions is not None
        else _load_policy_versions()
    )

    register_error_handlers(app)
    register_request_logging(app)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type"],
        )

    app.include_router(health.router)
    app.include_router(customers.router)
    app.include_router(pipeline.router)
    app.include_router(reviews.router)
    app.include_router(audit.router)
    return app


def build_default_app() -> FastAPI:
    """Real implementations: rule-based policy engine and the LLM draft generator
    (which uses its mock provider when no API key is configured)."""
    from ai_engine.generation import LLMDraftGenerator
    from policy_engine.engine import RuleBasedPolicyEngine

    return create_app(
        RuleBasedPolicyEngine.from_config_dir(),
        LLMDraftGenerator(),
        Settings.from_env(),
    )


app = build_default_app()
