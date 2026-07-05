"""E2 — Narration groundedness (PRD §6).

Generates N >= 50 briefings across a mix of historical-baseline and counterfactual
scenarios for all three replay storms, then reports the percentage of numeric claims
traceable to cached impact-engine output — both raw (no verifier) and after the
verifier's regenerate/redact pass. The gap between those two rows is the thesis.

Requires OPENAI_API_KEY. Run from the `landfall` conda env: python evals/e2_groundedness.py
"""

from landfall.impact.engine import run, run_baseline
from landfall.scenario import ScenarioConfig
from landfall.storms import STORMS
from landfall.verify.verified_narrator import narrate_verified

# 7 scenarios per storm x 3 storms = 21 distinct configs; 3 generations each = 63 briefings.
SCENARIO_VARIANTS = [
    {},  # historical baseline
    {"track_offset_km": 100, "track_bearing_deg": 0},
    {"track_offset_km": 100, "track_bearing_deg": 180},
    {"track_offset_km": 150, "track_bearing_deg": 90},
    {"track_offset_km": 50, "track_bearing_deg": 270},
    {"intensity_delta_kn": 20},
    {"intensity_delta_kn": -20},
]
GENERATIONS_PER_SCENARIO = 3


def _describe(storm_key: str, variant: dict) -> str:
    year = {"haiyan": 2013, "rolly": 2020, "odette": 2021}[storm_key]
    if not variant:
        return f"Historical replay of Typhoon {storm_key.title()} ({year})."
    parts = [f"Counterfactual based on Typhoon {storm_key.title()} ({year}):"]
    if "track_offset_km" in variant:
        parts.append(f"track shifted {variant['track_offset_km']} km at bearing {variant['track_bearing_deg']}°.")
    if "intensity_delta_kn" in variant:
        sign = "+" if variant["intensity_delta_kn"] > 0 else ""
        parts.append(f"intensity changed by {sign}{variant['intensity_delta_kn']} kn.")
    return " ".join(parts)


def main():
    raw_grounded = raw_total = 0
    final_grounded = final_total = 0
    rows = []

    years = {"haiyan": 2013, "rolly": 2020, "odette": 2021}

    for storm_key in STORMS:
        for variant in SCENARIO_VARIANTS:
            config = ScenarioConfig(storm_key=storm_key, **variant)
            result = run_baseline(storm_key) if not variant else run(config)
            description = _describe(storm_key, variant)

            damage_range = result["total_damage_usd_range"]
            for _ in range(GENERATIONS_PER_SCENARIO):
                text, raw_report, final_report = narrate_verified(
                    description,
                    damage_range["low"],
                    damage_range["high"],
                    result["affected_population"],
                    permitted_values=[years[storm_key]],
                )
                raw_grounded += raw_report.grounded_claims
                raw_total += raw_report.total_claims
                final_grounded += final_report.grounded_claims
                final_total += final_report.total_claims
                rows.append(
                    {
                        "storm": storm_key,
                        "variant": variant,
                        "raw_rate": raw_report.rate,
                        "final_rate": final_report.rate,
                        "text": text,
                    }
                )

    print(f"N briefings: {len(rows)}")
    print(f"Raw groundedness (no verifier):    {raw_grounded}/{raw_total} = {raw_grounded / raw_total:.1%}")
    print(f"Final groundedness (with verifier): {final_grounded}/{final_total} = {final_grounded / final_total:.1%}")
    return rows


if __name__ == "__main__":
    main()
