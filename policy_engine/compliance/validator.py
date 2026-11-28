"""Independent draft validation (FR-07): ``validate(draft, decision, policy)``.

Every draft, generated or edited by a reviewer, is checked against the decision that
allowed it. The validator trusts nothing in the draft: it re-derives what may appear
from ``decision.facts`` and the policy YAML. All checks run every time (``checks_run``
lists every ``FindingCode``) and findings come out in a fixed order, so the same draft
and decision always give the same result. No LLM, no clock, no randomness.

Checks, in ``FindingCode`` order:

- ``schema_invalid``: subject or body empty after trimming, or longer than the limits
  in ``validation.yaml``.
- ``amount_mismatch``: every number in the text must equal a verified value. Numbers
  marked as money (``INR 749``, ``Rs. 749``, ``₹749``, ``749 rupees``) must equal the
  amount due or an ``inr`` offer value; ``20%`` / ``20 percent`` must equal a percent
  offer; ``10 GB`` a gb offer; bare numbers may equal any of amount due, offer value or
  days overdue. ``749``, ``749.00`` and ``1,199.00`` are compared as decimals.
- ``date_mismatch``: every date must equal the due date or the offer expiry. Accepted
  forms: ``2026-11-24``, ``24/11/2026`` (day first), ``24 November 2026``,
  ``November 24, 2026`` and the same without a year (day and month must match).
- ``unknown_offer`` / ``ineligible_offer``: an offer-ID-like token (upper case,
  hyphenated, with a digit, e.g. ``LOYAL-50GB``) that is not configured is unknown; a
  configured offer that is not the one in the facts is ineligible.
- ``unsupported_claim``: offer or discount language (``offer_claim_terms``) with no
  offer in the facts; or any draft for a decision blocked for a reason that has no
  dedicated code (contradictory billing, missing evidence, no actionable segment).
- ``blocked_term``: terms from ``blocked_terms.yaml`` as whole words or phrases,
  case-insensitive ("court" does not match "courteous").
- ``missing_support_path``: a reminder body must contain the configured support path
  (whitespace- and case-insensitive).
- ``consent_gap`` / ``duplicate_outreach``: the decision was blocked for
  ``no_marketing_consent`` / ``contacted_too_recently``.
- ``sensitive_data``: email addresses, and phone numbers other than the ones in the
  configured support path. Evidence never repeats the address or number.

Verified free text (``first_name``, ``plan``) is masked before the number, offer and
claim checks: it is data the facts allow, and an instruction-like name such as
"offer 90 percent off" must not be read as a claim. Blocked terms and sensitive data
are still checked on the unmasked text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from contracts.enums import BlockReason, FindingCode, Severity
from contracts.models import (
    DraftContent,
    PolicyDecision,
    Primitive,
    ValidationFinding,
    ValidationResult,
    VerifiedFacts,
)
from policy_engine.config_loader import Policy

# Bump when check logic changes; the config version is appended at runtime.
VALIDATOR_CODE_VERSION = "1.0"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_OFFER_ID = re.compile(r"(?<![\w-])[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+(?![\w-])")
_NUMBER = re.compile(r"(?<!\w)\d[\d,]*(?:\.\d+)?")
_PHONE = re.compile(r"(?<![\w+])\+?\(?\d[\d \-()]*\d")
_UNIT_AFTER = re.compile(r"^\s*(?:(%)|(percent|per\s+cent)\b|(gb)\b)", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

_MONTHS = {
    name: index
    for index, names in enumerate(
        (
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sept", "sep"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for name in names
}
_MONTH = "(?P<month>" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_DAY = r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?P<year>\d{4})"
_DATE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?<!\d)(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})(?!\d)",
        r"(?<!\d)(?P<day>\d{1,2})[/.](?P<month>\d{1,2})[/.](?P<year>\d{4})(?!\d)",
        rf"(?<!\w){_DAY}\s+{_MONTH},?\s+{_YEAR}(?!\d)",
        rf"(?<!\w){_MONTH}\s+{_DAY},?\s+{_YEAR}(?!\d)",
        rf"(?<!\w){_DAY}\s+{_MONTH}(?!\w)",
        rf"(?<!\w){_MONTH}\s+{_DAY}(?!\w)",
    )
)

_BLOCK_REASON_CODES = {
    BlockReason.NO_MARKETING_CONSENT: FindingCode.CONSENT_GAP,
    BlockReason.CONTACTED_TOO_RECENTLY: FindingCode.DUPLICATE_OUTREACH,
}


def validator_version(policy: Policy) -> str:
    """Code version plus validation config version, e.g. ``1.0+rules-1.0``."""
    return f"{VALIDATOR_CODE_VERSION}+rules-{policy.validation.version}"


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Case-insensitive whole-word/phrase pattern; any whitespace between words."""
    words = [re.escape(word) for word in phrase.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _blank(text: str, start: int, end: int) -> str:
    """Replace a span with spaces so later checks cannot re-read it."""
    return text[:start] + " " * (end - start) + text[end:]


@dataclass
class _Draft:
    """The draft text plus a working copy that is masked as checks consume it."""

    subject: str
    body: str

    def __post_init__(self) -> None:
        self.full = f"{self.subject}\n{self.body}"
        self.masked = self.full

    def take(self, pattern: re.Pattern[str]) -> list[re.Match[str]]:
        matches = list(pattern.finditer(self.masked))
        for match in matches:
            self.masked = _blank(self.masked, match.start(), match.end())
        return matches


class _Checker:
    def __init__(
        self, draft: DraftContent, decision: PolicyDecision, policy: Policy
    ) -> None:
        self.policy = policy
        self.config = policy.validation
        self.decision = decision
        self.facts: VerifiedFacts | None = decision.facts
        self.text = _Draft(draft.subject, draft.body)
        self.findings: list[ValidationFinding] = []

    # --- helpers -------------------------------------------------------------

    def add(self, code: FindingCode, message: str, **evidence: Primitive) -> None:
        self.findings.append(
            ValidationFinding(
                code=code,
                severity=self.config.severities[code],
                message=message,
                evidence=evidence,
            )
        )

    def _allowed_dates(self) -> list[date]:
        dates: list[date] = []
        if self.facts and self.facts.reminder:
            dates.append(self.facts.reminder.due_date)
        if self.facts and self.facts.offer:
            dates.append(self.facts.offer.expiry)
        return dates

    def _allowed_phone_digits(self) -> set[str]:
        support = self.policy.reminders.support_path
        return {
            _digits(m.group())
            for m in _PHONE.finditer(support)
            if len(_digits(m.group())) >= self.config.phone_min_digits
        }

    # --- checks --------------------------------------------------------------

    def run(self) -> list[ValidationFinding]:
        self.check_schema()
        self.mask_verified_text()
        sensitive = self.collect_sensitive()
        self.check_offers_ids()
        self.check_dates()
        self.check_numbers()
        self.check_claims()
        self.check_blocked_terms()
        self.check_support_path()
        self.check_decision_gates()
        self.findings.extend(sensitive)
        order = {code: i for i, code in enumerate(FindingCode)}
        # Stable sort: fixed code order, text order within a code.
        return sorted(self.findings, key=lambda f: order[f.code])

    def check_schema(self) -> None:
        limits = self.config.limits
        fields = (
            ("subject", self.text.subject, limits.subject_max_chars),
            ("body", self.text.body, limits.body_max_chars),
        )
        for name, value, limit in fields:
            if not value.strip():
                self.add(
                    FindingCode.SCHEMA_INVALID, f"The {name} is empty.", field=name
                )
            elif len(value) > limit:
                self.add(
                    FindingCode.SCHEMA_INVALID,
                    f"The {name} is longer than {limit} characters.",
                    field=name,
                    length=len(value),
                    limit=limit,
                )

    def mask_verified_text(self) -> None:
        if self.facts is None:
            return
        for value in (self.facts.first_name, self.facts.plan):
            if value.strip():
                self.text.take(phrase_pattern(value))

    def collect_sensitive(self) -> list[ValidationFinding]:
        """Emails and phones are masked now so their digits are not read as amounts;
        their findings are added at the end to keep the fixed order."""
        before = len(self.findings)
        for _ in self.text.take(_EMAIL):
            self.add(
                FindingCode.SENSITIVE_DATA,
                "The draft contains an email address.",
                kind="email_address",
            )
        # Dates first, so "2026-11-24" is never read as a phone number.
        masked_dates = self.text.masked
        for pattern in _DATE_PATTERNS[:2]:
            for match in pattern.finditer(masked_dates):
                masked_dates = _blank(masked_dates, match.start(), match.end())
        allowed = self._allowed_phone_digits()
        for match in _PHONE.finditer(masked_dates):
            digits = _digits(match.group())
            if len(digits) < self.config.phone_min_digits:
                continue
            self.text.masked = _blank(self.text.masked, match.start(), match.end())
            if digits not in allowed:
                self.add(
                    FindingCode.SENSITIVE_DATA,
                    "The draft contains a phone number that is not the support number.",
                    kind="phone_number",
                    digit_count=len(digits),
                )
        found = self.findings[before:]
        del self.findings[before:]
        return found

    def check_offers_ids(self) -> None:
        configured = {offer.offer_id for offer in self.policy.offers.offers}
        eligible = (
            self.facts.offer.offer_id if self.facts and self.facts.offer else None
        )
        seen: set[str] = set()
        for match in list(_OFFER_ID.finditer(self.text.masked)):
            token = match.group()
            offer_id = token.upper()
            looks_like_id = offer_id in configured or (
                token == offer_id and any(ch.isdigit() for ch in token)
            )
            if not looks_like_id:
                continue  # ordinary hyphenated words such as "thank-you"
            self.text.masked = _blank(self.text.masked, match.start(), match.end())
            if offer_id in seen:
                continue
            seen.add(offer_id)
            if offer_id == eligible:
                continue
            if offer_id in configured:
                self.add(
                    FindingCode.INELIGIBLE_OFFER,
                    f"Offer {offer_id} is not the offer this customer is eligible for.",
                    offer_id=offer_id,
                    eligible_offer_id=eligible,
                )
            else:
                self.add(
                    FindingCode.UNKNOWN_OFFER,
                    f"Offer {offer_id} is not a configured offer.",
                    offer_id=offer_id,
                )

    def check_dates(self) -> None:
        allowed = self._allowed_dates()
        for pattern in _DATE_PATTERNS:
            for match in self.text.take(pattern):
                if not self._date_matches(match, allowed):
                    self.add(
                        FindingCode.DATE_MISMATCH,
                        "A date in the draft is not the due date or offer expiry.",
                        found=match.group(),
                        allowed=", ".join(d.isoformat() for d in allowed) or None,
                    )

    @staticmethod
    def _date_matches(match: re.Match[str], allowed: list[date]) -> bool:
        month_text = match.group("month")
        month = (
            int(month_text)
            if month_text.isdigit()
            else _MONTHS[month_text.lower().rstrip(".")]
        )
        day = int(match.group("day"))
        year_text = match.groupdict().get("year")
        if year_text is None:
            return any((d.month, d.day) == (month, day) for d in allowed)
        try:
            found = date(int(year_text), month, day)
        except ValueError:
            return False
        return found in allowed

    def check_numbers(self) -> None:
        facts = self.facts
        reminder = facts.reminder if facts else None
        offer = facts.offer if facts else None
        by_unit: dict[str, list[Decimal]] = {
            "percent": [],
            "gb": [],
            "currency": [],
            "plain": [],
        }
        if reminder is not None:
            by_unit["currency"].append(reminder.amount_due)
            by_unit["plain"] += [reminder.amount_due, Decimal(reminder.days_overdue)]
        if offer is not None:
            unit = {"percent": "percent", "gb": "gb", "inr": "currency"}[offer.unit]
            by_unit[unit].append(offer.value)
            by_unit["plain"].append(offer.value)

        markers = sorted(self.config.currency_markers, key=len, reverse=True)
        marker = "|".join(re.escape(m) for m in markers)
        before = re.compile(rf"(?<!\w)(?:{marker})\s*$", re.IGNORECASE)
        after = re.compile(rf"^\s*(?:{marker})(?!\w)", re.IGNORECASE)

        masked = self.text.masked
        for match in _NUMBER.finditer(masked):
            raw = match.group().rstrip(",")
            value = _decimal(raw)
            rest = masked[match.start() + len(raw) :]
            unit_match = _UNIT_AFTER.match(rest)
            if unit_match:
                unit = "gb" if unit_match.group(3) else "percent"
            elif before.search(masked[: match.start()]) or after.match(rest):
                unit = "currency"
            else:
                unit = "plain"
            if value is None or value not in by_unit[unit]:
                self.add(
                    FindingCode.AMOUNT_MISMATCH,
                    "A number in the draft does not match the verified facts.",
                    found=raw,
                    unit=unit,
                    allowed=", ".join(str(v) for v in by_unit[unit]) or None,
                )

    def check_claims(self) -> None:
        reasons = [
            r for r in self.decision.block_reasons if r not in _BLOCK_REASON_CODES
        ]
        for reason in reasons:
            self.add(
                FindingCode.UNSUPPORTED_CLAIM,
                "Outreach is blocked for this customer; no verified facts support a draft.",
                block_reason=reason.value,
            )
        if self.facts is not None and self.facts.offer is not None:
            return
        terms = [
            term
            for term in self.config.offer_claim_terms
            if phrase_pattern(term).search(self.text.masked)
        ]
        if terms:
            self.add(
                FindingCode.UNSUPPORTED_CLAIM,
                "The draft mentions an offer or discount, but none is approved.",
                terms=", ".join(terms),
            )

    def check_blocked_terms(self) -> None:
        for term in blocked_terms_in(self.text.full, self.policy.blocked_terms.terms):
            self.add(
                FindingCode.BLOCKED_TERM,
                f"The draft contains the blocked term {term!r}.",
                term=term,
            )

    def check_support_path(self) -> None:
        if self.facts is None or self.facts.reminder is None:
            return
        if _normalise(self.facts.reminder.support_path) not in _normalise(
            self.text.body
        ):
            self.add(
                FindingCode.MISSING_SUPPORT_PATH,
                "A payment reminder must include the support and dispute path verbatim.",
            )

    def check_decision_gates(self) -> None:
        for reason in self.decision.block_reasons:
            code = _BLOCK_REASON_CODES.get(reason)
            if code is not None:
                self.add(
                    code,
                    f"Outreach is blocked for this customer ({reason.value}).",
                    block_reason=reason.value,
                )


def validate_draft(
    draft: DraftContent, decision: PolicyDecision, policy: Policy
) -> ValidationResult:
    """Run every check; ``passed`` is true exactly when nothing blocking was found."""
    findings = _Checker(draft, decision, policy).run()
    return ValidationResult(
        passed=not any(f.severity is Severity.BLOCKING for f in findings),
        findings=findings,
        checks_run=list(FindingCode),
        validator_version=validator_version(policy),
    )


def blocked_terms_in(text: str, terms: Iterable[str]) -> list[str]:
    """Blocked terms present in ``text`` (whole word/phrase, case-insensitive)."""
    return [term for term in terms if phrase_pattern(term).search(text)]
