"""Load and validate policy configuration from data/policies/*.yaml.

Policy (thresholds, segments, offers, tones, reminder stages, blocked terms) lives
in YAML so a policy owner can change it without code edits. Loading fails fast on
any unknown key, unknown reference or inconsistent range.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
    model_validator,
)

from contracts.enums import Channel, OfferUnit, SegmentName

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "data" / "policies"

# Segment rules are implemented in code, so the segment names are a fixed contract
# (contracts.enums.SegmentName). Config controls thresholds, priority, strategy, offers.
SEGMENT_NAMES: frozenset[SegmentName] = frozenset(SegmentName)


class ConfigError(ValueError):
    """Raised when a policy file is missing or invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- policy.yaml -------------------------------------------------------------


class ContactRules(_Strict):
    min_days_between_contacts: int = Field(ge=0)
    reminders_require_marketing_consent: bool


class GeneralPolicy(_Strict):
    version: str
    as_of_date: date
    currency: str = Field(min_length=3, max_length=3)
    contact: ContactRules


# --- segments.yaml -----------------------------------------------------------


class SegmentThresholds(_Strict):
    declining_min_drop_pct: float = Field(gt=0, le=100)
    dormant_max_activity: float = Field(ge=0)
    loyalty_min_months_active: int = Field(ge=0)
    loyalty_min_on_time_payments: int = Field(ge=0, le=12)
    loyalty_min_activity: float = Field(ge=0)
    consistent_min_on_time_payments: int = Field(ge=0, le=12)
    consistent_min_activity: float = Field(ge=0)


class SegmentConfig(_Strict):
    version: str
    priority: list[SegmentName]
    thresholds: SegmentThresholds

    @model_validator(mode="after")
    def _priority_lists_every_segment_once(self) -> SegmentConfig:
        if (
            len(self.priority) != len(set(self.priority))
            or set(self.priority) != SEGMENT_NAMES
        ):
            raise ValueError(
                f"priority must list each of {sorted(SEGMENT_NAMES)} exactly once"
            )
        return self


# --- strategies.yaml ---------------------------------------------------------


class Strategy(_Strict):
    objective: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    offer_allowed: bool


class StrategyConfig(_Strict):
    version: str
    tones: dict[str, str]
    strategies: dict[SegmentName, Strategy]

    @model_validator(mode="after")
    def _complete_and_known_tones(self) -> StrategyConfig:
        missing = SEGMENT_NAMES - set(self.strategies)
        if missing:
            raise ValueError(f"no strategy for segments: {sorted(missing)}")
        for segment, strategy in self.strategies.items():
            if strategy.tone not in self.tones:
                raise ValueError(
                    f"strategy {segment!r} uses unknown tone {strategy.tone!r}"
                )
        return self


# --- offers.yaml -------------------------------------------------------------


class Offer(_Strict):
    offer_id: str = Field(pattern=r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
    description: str = Field(min_length=1)
    value: Decimal = Field(gt=0)
    unit: OfferUnit
    expiry: date
    allowed_segments: list[SegmentName] = Field(min_length=1)
    min_months_active: int = Field(ge=0)
    channel: Channel

    @model_validator(mode="after")
    def _percent_at_most_100(self) -> Offer:
        if self.unit == "percent" and self.value > 100:
            raise ValueError(f"offer {self.offer_id}: percent value above 100")
        return self


class OfferConfig(_Strict):
    version: str
    offers: list[Offer]

    @model_validator(mode="after")
    def _unique_ids(self) -> OfferConfig:
        ids = [offer.offer_id for offer in self.offers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate offer_id")
        return self


# --- reminders.yaml ----------------------------------------------------------


class ReminderStage(_Strict):
    name: str = Field(min_length=1)
    min_days: PositiveInt
    max_days: PositiveInt | None
    tone: str = Field(min_length=1)


class ReminderConfig(_Strict):
    version: str
    support_path: str = Field(min_length=10)
    stages: list[ReminderStage] = Field(min_length=1)

    @model_validator(mode="after")
    def _contiguous_stages(self) -> ReminderConfig:
        """Stages must cover 1, 2, 3, ... with no gap or overlap, open-ended last."""
        expected_start = 1
        for i, stage in enumerate(self.stages):
            if stage.min_days != expected_start:
                raise ValueError(
                    f"stage {stage.name!r} starts at {stage.min_days}, expected {expected_start}"
                )
            is_last = i == len(self.stages) - 1
            if stage.max_days is None:
                if not is_last:
                    raise ValueError(
                        f"only the last stage may be open-ended, not {stage.name!r}"
                    )
                break
            if stage.max_days < stage.min_days:
                raise ValueError(f"stage {stage.name!r} ends before it starts")
            expected_start = stage.max_days + 1
        else:
            raise ValueError(
                "the last reminder stage must be open-ended (max_days: null)"
            )
        if len({stage.name for stage in self.stages}) != len(self.stages):
            raise ValueError("duplicate reminder stage name")
        return self


# --- blocked_terms.yaml ------------------------------------------------------


class BlockedTermsConfig(_Strict):
    version: str
    terms: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _non_empty_unique(self) -> BlockedTermsConfig:
        normalised = [term.strip().lower() for term in self.terms]
        if any(not term for term in normalised):
            raise ValueError("blocked term must not be empty")
        if len(normalised) != len(set(normalised)):
            raise ValueError("duplicate blocked term")
        return self


# --- whole policy ------------------------------------------------------------

_FILES: dict[str, type[_Strict]] = {
    "policy": GeneralPolicy,
    "segments": SegmentConfig,
    "strategies": StrategyConfig,
    "offers": OfferConfig,
    "reminders": ReminderConfig,
    "blocked_terms": BlockedTermsConfig,
}


class Policy(_Strict):
    policy: GeneralPolicy
    segments: SegmentConfig
    strategies: StrategyConfig
    offers: OfferConfig
    reminders: ReminderConfig
    blocked_terms: BlockedTermsConfig

    @model_validator(mode="after")
    def _cross_file_references(self) -> Policy:
        tones = self.strategies.tones
        for stage in self.reminders.stages:
            if stage.tone not in tones:
                raise ValueError(
                    f"reminder stage {stage.name!r} uses unknown tone {stage.tone!r}"
                )
        for offer in self.offers.offers:
            for segment in offer.allowed_segments:
                if not self.strategies.strategies[segment].offer_allowed:
                    raise ValueError(
                        f"offer {offer.offer_id} targets {segment!r}, "
                        "whose strategy allows no offer"
                    )
        return self

    @property
    def versions(self) -> dict[str, str]:
        """Version of each policy file, for the audit record."""
        return {name: getattr(self, name).version for name in _FILES}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"missing config file: {path.name}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: top level must be a mapping")
    return data


def load_policy(config_dir: Path | str = DEFAULT_CONFIG_DIR) -> Policy:
    """Load, validate and cross-check every policy file in ``config_dir``."""
    config_dir = Path(config_dir)
    parts: dict[str, _Strict] = {}
    for name, model in _FILES.items():
        try:
            parts[name] = model.model_validate(_read_yaml(config_dir / f"{name}.yaml"))
        except ValidationError as exc:
            raise ConfigError(f"{name}.yaml: {exc}") from exc
    try:
        return Policy(**parts)
    except ValidationError as exc:
        raise ConfigError(f"cross-file check failed: {exc}") from exc
