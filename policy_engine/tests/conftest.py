"""Shared fixtures: the real policy, an engine, and a synthetic profile factory.

Profiles are built in code (Member 5's CSV is not merged yet). The default profile is
a plain ``consistent`` customer with a paid bill and marketing consent.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from contracts.models import CustomerProfile
from policy_engine.config_loader import DEFAULT_CONFIG_DIR, Policy, load_policy
from policy_engine.engine import RuleBasedPolicyEngine

ProfileFactory = Callable[..., CustomerProfile]
PolicyFactory = Callable[[Callable[[dict[str, dict[str, Any]]], None]], Policy]

BASE_PROFILE: dict[str, Any] = {
    "customer_id": "CUST-001",
    "first_name": "Asha",
    "consent_marketing": True,
    "plan": "Unlimited 499",
    "months_active": 12,
    "activity_score_30d": 50.0,
    "activity_score_prev_30d": 50.0,
    "on_time_payments_12m": 12,
    "bill_status": "paid",
    "days_overdue": 0,
    "amount_due": Decimal("0.00"),
    "due_date": None,
    "last_contacted_days_ago": None,
}

AS_OF = date(2026, 11, 28)


@pytest.fixture(scope="session")
def policy() -> Policy:
    return load_policy()


@pytest.fixture(scope="session")
def engine(policy: Policy) -> RuleBasedPolicyEngine:
    return RuleBasedPolicyEngine(policy)


@pytest.fixture
def make_profile() -> ProfileFactory:
    def factory(**overrides: Any) -> CustomerProfile:
        return CustomerProfile(**{**BASE_PROFILE, **overrides})

    return factory


@pytest.fixture
def overdue() -> dict[str, Any]:
    """Overrides for a consistent overdue bill, 5 days past due."""
    return {
        "bill_status": "overdue",
        "days_overdue": 5,
        "amount_due": Decimal("2000.00"),
        "due_date": date(2026, 11, 23),
        "on_time_payments_12m": 9,
    }


@pytest.fixture
def policy_with(tmp_path: Path) -> PolicyFactory:
    """Load a copy of the real policy files after applying ``mutate`` to them."""

    def factory(mutate: Callable[[dict[str, dict[str, Any]]], None]) -> Policy:
        files = {
            path.stem: yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in DEFAULT_CONFIG_DIR.glob("*.yaml")
        }
        mutate(files)
        for name, data in files.items():
            (tmp_path / f"{name}.yaml").write_text(
                yaml.safe_dump(data), encoding="utf-8"
            )
        return load_policy(tmp_path)

    return factory
