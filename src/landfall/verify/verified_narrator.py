"""Ties the narrator and groundedness verifier together: regenerate on failure, then
redact anything still ungrounded, logging every redaction rather than silently dropping it.
"""

import logging

from landfall.llm.narrator import narrate
from landfall.verify.groundedness import GroundednessReport, check, redact_ungrounded

logger = logging.getLogger(__name__)

MAX_REGENERATE_ATTEMPTS = 2


def narrate_verified(
    scenario_description: str,
    damage_low_usd: float,
    damage_high_usd: float,
    affected_population: float,
    permitted_values: list[float] | None = None,
) -> tuple[str, GroundednessReport, GroundednessReport]:
    """Returns (final_text, raw_report, final_report).

    raw_report is the groundedness of the *first* draft, before any regeneration or
    redaction — this is what E2's "baseline hallucination rate" is measured from.
    final_report is the groundedness of what's actually returned, after the verifier
    has done its job (should be ~100% by construction, since redaction forces it).

    Damage is a low/high range (v1.2 Phase 1, see docs/v1.2-phase1-result.md), not a
    point estimate — both bounds are permitted reference values, but nothing between
    them is: a stated figure the model computed by averaging the two (or any other
    value) is exactly the kind of invented statistic this verifier exists to catch.

    `permitted_values` covers numbers the prompt explicitly allows beyond the two core
    figures — e.g. the storm's year, which the system prompt tells the model it may
    state. These aren't "load-bearing" claims requiring traceability to impact-engine
    output, just legitimate context, so they're added to the allowed set rather than
    exempted by a magnitude heuristic (which doesn't work for 4-digit years anyway).
    """
    reference_values = [damage_low_usd, damage_high_usd, affected_population] + list(permitted_values or [])

    text = narrate(scenario_description, damage_low_usd, damage_high_usd, affected_population)
    raw_report = check(text, reference_values)

    report = raw_report
    for attempt in range(MAX_REGENERATE_ATTEMPTS):
        if not report.ungrounded:
            return text, raw_report, report
        logger.info("regenerating (attempt %d): ungrounded=%s", attempt + 1, report.ungrounded)
        text = narrate(scenario_description, damage_low_usd, damage_high_usd, affected_population)
        report = check(text, reference_values)

    if report.ungrounded:
        logger.warning("redacting after %d failed regenerations: %s", MAX_REGENERATE_ATTEMPTS, report.ungrounded)
        text, report = redact_ungrounded(text, reference_values)

    return text, raw_report, report
