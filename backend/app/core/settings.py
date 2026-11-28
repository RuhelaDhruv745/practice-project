"""Backend settings read from environment variables.

Settings come from the process environment only; this module never opens the local
secrets file (pass it to uvicorn with ``--env-file`` instead). API keys are never
stored here: only whether one is configured, so ``/api/health`` can report
``llm_mode`` without any way to leak the key.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

DEFAULT_DATABASE_URL = "sqlite:///outputs/app.db"
DEFAULT_LLM_PROVIDER = "anthropic"

# Provider name -> environment variable holding its API key ("mock" needs none).
_PROVIDER_KEY_VARS: dict[str, str | None] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "mock": None,
}


class SettingsError(ValueError):
    """Raised when an environment variable has an invalid value."""


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_key_configured: bool = False
    cors_origins: tuple[str, ...] = field(default_factory=tuple)
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.llm_provider not in _PROVIDER_KEY_VARS:
            allowed = ", ".join(sorted(_PROVIDER_KEY_VARS))
            raise SettingsError(f"LLM_PROVIDER must be one of: {allowed}")

    @property
    def llm_mode(self) -> Literal["live", "mock"]:
        """``mock`` when the provider is mock or no API key is configured."""
        if self.llm_provider == "mock" or not self.llm_key_configured:
            return "mock"
        return "live"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ
        provider = (env.get("LLM_PROVIDER") or DEFAULT_LLM_PROVIDER).strip().lower()
        key_var = _PROVIDER_KEY_VARS.get(provider)
        key_configured = bool(key_var and (env.get(key_var) or "").strip())
        origins = tuple(
            o.strip() for o in (env.get("CORS_ORIGINS") or "").split(",") if o.strip()
        )
        return cls(
            database_url=(env.get("DATABASE_URL") or DEFAULT_DATABASE_URL).strip(),
            llm_provider=provider,
            llm_key_configured=key_configured,
            cors_origins=origins,
            log_level=(env.get("LOG_LEVEL") or "INFO").strip().upper(),
        )
