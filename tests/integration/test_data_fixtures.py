"""Checks on Member 5's synthetic data and labelled fixtures.

These tests guard the data contract in docs/DATA_DICTIONARY.md ("File data contracts")
and keep the hand-derived labels in data/fixtures/scenarios.jsonl consistent with the
current policy YAML. They do not exercise the real policy engine; the integration tests
that run every scenario through ``PolicyEngine.decide`` come once it exists.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from contracts.enums import (
    BillStatus,
    BlockReason,
    DecisionStatus,
    FindingCode,
    SegmentName,
)
from contracts.models import CustomerProfile, DraftContent
from policy_engine.config_loader import Policy, load_policy

ROOT = Path(__file__).resolve().parents[2]
CUSTOMERS_CSV = ROOT / "data" / "synthetic" / "customers.csv"
SCENARIOS = ROOT / "data" / "fixtures" / "scenarios.jsonl"
BAD_DRAFTS = ROOT / "data" / "fixtures" / "bad_drafts.jsonl"

SCENARIO_KEYS = {
    "customer_id",
    "scenario",
    "expected_primary_segment",
    "expected_status",
    "expected_block_reasons",
    "expected_reminder_stage",
    "expected_offer_id",
}
BAD_DRAFT_KEYS = {"case_id", "customer_id", "defect", "draft", "expected_finding_codes"}

# Column names that must never appear: protected characteristics, proxies, contact data.
FORBIDDEN_COLUMNS = {
    "email",
    "email_address",
    "phone",
    "age",
    "date_of_birth",
    "dob",
    "gender",
    "sex",
    "religion",
    "ethnicity",
    "race",
    "nationality",
    "disability",
    "marital_status",
    "location",
    "address",
    "city",
    "postcode",
    "pincode",
    "zip",
}

REQUIRED_SCENARIOS = {
    "consistent",
    "loyalty_candidate",
    "declining",
    "dormant",
    "overdue_courteous",
    "overdue_firm",
    "overdue_final_notice",
    "no_consent",
    "recent_contact",
    "overdue_no_consent",
    "ineligible_reward",
    "contradictory_billing",
    "missing_evidence",
    "prompt_injection_name",
}

REQUIRED_BAD_DRAFT_CODES = {
    FindingCode.UNKNOWN_OFFER,
    FindingCode.AMOUNT_MISMATCH,
    FindingCode.DATE_MISMATCH,
    FindingCode.BLOCKED_TERM,
    FindingCode.MISSING_SUPPORT_PATH,
    FindingCode.SENSITIVE_DATA,
}


# --- loaders -----------------------------------------------------------------


def _csv_value(field: str, raw: str) -> Any:
    """Turn a CSV cell into the value the data contract specifies (strictly)."""
    if field == "consent_marketing":
        if raw not in {"true", "false"}:
            raise ValueError(f"consent_marketing must be true/false, got {raw!r}")
        return raw == "true"
    if field in {"due_date", "last_contacted_days_ago"} and raw == "":
        return None
    return raw


def load_customer_rows() -> list[dict[str, str]]:
    with CUSTOMERS_CSV.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_customers() -> dict[str, CustomerProfile]:
    profiles = {}
    for row in load_customer_rows():
        values = {field: _csv_value(field, raw) for field, raw in row.items()}
        profile = CustomerProfile.model_validate(values)
        profiles[profile.customer_id] = profile
    return profiles


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture(scope="module")
def customers() -> dict[str, CustomerProfile]:
    return load_customers()


@pytest.fixture(scope="module")
def scenarios() -> list[dict[str, Any]]:
    return load_jsonl(SCENARIOS)


@pytest.fixture(scope="module")
def bad_drafts() -> list[dict[str, Any]]:
    return load_jsonl(BAD_DRAFTS)


@pytest.fixture(scope="module")
def policy() -> Policy:
    return load_policy()


# --- customers.csv -----------------------------------------------------------


def test_csv_header_is_exactly_the_customer_profile_fields() -> None:
    with CUSTOMERS_CSV.open(encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    assert header == list(CustomerProfile.model_fields)


def test_csv_has_no_forbidden_or_protected_columns() -> None:
    with CUSTOMERS_CSV.open(encoding="utf-8", newline="") as handle:
        header = {column.strip().lower() for column in next(csv.reader(handle))}
    assert header.isdisjoint(FORBIDDEN_COLUMNS)


def test_csv_contains_no_email_address_or_at_sign() -> None:
    assert "@" not in CUSTOMERS_CSV.read_text(encoding="utf-8")


def test_every_csv_row_validates_as_customer_profile(
    customers: dict[str, CustomerProfile],
) -> None:
    assert len(customers) == len(load_customer_rows())
    assert len(customers) >= 15


def test_customer_ids_are_unique_and_sequential() -> None:
    ids = [row["customer_id"] for row in load_customer_rows()]
    assert len(ids) == len(set(ids))
    assert ids == [f"CUST-{n:03d}" for n in range(1, len(ids) + 1)]


def test_csv_cells_follow_the_file_contract() -> None:
    for row in load_customer_rows():
        assert row["consent_marketing"] in {"true", "false"}
        assert re.fullmatch(r"\d+\.\d{2}", row["amount_due"]), row["customer_id"]
        assert row["due_date"] == "" or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", row["due_date"]
        )


def test_on_time_payments_never_exceed_tenure(
    customers: dict[str, CustomerProfile],
) -> None:
    for profile in customers.values():
        limit = min(profile.months_active, 12)
        assert profile.on_time_payments_12m <= limit, profile.customer_id


def test_overdue_due_dates_match_days_overdue(
    customers: dict[str, CustomerProfile], policy: Policy
) -> None:
    """Keep billing facts internally consistent unless a row is deliberately broken."""
    as_of = policy.policy.as_of_date
    for profile in customers.values():
        if profile.bill_status is BillStatus.OVERDUE and profile.due_date is not None:
            expected = as_of - timedelta(days=profile.days_overdue)
            assert profile.due_date == expected, profile.customer_id


def test_prompt_injection_row_is_plain_data(
    customers: dict[str, CustomerProfile], scenarios: list[dict[str, Any]]
) -> None:
    [row] = [s for s in scenarios if s["scenario"] == "prompt_injection_name"]
    name = customers[row["customer_id"]].first_name
    assert "ignore previous instructions" in name.lower()


# --- scenarios.jsonl ---------------------------------------------------------


def test_scenario_lines_have_exact_schema_and_valid_values(
    scenarios: list[dict[str, Any]],
) -> None:
    for line in scenarios:
        assert set(line) == SCENARIO_KEYS, line
        assert isinstance(line["scenario"], str) and line["scenario"]
        if line["expected_primary_segment"] is not None:
            SegmentName(line["expected_primary_segment"])
        status = DecisionStatus(line["expected_status"])
        reasons = [BlockReason(r) for r in line["expected_block_reasons"]]
        assert len(reasons) == len(set(reasons))
        if status is DecisionStatus.BLOCKED:
            assert reasons, line["customer_id"]
            assert line["expected_reminder_stage"] is None
            assert line["expected_offer_id"] is None
        else:
            assert reasons == [], line["customer_id"]


def test_one_scenario_line_per_customer(
    customers: dict[str, CustomerProfile], scenarios: list[dict[str, Any]]
) -> None:
    ids = [line["customer_id"] for line in scenarios]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(customers)


def test_required_scenarios_are_all_covered(scenarios: list[dict[str, Any]]) -> None:
    present = {line["scenario"] for line in scenarios}
    assert REQUIRED_SCENARIOS <= present
    counts = {name: 0 for name in ("consistent", "loyalty_candidate", "declining")}
    counts["dormant"] = 0
    for line in scenarios:
        if line["scenario"] in counts:
            counts[line["scenario"]] += 1
    assert all(count >= 2 for count in counts.values()), counts


def test_scenario_stages_and_offers_exist_in_policy(
    scenarios: list[dict[str, Any]], policy: Policy
) -> None:
    stages = {stage.name for stage in policy.reminders.stages}
    offers = {offer.offer_id for offer in policy.offers.offers}
    for line in scenarios:
        if line["expected_reminder_stage"] is not None:
            assert line["expected_reminder_stage"] in stages
        if line["expected_offer_id"] is not None:
            assert line["expected_offer_id"] in offers


# --- labels versus the policy YAML ---------------------------------------------
# A small reference reading of the rules (documented in data/fixtures/NOTES.md). It is
# not the policy engine; it makes a YAML threshold change that invalidates a label
# fail here, so labels are never silently stale.


def _reference_segments(profile: CustomerProfile, policy: Policy) -> list[SegmentName]:
    t = policy.segments.thresholds
    overdue = profile.bill_status is BillStatus.OVERDUE and profile.days_overdue >= 1
    act, prev = profile.activity_score_30d, profile.activity_score_prev_30d
    matched = set()
    if overdue:
        matched.add(SegmentName.PAYMENT_REMINDER)
    if act < t.dormant_max_activity:
        matched.add(SegmentName.DORMANT)
    if prev > 0 and (prev - act) / prev * 100 >= t.declining_min_drop_pct:
        matched.add(SegmentName.DECLINING)
    if (
        profile.months_active >= t.loyalty_min_months_active
        and profile.on_time_payments_12m >= t.loyalty_min_on_time_payments
        and act >= t.loyalty_min_activity
        and not overdue
    ):
        matched.add(SegmentName.LOYALTY_CANDIDATE)
    if (
        profile.on_time_payments_12m >= t.consistent_min_on_time_payments
        and act >= t.consistent_min_activity
    ):
        matched.add(SegmentName.CONSISTENT)
    return [s for s in policy.segments.priority if s in matched]


def _reference_block_reasons(
    profile: CustomerProfile, primary: SegmentName | None, policy: Policy
) -> set[BlockReason]:
    contact = policy.policy.contact
    reasons = set()
    is_reminder = primary is SegmentName.PAYMENT_REMINDER
    if not profile.consent_marketing and (
        not is_reminder or contact.reminders_require_marketing_consent
    ):
        reasons.add(BlockReason.NO_MARKETING_CONSENT)
    last = profile.last_contacted_days_ago
    if last is not None and last < contact.min_days_between_contacts:
        reasons.add(BlockReason.CONTACTED_TOO_RECENTLY)
    status, days, amount = profile.bill_status, profile.days_overdue, profile.amount_due
    if (status is BillStatus.PAID and days > 0) or (
        status is BillStatus.OVERDUE and (days == 0 or amount == Decimal("0"))
    ):
        reasons.add(BlockReason.CONTRADICTORY_BILLING_DATA)
    if status is BillStatus.OVERDUE and profile.due_date is None:
        reasons.add(BlockReason.MISSING_EVIDENCE)
    if primary is None:
        reasons.add(BlockReason.NO_ACTIONABLE_SEGMENT)
    return reasons


def _reference_stage(days_overdue: int, policy: Policy) -> str:
    for stage in policy.reminders.stages:
        if days_overdue >= stage.min_days and (
            stage.max_days is None or days_overdue <= stage.max_days
        ):
            return stage.name
    raise AssertionError(f"no stage for {days_overdue} days")


def _reference_offer(
    profile: CustomerProfile, primary: SegmentName, policy: Policy
) -> str | None:
    if not policy.strategies.strategies[primary].offer_allowed:
        return None
    eligible = [
        offer.offer_id
        for offer in policy.offers.offers
        if primary in offer.allowed_segments
        and profile.months_active >= offer.min_months_active
        and offer.expiry >= policy.policy.as_of_date
        and offer.channel == "email"
    ]
    assert len(eligible) <= 1, f"{profile.customer_id}: ambiguous offers {eligible}"
    return eligible[0] if eligible else None


@pytest.mark.parametrize(
    "line", load_jsonl(SCENARIOS), ids=lambda line: line["customer_id"]
)
def test_labels_follow_from_policy_yaml(
    line: dict[str, Any], customers: dict[str, CustomerProfile], policy: Policy
) -> None:
    profile = customers[line["customer_id"]]
    segments = _reference_segments(profile, policy)
    primary = segments[0] if segments else None
    assert line["expected_primary_segment"] == (primary and primary.value)

    reasons = _reference_block_reasons(profile, primary, policy)
    assert set(line["expected_block_reasons"]) == {r.value for r in reasons}
    expected_status = (
        DecisionStatus.BLOCKED if reasons else DecisionStatus.DRAFT_ALLOWED
    )
    assert line["expected_status"] == expected_status.value

    allowed = not reasons
    stage = None
    if allowed and primary is SegmentName.PAYMENT_REMINDER:
        stage = _reference_stage(profile.days_overdue, policy)
    assert line["expected_reminder_stage"] == stage

    offer = _reference_offer(profile, primary, policy) if allowed else None
    assert line["expected_offer_id"] == offer


def test_ineligible_reward_row_fails_only_on_tenure(
    customers: dict[str, CustomerProfile],
    scenarios: list[dict[str, Any]],
    policy: Policy,
) -> None:
    [line] = [s for s in scenarios if s["scenario"] == "ineligible_reward"]
    profile = customers[line["customer_id"]]
    segment = SegmentName(line["expected_primary_segment"])
    [offer] = [o for o in policy.offers.offers if segment in o.allowed_segments]
    assert profile.months_active < offer.min_months_active
    assert offer.expiry >= policy.policy.as_of_date
    assert line["expected_offer_id"] is None
    assert line["expected_status"] == DecisionStatus.DRAFT_ALLOWED.value


# --- bad_drafts.jsonl ----------------------------------------------------------


def test_bad_draft_lines_have_exact_schema(bad_drafts: list[dict[str, Any]]) -> None:
    case_ids = [case["case_id"] for case in bad_drafts]
    assert len(case_ids) == len(set(case_ids))
    for case in bad_drafts:
        assert set(case) == BAD_DRAFT_KEYS, case.get("case_id")
        DraftContent.model_validate(case["draft"])
        codes = [FindingCode(code) for code in case["expected_finding_codes"]]
        assert codes, case["case_id"]


def test_bad_drafts_reference_known_customers(
    bad_drafts: list[dict[str, Any]],
    customers: dict[str, CustomerProfile],
    scenarios: list[dict[str, Any]],
) -> None:
    labels = {line["customer_id"]: line for line in scenarios}
    gate_codes = {
        FindingCode.CONSENT_GAP: BlockReason.NO_MARKETING_CONSENT,
        FindingCode.DUPLICATE_OUTREACH: BlockReason.CONTACTED_TOO_RECENTLY,
    }
    for case in bad_drafts:
        assert case["customer_id"] in customers
        label = labels[case["customer_id"]]
        codes = {FindingCode(code) for code in case["expected_finding_codes"]}
        gate = [gate_codes[c].value for c in codes if c in gate_codes]
        if gate:
            assert label["expected_status"] == DecisionStatus.BLOCKED.value
            assert set(gate) <= set(label["expected_block_reasons"])
        else:
            # Content defects are tested against customers whose decision is allowed,
            # so the only reason to block is the draft itself.
            assert label["expected_status"] == DecisionStatus.DRAFT_ALLOWED.value


def test_bad_drafts_cover_every_required_defect(
    bad_drafts: list[dict[str, Any]],
) -> None:
    covered = {
        FindingCode(c) for case in bad_drafts for c in case["expected_finding_codes"]
    }
    assert REQUIRED_BAD_DRAFT_CODES <= covered


def test_reminder_bad_drafts_isolate_the_support_path_defect(
    bad_drafts: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    policy: Policy,
) -> None:
    """Only the missing-support-path case omits the support path, so other reminder
    cases test exactly the defect they are labelled with."""
    support_path = " ".join(policy.reminders.support_path.split())
    reminders = {
        line["customer_id"]
        for line in scenarios
        if line["expected_reminder_stage"] is not None
    }
    for case in bad_drafts:
        if case["customer_id"] not in reminders:
            continue
        body = " ".join(case["draft"]["body"].split())
        missing = (
            FindingCode.MISSING_SUPPORT_PATH.value in case["expected_finding_codes"]
        )
        assert (support_path not in body) == missing, case["case_id"]
