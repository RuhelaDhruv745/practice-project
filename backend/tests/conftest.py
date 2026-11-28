"""Shared fixtures: a temp SQLite file per test, seeded from a small fixture CSV."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.seed import seed_customers
from backend.tests.fakes import FakeDraftGenerator, FakePolicyEngine
from contracts.enums import SegmentName

FIXTURES = Path(__file__).parent / "fixtures"
CUSTOMERS_CSV = FIXTURES / "customers_small.csv"
TEST_POLICY_VERSIONS = {"policy": "1.0", "segments": "1.0"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    db_file = tmp_path / "db" / "test.db"
    return Settings(
        database_url=f"sqlite:///{db_file.as_posix()}",
        llm_provider="mock",
        outbox_path=(tmp_path / "outputs" / "outbox.jsonl").as_posix(),
    )


@pytest.fixture
def policy_engine() -> FakePolicyEngine:
    return FakePolicyEngine(
        segments={
            "CUST-001": SegmentName.LOYALTY_CANDIDATE,
            "CUST-002": SegmentName.DECLINING,
            "CUST-003": SegmentName.PAYMENT_REMINDER,
        }
    )


@pytest.fixture
def generator() -> FakeDraftGenerator:
    return FakeDraftGenerator()


@pytest.fixture
def app(
    policy_engine: FakePolicyEngine, generator: FakeDraftGenerator, settings: Settings
) -> FastAPI:
    return create_app(
        policy_engine,
        generator,
        settings,
        policy_versions=TEST_POLICY_VERSIONS,
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:  # runs lifespan: creates the tables
        seed_customers(app.state.session_factory, CUSTOMERS_CSV)
        yield test_client


@pytest.fixture
def empty_client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
