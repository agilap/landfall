"""Hazard -> exposure -> impact run for any registered storm, historical or counterfactual.

Every run is a ScenarioConfig (the historical baseline is just one with zero perturbation)
and every result is cached to disk keyed on the config's hash, per PRD §5.1 — downstream
narration can only ever reference this cached output, never a live recomputation.
"""

import json
import sys
from pathlib import Path

from climada.engine import ImpactCalc
from climada.entity.impact_funcs.trop_cyclone import ImpfSetTropCyclone

from landfall.exposure.litpop import asset_exposure, population_exposure
from landfall.hazard.tracks import get_track
from landfall.hazard.wind import wind_field
from landfall.impact.municipality import affected_population_by_municipality, damage_by_municipality
from landfall.scenario import ScenarioConfig, perturb_track
from landfall.storms import STORMS

PHILIPPINES_IMPF_ID = 7  # WP2 region, Eberenz et al. 2021 — see ImpfSetTropCyclone lookup
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "scenarios"

# v1.1 Phase 1: RMSF replaces the CLIMADA default of TDR for the WP2 (Philippines)
# calibration. Eberenz et al. 2021 (NHESS 21:393-415, https://doi.org/10.5194/nhess-21-393-2021)
# calibrate v_half three ways per region; for WP2-4 specifically they report that TDR
# ("larger weight to events with large damage values... these results indicate that
# these events are systematically overestimated by the model in the regions WP2-4")
# fits an anomalously flat curve (v_half=188.4 m/s) that is near-zero at any wind speed
# a real typhoon reaches. RMSF weights every matched historical event equally
# (v_half=84.7 m/s) instead of letting the region's few largest-damage events dominate
# the fit — see docs/v1.1-phase1-result.md for the E1 before/after this produces,
# including Odette (held out from this decision) flipping from underestimation to
# overestimation under this same curve.
IMPF_CALIBRATION_APPROACH = "RMSF"


def run(scenario: ScenarioConfig, use_cache: bool = True) -> dict:
    cache_path = CACHE_DIR / f"{scenario.scenario_hash()}.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text())

    storm_config = STORMS[scenario.storm_key]
    tracks = get_track(scenario.storm_key)
    if not scenario.is_historical_baseline():
        tracks = perturb_track(tracks, scenario)
    wind = wind_field(tracks, storm_config.roi_bounds)

    impf_set = ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(calibration_approach=IMPF_CALIBRATION_APPROACH)

    asset_exp = asset_exposure(storm_config.roi_bounds)
    asset_exp.gdf["impf_TC"] = PHILIPPINES_IMPF_ID
    damage = ImpactCalc(asset_exp, impf_set, wind).impact()
    damage_per_point = damage.imp_mat[0].toarray().flatten()

    # Affected-population proxy: population where the hazard grid carries any nonzero
    # (i.e. >= intensity_thres, ~17.5 m/s) wind — not a damage-function-based estimate.
    # Deliberately crude; PRD non-goals exclude casualty modeling.
    pop_exp = population_exposure(storm_config.roi_bounds)
    pop_exp.assign_centroids(wind)
    affected_mask = wind.intensity[0, pop_exp.gdf["centr_TC"]].toarray().flatten() > 0
    affected_population = pop_exp.gdf["value"][affected_mask].sum()

    by_municipality = damage_by_municipality(asset_exp, damage_per_point, storm_config.roi_bounds)
    affected_by_municipality = affected_population_by_municipality(pop_exp, wind, storm_config.roi_bounds)

    result = {
        "scenario_hash": scenario.scenario_hash(),
        "scenario": scenario.model_dump(),
        "total_damage_usd": float(damage.at_event[0]),
        "affected_population": float(affected_population),
        "impf_id": PHILIPPINES_IMPF_ID,
        "impf_region": "WP2",
        "calibration_approach": IMPF_CALIBRATION_APPROACH,
        "hazard_model": "H1980",
        "damage_by_municipality": by_municipality.to_dict(orient="records"),
        "affected_population_by_municipality": affected_by_municipality.to_dict(orient="records"),
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, indent=2))
    return result


def run_baseline(storm_key: str, use_cache: bool = True) -> dict:
    return run(ScenarioConfig(storm_key=storm_key), use_cache=use_cache)


if __name__ == "__main__":
    for storm_key in sys.argv[1:] or STORMS.keys():
        result = run_baseline(storm_key)
        print(f"--- {storm_key} ---")
        for k, v in result.items():
            print(f"{k}: {v}")
