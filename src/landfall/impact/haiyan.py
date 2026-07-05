"""Week 1 Session 4: first end-to-end damage number for Haiyan over the Visayas ROI.

No scenario cache yet — that lands in Week 2 once there's more than one run to cache.
"""

from climada.engine import ImpactCalc
from climada.entity.impact_funcs.trop_cyclone import ImpfSetTropCyclone

from landfall.exposure.litpop import visayas_asset_exposure, visayas_population_exposure
from landfall.hazard.tracks import get_haiyan_track
from landfall.hazard.wind import haiyan_wind_field

PHILIPPINES_IMPF_ID = 7  # WP2 region, Eberenz et al. 2021 — see ImpfSetTropCyclone lookup


def run() -> dict:
    tracks = get_haiyan_track()
    wind = haiyan_wind_field(tracks)

    impf_set = ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(calibration_approach="TDR")

    asset_exp = visayas_asset_exposure()
    asset_exp.gdf["impf_TC"] = PHILIPPINES_IMPF_ID
    damage = ImpactCalc(asset_exp, impf_set, wind).impact()

    # Affected-population proxy: population where the hazard grid carries any nonzero
    # (i.e. >= intensity_thres, ~17.5 m/s) wind — not a damage-function-based estimate.
    # Deliberately crude; PRD non-goals exclude casualty modeling, and this is Week 1.
    pop_exp = visayas_population_exposure()
    pop_exp.assign_centroids(wind)
    affected_mask = wind.intensity[0, pop_exp.gdf["centr_TC"]].toarray().flatten() > 0
    affected_population = pop_exp.gdf["value"][affected_mask].sum()

    return {
        "total_damage_usd": float(damage.at_event[0]),
        "affected_population": float(affected_population),
        "impf_id": PHILIPPINES_IMPF_ID,
        "impf_region": "WP2",
        "calibration_approach": "TDR",
        "hazard_model": "H1980",
    }


if __name__ == "__main__":
    result = run()
    for k, v in result.items():
        print(f"{k}: {v}")
