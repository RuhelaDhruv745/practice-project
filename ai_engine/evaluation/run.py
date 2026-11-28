"""Measure the drafting pipeline on the synthetic customers.

Usage: ``python -m ai_engine.evaluation.run [--csv PATH] [--output PATH]
[--config-dir PATH]``

For every customer: ``PolicyEngine.decide``; for each ``draft_allowed`` decision, run
the configured generator (mock unless ``LLM_PROVIDER`` and a key say otherwise) and
record whether the reply parsed, whether the grounding pre-check passed and, when the
policy engine implements it, ``PolicyEngine.validate`` (passed + finding codes). If
``validate`` raises ``NotImplementedError`` that is recorded as ``skipped``, never as a
pass. Writes ``outputs/ai_evaluation.json`` and prints a summary. Every number is
counted from this run; nothing is estimated.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_engine.generation.cache import cache_from_env
from ai_engine.generation.generator import (
    DraftParseError,
    LLMDraftGenerator,
    parse_draft,
)
from ai_engine.generation.providers import (
    LLMProvider,
    PromptRequest,
    provider_from_env,
)
from ai_engine.grounding.facts import missing_required_facts
from contracts.enums import DecisionStatus, Severity
from contracts.interfaces import GenerationError, PolicyEngine
from contracts.models import (
    CustomerProfile,
    DraftContent,
    PolicyDecision,
    VerifiedFacts,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "data" / "synthetic" / "customers.csv"
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "ai_evaluation.json"


class EvaluationInputError(ValueError):
    """The customer CSV is missing or a row is not a valid CustomerProfile."""


def load_profiles(csv_path: Path) -> list[CustomerProfile]:
    """Read and validate every row (empty cells are ``None``). Fails loudly."""
    if not csv_path.is_file():
        raise EvaluationInputError(f"CSV not found: {csv_path.name}")
    profiles: list[CustomerProfile] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            values = {k: (None if v == "" else v) for k, v in row.items()}
            try:
                profiles.append(CustomerProfile.model_validate(values))
            except ValueError:
                raise EvaluationInputError(
                    f"line {line_no}: not a valid customer profile"
                ) from None
    return profiles


@dataclass
class _Attempt:
    parsed: bool
    grounded: bool | None
    problem: str | None


@dataclass
class RecordingProvider:
    """Wraps a provider and keeps each raw reply so attempts can be scored.

    The raw replies stay in memory only; they are not written to the report.
    """

    inner: LLMProvider
    replies: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    def complete(self, request: PromptRequest) -> str:
        reply = self.inner.complete(request)
        self.replies.append(reply)
        return reply


def _score_reply(raw: str, facts: VerifiedFacts) -> _Attempt:
    try:
        draft = parse_draft(raw)
    except DraftParseError as exc:
        return _Attempt(parsed=False, grounded=None, problem=str(exc))
    missing = missing_required_facts(draft, facts)
    problem = ("missing facts: " + ", ".join(missing)) if missing else None
    return _Attempt(parsed=True, grounded=not missing, problem=problem)


def _validate(
    engine: PolicyEngine, decision: PolicyDecision, draft: DraftContent
) -> dict[str, Any]:
    try:
        result = engine.validate(draft, decision)
    except NotImplementedError:
        return {"status": "skipped", "reason": "validate not implemented"}
    except Exception as exc:  # a validator bug must be visible, not fatal
        return {"status": "error", "error_type": type(exc).__name__}
    return {
        "status": "passed" if result.passed else "failed",
        "passed": result.passed,
        "finding_codes": [f.code.value for f in result.findings],
        "blocking_codes": [
            f.code.value for f in result.findings if f.severity is Severity.BLOCKING
        ],
        "validator_version": result.validator_version,
    }


def evaluate_customer(
    profile: CustomerProfile,
    engine: PolicyEngine,
    generator: LLMDraftGenerator,
    recorder: RecordingProvider,
) -> dict[str, Any]:
    decision = engine.decide(profile)
    record: dict[str, Any] = {
        "customer_id": profile.customer_id,
        "decision_status": decision.status.value,
        "block_reasons": [r.value for r in decision.block_reasons],
    }
    if decision.status is not DecisionStatus.DRAFT_ALLOWED or decision.facts is None:
        return record

    facts = decision.facts
    record["segment"] = facts.segment.value
    record["offer_id"] = facts.offer.offer_id if facts.offer else None
    record["reminder_stage"] = facts.reminder.stage if facts.reminder else None
    recorder.replies.clear()
    try:
        message = generator.generate(facts)
    except GenerationError as exc:
        message = None
        record["generation_error"] = str(exc)[:300]
    attempts = [_score_reply(raw, facts) for raw in recorder.replies]
    record["provider_calls"] = len(attempts)
    record["from_cache"] = message is not None and not attempts
    record["attempts"] = [
        {"parsed": a.parsed, "grounded": a.grounded, "problem": a.problem}
        for a in attempts
    ]
    record["generated"] = message is not None
    if message is None:
        record["parsed_ok"] = any(a.parsed for a in attempts)
        record["grounding_ok"] = False
        record["validation"] = {"status": "not_run", "reason": "no draft"}
        return record
    record["parsed_ok"] = True
    record["grounding_ok"] = not missing_required_facts(message.draft, facts)
    record["draft"] = message.draft.model_dump()
    record["validation"] = _validate(engine, decision, message.draft)
    return record


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = [r for r in records if r["decision_status"] == "draft_allowed"]
    validation = Counter(r["validation"]["status"] for r in allowed)
    findings: Counter[str] = Counter()
    for r in allowed:
        findings.update(r["validation"].get("finding_codes", []))
    first_ok = sum(
        1
        for r in allowed
        if r["attempts"] and r["attempts"][0]["parsed"] and r["attempts"][0]["grounded"]
    )
    return {
        "customers": len(records),
        "draft_allowed": len(allowed),
        "blocked": len(records) - len(allowed),
        "generated": sum(1 for r in allowed if r["generated"]),
        "generation_errors": sum(1 for r in allowed if not r["generated"]),
        "parsed_ok": sum(1 for r in allowed if r["parsed_ok"]),
        "grounding_ok": sum(1 for r in allowed if r["grounding_ok"]),
        "first_attempt_ok": first_ok,
        "from_cache": sum(1 for r in allowed if r["from_cache"]),
        "validation": {
            "passed": validation.get("passed", 0),
            "failed": validation.get("failed", 0),
            "skipped": validation.get("skipped", 0),
            "error": validation.get("error", 0),
            "not_run": validation.get("not_run", 0),
        },
        "finding_codes": dict(sorted(findings.items())),
    }


def run_evaluation(
    profiles: Sequence[CustomerProfile],
    engine: PolicyEngine,
    provider: LLMProvider,
    *,
    use_env_cache: bool = False,
) -> dict[str, Any]:
    """Evaluate every profile; returns the full report (summary + per customer)."""
    recorder = RecordingProvider(provider)
    generator = LLMDraftGenerator(
        provider=recorder, cache=cache_from_env() if use_env_cache else None
    )
    records = [evaluate_customer(p, engine, generator, recorder) for p in profiles]
    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "provider": provider.name,
        "model": provider.model,
        "prompt_version": generator.prompt_version,
        "summary": summarise(records),
        "customers": records,
    }


def format_summary(report: dict[str, Any]) -> str:
    s = report["summary"]
    n = s["draft_allowed"]
    v = s["validation"]
    lines = [
        f"AI evaluation ({report['provider']} / {report['model']}, "
        f"{report['prompt_version']})",
        f"customers: {s['customers']}  draft_allowed: {n}  blocked: {s['blocked']}",
        f"generated: {s['generated']}/{n}  parsed_ok: {s['parsed_ok']}/{n}  "
        f"grounding_ok: {s['grounding_ok']}/{n}  first_attempt_ok: "
        f"{s['first_attempt_ok']}/{n}  from_cache: {s['from_cache']}",
        f"validation: passed {v['passed']}, failed {v['failed']}, skipped "
        f"{v['skipped']}, error {v['error']}, not_run {v['not_run']} (of {n})",
    ]
    if s["finding_codes"]:
        codes = ", ".join(f"{k}={c}" for k, c in s["finding_codes"].items())
        lines.append(f"finding codes: {codes}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    # Imported here so ai_engine's runtime import graph never depends on policy_engine.
    from policy_engine.engine import RuleBasedPolicyEngine

    engine = (
        RuleBasedPolicyEngine.from_config_dir(args.config_dir)
        if args.config_dir
        else RuleBasedPolicyEngine.from_config_dir()
    )
    try:
        profiles = load_profiles(args.csv)
    except EvaluationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = run_evaluation(profiles, engine, provider_from_env(), use_env_cache=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(format_summary(report))
    print(f"report: {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
