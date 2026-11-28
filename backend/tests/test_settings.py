from __future__ import annotations

import pytest

from backend.app.core.settings import DEFAULT_DATABASE_URL, Settings, SettingsError


def test_defaults() -> None:
    settings = Settings.from_env({})

    assert settings.database_url == DEFAULT_DATABASE_URL == "sqlite:///outputs/app.db"
    assert settings.llm_provider == "anthropic"
    assert settings.llm_mode == "mock"  # no key configured


@pytest.mark.parametrize(
    ("env", "mode"),
    [
        ({"LLM_PROVIDER": "mock", "ANTHROPIC_API_KEY": "x"}, "mock"),
        ({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "x"}, "live"),
        ({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "  "}, "mock"),
        ({"LLM_PROVIDER": "groq", "ANTHROPIC_API_KEY": "x"}, "mock"),
        ({"LLM_PROVIDER": "GROQ", "GROQ_API_KEY": "x"}, "live"),
    ],
)
def test_llm_mode(env: dict[str, str], mode: str) -> None:
    assert Settings.from_env(env).llm_mode == mode


def test_unknown_provider_fails_loudly() -> None:
    with pytest.raises(SettingsError):
        Settings.from_env({"LLM_PROVIDER": "openai"})


def test_cors_origins_parsed() -> None:
    settings = Settings.from_env({"CORS_ORIGINS": "http://a:1, http://b:2,"})

    assert settings.cors_origins == ("http://a:1", "http://b:2")
