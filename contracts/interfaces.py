"""Module boundaries as typing.Protocol. Architect-owned.

backend orchestrates; it depends on these protocols, not on implementations, so each
member can build and test their module against fakes while others are still working.
"""

from __future__ import annotations

from typing import Protocol

from contracts.models import (
    ClassificationResult,
    CustomerProfile,
    DraftContent,
    GeneratedMessage,
    PolicyDecision,
    ValidationResult,
    VerifiedFacts,
)


class GenerationError(RuntimeError):
    """Raised by a DraftGenerator when no valid structured draft could be produced.

    The backend records GENERATION_FAILED and creates no review item to approve.
    """


class PolicyEngine(Protocol):
    """Member 3. Deterministic; never calls an LLM."""

    def classify(self, profile: CustomerProfile) -> ClassificationResult: ...

    def decide(self, profile: CustomerProfile) -> PolicyDecision:
        """Classify, pick strategy, check offers, reminder stage, consent and contact
        frequency. Returns BLOCKED with reasons, or DRAFT_ALLOWED with VerifiedFacts."""
        ...

    def validate(
        self, draft: DraftContent, decision: PolicyDecision
    ) -> ValidationResult:
        """Check a draft (generated or human-edited) against the decision's facts,
        offer terms, blocked terms, support path, consent and contact frequency."""
        ...


class DraftGenerator(Protocol):
    """Member 2. Words a message from VerifiedFacts only. Raises GenerationError."""

    def generate(self, facts: VerifiedFacts) -> GeneratedMessage: ...
