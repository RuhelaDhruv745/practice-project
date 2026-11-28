"""Evaluation script on the real synthetic CSV with the mock provider (no API calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_engine.evaluation.run import (
    DEFAULT_CSV,
    EvaluationInputError,
    load_profiles,
    main,
    run_evaluation,
)
from ai_engine.generation import LLMDraftGenerator, MockProvider, PromptRequest
from contracts.enums import DecisionStatus, FindingCode, Severity
from contracts.models import (
    ClassificationResult,
    CustomerProfile,
    DraftContent,
    PolicyDecision,
    ValidationFinding,
    ValidationResult,
)
from policy_engine.engine import RuleBasedPolicyEngine


@pytest.fixture(scope="module")
def engine() -> RuleBasedPolicyEngine:
    return RuleBasedPolicyEngine.from_config_dir()


@pytest.fixture(scope="module")
def profiles() -> list[CustomerProfile]:
    return load_profiles(DEFAULT_CSV)


class StubValidatingEngine:
    """Real decide; validate flags any draft for one customer with a blocking finding."""

    def __init__(self, inner: RuleBasedPolicyEngine, fail_for: str) -> None:
        self._inner = inner
        self._fail_for = fail_for

    def classify(self, profile: CustomerProfile) -> ClassificationResult:
        return self._inner.classify(profile)

    def decide(self, profile: CustomerProfile) -> PolicyDecision:
        return self._inner.decide(profile)

    def validate(
        self, draft: DraftContent, decision: PolicyDecision
    ) -> ValidationResult:
        checks = [FindingCode.AMOUNT_MISMATCH]
        if decision.customer_id == self._fail_for:
            finding = ValidationFinding(
                code=FindingCode.AMOUNT_MISMATCH,
                severity=Severity.BLOCKING,
                message="stub",
            )
            return ValidationResult(
                passed=False,
                findings=[finding],
                checks_run=checks,
                validator_version="stub",
            )
        return ValidationResult(
            passed=True, checks_run=checks, validator_version="stub"
        )


def test_every_allowed_csv_row_generates_with_mock(
    engine: RuleBasedPolicyEngine, profiles: list[CustomerProfile]
) -> None:
    """Sprint 2 re-check: real decide() facts never make the generator fail."""
    generator = LLMDraftGenerator(provider=MockProvider())
    allowed = 0
    for profile in profiles:
        decision = engine.decide(profile)
        if decision.status is not DecisionStatus.DRAFT_ALLOWED:
            continue
        assert decision.facts is not None
        allowed += 1
        message = generator.generate(decision.facts)
        assert message.customer_id == profile.customer_id
        assert (message.provider, message.prompt_version) == ("mock", "draft_v1")
    assert allowed > 0


def test_report_counts_are_measured(
    engine: RuleBasedPolicyEngine, profiles: list[CustomerProfile]
) -> None:
    report = run_evaluation(profiles, engine, MockProvider())
    summary = report["summary"]
    records = report["customers"]
    allowed = [r for r in records if r["decision_status"] == "draft_allowed"]
    assert summary["customers"] == len(profiles) == len(records)
    assert summary["draft_allowed"] == len(allowed) > 0
    assert summary["blocked"] == len(records) - len(allowed)
    assert summary["generated"] == summary["parsed_ok"] == summary["grounding_ok"]
    assert summary["generated"] == len(allowed)
    assert summary["first_attempt_ok"] == len(allowed)
    for record in allowed:
        assert record["provider_calls"] == 1
        assert record["attempts"][0] == {
            "parsed": True,
            "grounded": True,
            "problem": None,
        }
    for record in records:
        if record["decision_status"] == "blocked":
            assert record["block_reasons"]
            assert "draft" not in record


def test_validation_skipped_when_not_implemented(
    profiles: list[CustomerProfile],
) -> None:
    class NotImplementedEngine(StubValidatingEngine):
        def validate(self, draft, decision):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    engine = NotImplementedEngine(RuleBasedPolicyEngine.from_config_dir(), "")
    summary = run_evaluation(profiles, engine, MockProvider())["summary"]
    assert summary["validation"]["skipped"] == summary["draft_allowed"]
    assert summary["validation"]["passed"] == 0
    assert summary["finding_codes"] == {}


def test_validation_results_and_codes_recorded(
    engine: RuleBasedPolicyEngine, profiles: list[CustomerProfile]
) -> None:
    first_allowed = next(
        p.customer_id
        for p in profiles
        if engine.decide(p).status is DecisionStatus.DRAFT_ALLOWED
    )
    stub = StubValidatingEngine(engine, fail_for=first_allowed)
    report = run_evaluation(profiles, stub, MockProvider())
    summary = report["summary"]
    assert summary["validation"]["failed"] == 1
    assert summary["validation"]["passed"] == summary["draft_allowed"] - 1
    assert summary["validation"]["skipped"] == 0
    assert summary["finding_codes"] == {"amount_mismatch": 1}
    failed = next(r for r in report["customers"] if r["customer_id"] == first_allowed)
    assert failed["validation"]["blocking_codes"] == ["amount_mismatch"]


def test_validator_exception_recorded_as_error(
    engine: RuleBasedPolicyEngine, profiles: list[CustomerProfile]
) -> None:
    class BrokenEngine(StubValidatingEngine):
        def validate(self, draft, decision):  # type: ignore[no-untyped-def]
            raise KeyError("bug")

    summary = run_evaluation(profiles, BrokenEngine(engine, ""), MockProvider())[
        "summary"
    ]
    assert summary["validation"]["error"] == summary["draft_allowed"]


def test_generation_failure_is_counted(
    engine: RuleBasedPolicyEngine, profiles: list[CustomerProfile]
) -> None:
    class BadProvider:
        name = "anthropic"
        model = "stub"

        def complete(self, request: PromptRequest) -> str:
            return "not json"

    summary = run_evaluation(profiles, engine, BadProvider())["summary"]
    assert summary["generated"] == 0
    assert summary["parsed_ok"] == 0
    assert summary["generation_errors"] == summary["draft_allowed"]
    assert summary["validation"]["not_run"] == summary["draft_allowed"]


def test_main_writes_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "ai_evaluation.json"
    assert main(["--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["provider"] == "mock"
    printed = capsys.readouterr().out
    assert f"customers: {report['summary']['customers']}" in printed
    assert "validation:" in printed


def test_missing_csv_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(EvaluationInputError):
        load_profiles(tmp_path / "nope.csv")
    assert (
        main(
            ["--csv", str(tmp_path / "nope.csv"), "--output", str(tmp_path / "o.json")]
        )
        == 2
    )
