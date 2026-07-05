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
    "trillion": 1e12,
    # single-letter abbreviations, applied ONLY when the number is currency-prefixed and
    # the letter is directly attached (see _NUMBER_RE / _token_value below)
    "k": 1e3,
    "m": 1e6,
    "b": 1e9,
    "t": 1e12,
}

# Matches things like "49,327,691.86", "49.3 million", "49.3million", "49.3-million",
# "9,168,006", "1,081,467 people", "2.5 trillion", and currency-abbreviated forms like
# "$49.3M" / "₱1.2B".
#
# The single-letter suffix (M/B/K/T) counts as a magnitude ONLY when the number carries a
# currency prefix ($/₱) AND the letter is directly attached (no space). Both guards are
# load-bearing against real NDRRMC-corpus false positives, confirmed by scanning it:
#   - bare "20m", "3.8m" mean *metres* in road-damage tables (dozens of them) — excluded
#     by requiring a currency prefix;
#   - "₱2,229,439.00 b" is a complete peso amount followed by a list-marker "b." — excluded
#     by requiring the suffix be attached (no space), while the real "₱400M" is kept.
# The remaining gap is deliberate: an un-prefixed "49.3M USD" still reads as 49.3, because
# a bare "m" cannot be safely disambiguated from metres in this corpus. See tests.
_NUMBER_RE = re.compile(
    r"(?P<cur>[$₱])?"
    r"(?P<num>\d[\d,]*\.?\d*)"
    r"(?:[\s-]*(?P<word>thousand|million|billion|trillion)"
    r"|(?P<abbr>[MBKT])\b)?",
    re.IGNORECASE,
)


def _token_value(match: re.Match) -> float | None:
    """The numeric value of one _NUMBER_RE match, applying a magnitude multiplier when a
    spelled-out word follows, or a single-letter suffix follows a currency-prefixed number.
    Returns None for a degenerate token (e.g. a lone "." matched as digits)."""
    raw = match.group("num").replace(",", "")
    if raw in ("", "."):
        return None
    value = float(raw)
    word = match.group("word")
    abbr = match.group("abbr")
    if word:
        value *= _MAGNITUDE_WORDS[word.lower()]
    elif abbr and match.group("cur"):
        value *= _MAGNITUDE_WORDS[abbr.lower()]
    return value


@dataclass
class GroundednessReport:
    total_claims: int
    grounded_claims: int
    ungrounded: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.grounded_claims / self.total_claims if self.total_claims else 1.0


def extract_numbers(text: str) -> list[float]:
    values = []
    for match in _NUMBER_RE.finditer(text):
        value = _token_value(match)
        if value is not None:
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
    found = extract_numbers(text)
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
        value = _token_value(match)
        if value is None:
            return match.group(0)
        if value >= 100 and not _is_grounded(value, reference_values):
            return "[REDACTED]"
        return match.group(0)

    redacted_text = _NUMBER_RE.sub(_replace, text)
    return redacted_text, check(redacted_text, reference_values)
