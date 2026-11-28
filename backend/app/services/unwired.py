"""Stand-ins used by the module-level ``app`` until Members 2 and 3 merge.

They satisfy the Protocols but refuse every call, so a misconfigured deployment
fails loudly (500 ``internal_error``) instead of inventing segments or drafts.
Replace them in ``backend/app/main.py`` with the real implementations.
"""

from __future__ import annotations

from contracts.models import (
    ClassificationResult,
    CustomerProfile,
    DraftContent,
    GeneratedMessage,
    PolicyDecision,
    ValidationResult,
    VerifiedFacts,
)


class NotWiredError(RuntimeError):
    """A module implementation has not been wired into the backend yet."""


class UnwiredPolicyEngine:
    def classify(self, profile: CustomerProfile) -> ClassificationResult:
        raise NotWiredError("policy engine is not wired yet")

    def decide(self, profile: CustomerProfile) -> PolicyDecision:
        raise NotWiredError("policy engine is not wired yet")

    def validate(
        self, draft: DraftContent, decision: PolicyDecision
    ) -> ValidationResult:
        raise NotWiredError("policy engine is not wired yet")


class UnwiredDraftGenerator:
    def generate(self, facts: VerifiedFacts) -> GeneratedMessage:
        raise NotWiredError("draft generator is not wired yet")
