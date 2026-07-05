"""Groundedness verifier: every numeric claim in a narrator draft must trace to cached
impact-engine output, within a declared rounding tolerance, or it gets flagged.

This is the Receipts verification pattern reapplied (PRD §5.2): the prompt telling the
narrator what numbers it may use is not itself a correctness guarantee — an LLM can still
invent or mis-state a figure. This module is the actual enforcement point.
"""

import re
from dataclasses import dataclass, field

RELATIVE_TOLERANCE = 0.01  # 1% — generous enough for natural-language rounding

_MAGNITUDE_WORDS = {
    "thousand": 1e3,
    "million": 1e6,
    "billion": 1e9,
}

# Matches things like "49,327,691.86", "49.3 million", "9,168,006", "1,081,467 people"
_NUMBER_RE = re.compile(
    r"(?P<num>\d[\d,]*\.?\d*)(?:\s+(?P<mag>thousand|million|billion))?",
    re.IGNORECASE,
)


@dataclass
class GroundednessReport:
    total_claims: int
    grounded_claims: int
    ungrounded: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.grounded_claims / self.total_claims if self.total_claims else 1.0


def _extract_numbers(text: str) -> list[float]:
    values = []
    for match in _NUMBER_RE.finditer(text):
        raw = match.group("num").replace(",", "")
        if raw in ("", "."):
            continue
        value = float(raw)
        mag = match.group("mag")
        if mag:
            value *= _MAGNITUDE_WORDS[mag.lower()]
        values.append(value)
    return values


def _is_grounded(value: float, reference_values: list[float]) -> bool:
    for ref in reference_values:
        if ref == 0:
            if value == 0:
                return True
            continue
        if abs(value - ref) / abs(ref) <= RELATIVE_TOLERANCE:
            return True
    return False


def check(text: str, reference_values: list[float]) -> GroundednessReport:
    """Every distinct number extracted from `text` must match one of `reference_values`
    within RELATIVE_TOLERANCE. Small integers (years, single-digit counts) are exempt —
    they're structurally unlikely to be fabricated damage/population claims and the PRD's
    concern is specifically disaster-figure hallucination, not incidental phrasing."""
    found = _extract_numbers(text)
    claims = [v for v in found if v >= 100]  # exempt years/small incidental numbers

    ungrounded = [v for v in claims if not _is_grounded(v, reference_values)]
    return GroundednessReport(
        total_claims=len(claims),
        grounded_claims=len(claims) - len(ungrounded),
        ungrounded=[str(v) for v in ungrounded],
    )


def redact_ungrounded(text: str, reference_values: list[float]) -> tuple[str, GroundednessReport]:
    """Replace any ungrounded numeric token with [REDACTED], logging what was removed.

    The returned report reflects the *redacted* text, not the original draft — every
    ungrounded number was just removed, so this should read as fully grounded (any
    remaining number, by construction, matched a reference value). Use the pre-redaction
    report (e.g. from `check()` beforehand) if you need to log what was actually removed.
    """

    def _replace(match: re.Match) -> str:
        raw = match.group("num").replace(",", "")
        if raw in ("", "."):
            return match.group(0)
        value = float(raw)
        mag = match.group("mag")
        if mag:
            value *= _MAGNITUDE_WORDS[mag.lower()]
        if value >= 100 and not _is_grounded(value, reference_values):
            return "[REDACTED]"
        return match.group(0)

    redacted_text = _NUMBER_RE.sub(_replace, text)
    return redacted_text, check(redacted_text, reference_values)
