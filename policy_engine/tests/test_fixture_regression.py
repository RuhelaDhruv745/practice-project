"""Regression against Member 5's labelled fixtures and Member 2's mock drafts.

- every row of ``data/fixtures/scenarios.jsonl`` through ``decide``;
- every case of ``data/fixtures/bad_drafts.jsonl`` reports at least its expected
  finding codes, all blocking;
- the offline ``MockProvider`` draft for every ``draft_allowed`` customer passes
  ``validate`` (the end-to-end happy path the demo relies on).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from contracts.enums import DecisionStatus, Severity
from contracts.models import CustomerProfile, DraftContent
from policy_engine.config_loader import DEFAULT_CONFIG_DIR

ROOT = DEFAULT_CONFIG_DIR.parent.parent
CUSTOMERS_CSV = ROOT / "data" / "synthetic" / "customers.csv"
SCENARIOS = ROOT / "data" / "fixtures" / "scenarios.jsonl"
BAD_DRAFTS = ROOT / "data" / "fixtures" / "bad_drafts.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _load_customers() -> dict[str, CustomerProfile]:
    profiles: dict[str, CustomerProfile] = {}
    with CUSTOMERS_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            data: dict[str, Any] = {k: (v if v != "" else None) for k, v in row.items()}
            data["consent_marketing"] = {"true": True, "false": False}[
                data["consent_marketing"]
            ]
            profiles[data["customer_id"]] = CustomerProfile(**data)
    return profiles


CUSTOMERS = _load_customers()
SCENARIO_ROWS = _read_jsonl(SCENARIOS)
BAD_DRAFT_ROWS = _read_jsonl(BAD_DRAFTS)
ALLOWED_IDS = [
    row["customer_id"]
    for row in SCENARIO_ROWS
    if row["expected_status"] == DecisionStatus.DRAFT_ALLOWED
]


def test_every_customer_has_a_scenario() -> None:
    assert {row["customer_id"] for row in SCENARIO_ROWS} == set(CUSTOMERS)
    assert len(BAD_DRAFT_ROWS) >= 14


@pytest.mark.parametrize("row", SCENARIO_ROWS, ids=lambda r: r["customer_id"])
def test_scenario_decision_matches_label(engine, row) -> None:
    decision = engine.decide(CUSTOMERS[row["customer_id"]])
    facts = decision.facts

    assert decision.classification.primary_segment == row["expected_primary_segment"]
    assert decision.status == row["expected_status"]
    assert sorted(decision.block_reasons) == sorted(row["expected_block_reasons"])
    stage = facts.reminder.stage if facts and facts.reminder else None
    offer_id = facts.offer.offer_id if facts and facts.offer else None
    assert stage == row["expected_reminder_stage"]
    assert offer_id == row["expected_offer_id"]


@pytest.mark.parametrize("case", BAD_DRAFT_ROWS, ids=lambda c: c["case_id"])
def test_bad_draft_is_blocked_with_expected_codes(engine, case) -> None:
    decision = engine.decide(CUSTOMERS[case["customer_id"]])
    result = engine.validate(DraftContent(**case["draft"]), decision)

    blocking = {f.code for f in result.findings if f.severity is Severity.BLOCKING}
    assert not result.passed
    assert set(case["expected_finding_codes"]) <= blocking, result.findings


@pytest.fixture
def mock_generator(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    generation = pytest.importorskip("ai_engine.generation")
    generator = generation.LLMDraftGenerator()
    assert generator.mode == "mock"
    return generator


@pytest.mark.parametrize("customer_id", ALLOWED_IDS)
def test_mock_provider_draft_passes_validation(
    engine, mock_generator, customer_id
) -> None:
    decision = engine.decide(CUSTOMERS[customer_id])
    message = mock_generator.generate(decision.facts)
    result = engine.validate(message.draft, decision)

    assert result.passed, result.findings
    assert result.findings == []
