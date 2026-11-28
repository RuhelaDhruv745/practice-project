from __future__ import annotations

import pytest

from ai_engine.tests import factories
from contracts.models import VerifiedFacts


@pytest.fixture
def thanks_facts() -> VerifiedFacts:
    return factories.make_facts()


@pytest.fixture
def reward_facts() -> VerifiedFacts:
    return factories.reward_facts()


@pytest.fixture
def reminder_facts() -> VerifiedFacts:
    return factories.reminder_facts()
