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

# v1.1 Phase 3: hybrid replaces pure LitPop -- OSM buildings + PSA census population
# for Catanduanes/Albay/Camarines Sur, LitPop everywhere else. See
# docs/v1.1-phase3-result.md for why (LitPop's nightlights weighting undervalues rural
# Bicol) and what this doesn't resolve (uneven OSM mapping completeness by province).
from landfall.exposure.hybrid import asset_exposure, population_exposure
from landfall.hazard.tracks import get_track
from landfall.hazard.wind import wind_field
from landfall.impact.municipality import affected_population_by_municipality, damage_by_municipality
from landfall.scenario import ScenarioConfig, perturb_track
from landfall.storms import STORMS

PHILIPPINES_IMPF_ID = 7  # WP2 region, Eberenz et al. 2021 — see ImpfSetTropCyclone lookup
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "scenarios"


class ROICoverageError(ValueError):
    """Raised when a perturbed track leaves the storm's fixed ROI grid entirely (wind
    intensity is 0 everywhere in it), found by directly sweeping track_offset_km for all
    four storms (see docs/v1.3-phase2-result.md). `roi_bounds` is a static box per storm
    (landfall/storms.py) sized to the *historical* track — it is never re-derived for a
    counterfactual. A large enough offset can push the storm's core (or all of it, for
    Rolly's notably small 3.5°x3° box, at just 150km — 30% of the compiler's own 500km
    max) outside that box, and the engine would otherwise silently return $0 damage and
    0 affected population: a number that looks exactly like a legitimate cached result
    (passes the groundedness verifier fine, since 0 *is* what got cached) but actually
    means "the grid never looked at where the storm went," not "this counterfactual
    causes no damage." Failing loud here instead of downstream is PRD §4.2's principle,
    applied to the physics layer rather than just the compiler's input schema."""


def _check_roi_coverage(wind, storm_key: str, storm_config, scenario: ScenarioConfig) -> None:
    if wind.intensity.max() == 0:
        raise ROICoverageError(
            f"This counterfactual (offset {scenario.track_offset_km:.0f} km at bearing "
            f"{scenario.track_bearing_deg:.0f}°) moves {storm_key.title()}'s track entirely "
            f"outside its fixed region of interest {storm_config.roi_bounds} — no wind "
            f"anywhere in the simulated grid. This is a coverage gap, not a genuine "
            f"zero-damage result: try a smaller offset or a different bearing."
        )

# v1.1 Phase 1: RMSF replaced the CLIMADA default of TDR for the WP2 (Philippines)
# calibration -- see docs/v1.1-phase1-result.md. v1.1 Phase 5 then found that no single
# v_half can fit Haiyan/Rolly/Odette simultaneously: their pre-existing TDR-era deficits
# (18.6x, 575x, 2.5-5x under) are too far apart for one point-estimate curve to close
# without overshooting at least one storm, and Odette did get overshot. See
# docs/v1.1-phase5-result.md.
#
# v1.2 Phase 1: rather than search for a better single v_half, report the genuine
# calibration uncertainty Eberenz et al. 2021 already publish. Their "EDR" approach
# fits v_half individually per historical WP2 event (83 events, 1980-2016) rather than
# to one region-wide aggregate; CLIMADA exposes any quantile of that per-event
# distribution via `calibration_approach="EDR", q=...`. The interquartile range
# (q0.25-q0.75) of that *already-published, already-bundled* distribution brackets all
# three storms' actual recorded damage simultaneously -- the first thing tried across
# v1.1 and v1.2 that works for Haiyan, Rolly, *and* the held-out Odette at once. See
# docs/v1.2-phase1-result.md. This is not a new curve (PRD's non-goal on custom
# fragility curves is unaffected) -- it's a different, still-published quantile
# selection from data CLIMADA already ships.
IMPF_CALIBRATION_APPROACH = "EDR"
IMPF_POINT_QUANTILE = 0.5  # median -- kept for backward-compatible single-number consumers
IMPF_RANGE_QUANTILES = (0.25, 0.75)  # interquartile range reported alongside the point estimate


def run(scenario: ScenarioConfig, use_cache: bool = True) -> dict:
    cache_path = CACHE_DIR / f"{scenario.scenario_hash()}.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text())

    storm_config = STORMS[scenario.storm_key]
    tracks = get_track(scenario.storm_key)
    if not scenario.is_historical_baseline():
        tracks = perturb_track(tracks, scenario)
    wind = wind_field(tracks, storm_config.roi_bounds)
    _check_roi_coverage(wind, scenario.storm_key, storm_config, scenario)

    impf_set = ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(
        calibration_approach=IMPF_CALIBRATION_APPROACH, q=IMPF_POINT_QUANTILE
    )

    asset_exp = asset_exposure(storm_config.roi_bounds)
    asset_exp.gdf["impf_TC"] = PHILIPPINES_IMPF_ID
    damage = ImpactCalc(asset_exp, impf_set, wind).impact()
    damage_per_point = damage.imp_mat[0].toarray().flatten()

    # v_half increases monotonically with quantile, so damage *decreases* with quantile:
    # the lower quantile (steeper curve) gives the higher damage figure and vice versa.
    q_for_high_damage, q_for_low_damage = IMPF_RANGE_QUANTILES  # (0.25, 0.75)
    range_high = ImpactCalc(
        asset_exp,
        ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(
            calibration_approach=IMPF_CALIBRATION_APPROACH, q=q_for_high_damage
        ),
        wind,
    ).impact()
    range_low = ImpactCalc(
        asset_exp,
        ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(
            calibration_approach=IMPF_CALIBRATION_APPROACH, q=q_for_low_damage
        ),
        wind,
    ).impact()

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
        "total_damage_usd_range": {"low": float(range_low.at_event[0]), "high": float(range_high.at_event[0])},
        "affected_population": float(affected_population),
        "impf_id": PHILIPPINES_IMPF_ID,
        "impf_region": "WP2",
        "calibration_approach": IMPF_CALIBRATION_APPROACH,
        "calibration_point_quantile": IMPF_POINT_QUANTILE,
        "calibration_range_quantiles": list(IMPF_RANGE_QUANTILES),
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
