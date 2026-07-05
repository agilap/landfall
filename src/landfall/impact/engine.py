"""Storm-generic hazard -> exposure -> impact run, for any of the three registered storms.

No scenario cache yet — Week 3 introduces that once counterfactuals create more runs to cache.
"""

from climada.engine import ImpactCalc
from climada.entity.impact_funcs.trop_cyclone import ImpfSetTropCyclone

from landfall.exposure.litpop import asset_exposure, population_exposure
from landfall.hazard.tracks import get_track
from landfall.hazard.wind import wind_field
from landfall.storms import STORMS

PHILIPPINES_IMPF_ID = 7  # WP2 region, Eberenz et al. 2021 — see ImpfSetTropCyclone lookup


def run(storm_key: str) -> dict:
    config = STORMS[storm_key]
    tracks = get_track(storm_key)
    wind = wind_field(tracks, config.roi_bounds)

    impf_set = ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(calibration_approach="TDR")

    asset_exp = asset_exposure(config.roi_bounds)
    asset_exp.gdf["impf_TC"] = PHILIPPINES_IMPF_ID
    damage = ImpactCalc(asset_exp, impf_set, wind).impact()

    # Affected-population proxy: population where the hazard grid carries any nonzero
    # (i.e. >= intensity_thres, ~17.5 m/s) wind — not a damage-function-based estimate.
    # Deliberately crude; PRD non-goals exclude casualty modeling.
    pop_exp = population_exposure(config.roi_bounds)
    pop_exp.assign_centroids(wind)
    affected_mask = wind.intensity[0, pop_exp.gdf["centr_TC"]].toarray().flatten() > 0
    affected_population = pop_exp.gdf["value"][affected_mask].sum()

    return {
        "storm": storm_key,
        "total_damage_usd": float(damage.at_event[0]),
        "affected_population": float(affected_population),
        "impf_id": PHILIPPINES_IMPF_ID,
        "impf_region": "WP2",
        "calibration_approach": "TDR",
        "hazard_model": "H1980",
    }


if __name__ == "__main__":
    import sys

    for storm_key in sys.argv[1:] or STORMS.keys():
        result = run(storm_key)
        print(f"--- {storm_key} ---")
        for k, v in result.items():
            print(f"{k}: {v}")
