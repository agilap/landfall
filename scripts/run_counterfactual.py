"""Phase 3 DoD: a counterfactual run end-to-end against its historical baseline.

Usage: python scripts/run_counterfactual.py <storm_key> <offset_km> <bearing_deg> [intensity_delta_kn]
Example: python scripts/run_counterfactual.py haiyan 100 0
  ("Haiyan, 100 km north" — bearing 0 = due north)
"""

import sys

from landfall.impact.engine import run, run_baseline
from landfall.scenario import ScenarioConfig

if __name__ == "__main__":
    storm_key = sys.argv[1]
    offset_km = float(sys.argv[2])
    bearing_deg = float(sys.argv[3])
    intensity_delta_kn = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0

    baseline = run_baseline(storm_key)
    counterfactual = run(
        ScenarioConfig(
            storm_key=storm_key,
            track_offset_km=offset_km,
            track_bearing_deg=bearing_deg,
            intensity_delta_kn=intensity_delta_kn,
        )
    )

    print("--- historical baseline ---")
    print(f"total_damage_usd: {baseline['total_damage_usd']:,.2f}")
    print(f"affected_population: {baseline['affected_population']:,.0f}")

    print("--- counterfactual ---")
    print(f"total_damage_usd: {counterfactual['total_damage_usd']:,.2f}")
    print(f"affected_population: {counterfactual['affected_population']:,.0f}")

    damage_ratio = counterfactual["total_damage_usd"] / baseline["total_damage_usd"]
    pop_ratio = counterfactual["affected_population"] / baseline["affected_population"]
    print("--- comparison ---")
    print(f"damage ratio (counterfactual / baseline): {damage_ratio:.3f}")
    print(f"affected population ratio: {pop_ratio:.3f}")
