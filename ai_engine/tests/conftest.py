from __future__ import annotations

import pytest

from ai_engine.tests import factories
from contracts.models import VerifiedFacts


@pytest.fixture(autouse=True)
def _no_dev_cache_or_live_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never use the dev cache or a live provider, whatever the shell has set."""
    for name in ("LLM_CACHE", "LLM_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")


@pytest.fixture
def thanks_facts() -> VerifiedFacts:
    return factories.make_facts()


@pytest.fixture
def reward_facts() -> VerifiedFacts:
    return factories.reward_facts()


@pytest.fixture
def reminder_facts() -> VerifiedFacts:
    return factories.reminder_facts()
