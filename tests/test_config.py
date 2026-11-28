"""Tests for loading and validating policy configuration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.config import DEFAULT_CONFIG_DIR, ConfigError, load_policy

Mutator = Callable[[dict[str, dict[str, Any]]], None]


def _write_config(tmp_path: Path, mutate: Mutator) -> Path:
    """Copy the real config into tmp_path, apply ``mutate`` to the parsed files."""
    files = {
        path.stem: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in DEFAULT_CONFIG_DIR.glob("*.yaml")
    }
    mutate(files)
    for name, data in files.items():
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


def test_real_config_loads() -> None:
    policy = load_policy()

    assert policy.policy.as_of_date == date(2026, 11, 28)
    assert policy.policy.contact.reminders_require_marketing_consent is False
    assert set(policy.versions) == {
        "policy",
        "segments",
        "strategies",
        "offers",
        "reminders",
        "blocked_terms",
    }
    assert len(policy.offers.offers) == 3
    assert policy.strategies.strategies["consistent"].offer_allowed is False


def test_reminder_stages_match_problem_statement() -> None:
    stages = [(s.name, s.min_days, s.max_days) for s in load_policy().reminders.stages]

    assert stages == [("courteous", 1, 7), ("firm", 8, 21), ("final_notice", 22, None)]


def test_unchanged_copy_loads(tmp_path: Path) -> None:
    """Guards the helper: a round-tripped copy must load, so failures below are real."""
    load_policy(_write_config(tmp_path, lambda files: None))


def _drop_priority(files: dict) -> None:
    files["segments"]["priority"].remove("dormant")


def _unknown_segment_in_offer(files: dict) -> None:
    files["offers"]["offers"][0]["allowed_segments"] = ["vip"]


def _overlapping_stages(files: dict) -> None:
    files["reminders"]["stages"][1]["min_days"] = 7


def _gap_in_stages(files: dict) -> None:
    files["reminders"]["stages"][1]["min_days"] = 9


def _open_ended_not_last(files: dict) -> None:
    files["reminders"]["stages"][0]["max_days"] = None


def _last_stage_closed(files: dict) -> None:
    files["reminders"]["stages"][-1]["max_days"] = 60


def _unknown_strategy_tone(files: dict) -> None:
    files["strategies"]["strategies"]["dormant"]["tone"] = "aggressive"


def _unknown_stage_tone(files: dict) -> None:
    files["reminders"]["stages"][2]["tone"] = "threatening"


def _missing_strategy(files: dict) -> None:
    del files["strategies"]["strategies"]["declining"]


def _typo_key(files: dict) -> None:
    files["segments"]["thresholds"]["dormant_max_activty"] = 10


def _duplicate_offer_id(files: dict) -> None:
    files["offers"]["offers"][1]["offer_id"] = files["offers"]["offers"][0]["offer_id"]


def _percent_over_100(files: dict) -> None:
    files["offers"]["offers"][1]["value"] = 150


def _offer_for_no_offer_segment(files: dict) -> None:
    files["offers"]["offers"][0]["allowed_segments"] = ["consistent"]


def _empty_blocked_term(files: dict) -> None:
    files["blocked_terms"]["terms"].append("  ")


def _duplicate_blocked_term(files: dict) -> None:
    files["blocked_terms"]["terms"].append("Guaranteed")


@pytest.mark.parametrize(
    "mutate",
    [
        _drop_priority,
        _unknown_segment_in_offer,
        _overlapping_stages,
        _gap_in_stages,
        _open_ended_not_last,
        _last_stage_closed,
        _unknown_strategy_tone,
        _unknown_stage_tone,
        _missing_strategy,
        _typo_key,
        _duplicate_offer_id,
        _percent_over_100,
        _offer_for_no_offer_segment,
        _empty_blocked_term,
        _duplicate_blocked_term,
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, mutate: Mutator) -> None:
    with pytest.raises(ConfigError):
        load_policy(_write_config(tmp_path, mutate))


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path, lambda files: None)
    (config_dir / "offers.yaml").unlink()

    with pytest.raises(ConfigError, match="offers.yaml"):
        load_policy(config_dir)
