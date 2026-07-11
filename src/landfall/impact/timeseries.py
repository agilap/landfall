"""Per-timestep cumulative damage — the engine half of Landfall Viz Tier 2 (PRD §6, §7 Phase 3).

Damage is NOT additive over time: a building destroyed at landfall is not destroyed again an
hour later. The only definition of "cumulative damage at frame i" that is physically correct
*and* reconciles with the validated single-pass number is:

    ImpactCalc applied to the elementwise RUNNING MAX of the wind field over track positions
    0..i (running max per grid cell, monotonic non-decreasing across frames).

At the final frame — running max over ALL resampled track positions — that wind field is
mathematically identical to the single max-swath field `hazard.wind.wind_field()` already
produces (verified 0.0 max abs diff after the 17.5 m/s intensity threshold). So the final
frame's cumulative damage MUST equal `impact.engine.run()`'s `total_damage_usd` to
floating-point precision. That identity is this module's exit test and is self-checked at
cache-write time (`run_timeseries` raises if it fails — a result that violates its own
invariant is never cached).

This is deliberately NOT instantaneous-damage-summed-over-time: summing per-timestep damage
would double-count the same destroyed assets and cannot reconcile with the single-pass figure.

Scope (PRD §6): the POINT estimate only (q=0.5) is animated per frame. The low/high EDR range
(q=0.25/0.75) is a single-pass, whole-storm uncertainty figure already in the scenario cache
(`total_damage_usd_range`) and damage.json; recomputing it per frame would triple the CLIMADA
runs per frame for a number the viz shows statically, not animated. Affected-population is
likewise single-pass only — it is not a running-max quantity and is out of Phase 3 scope.
"""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from climada.engine import ImpactCalc
from climada.entity.impact_funcs.trop_cyclone import ImpfSetTropCyclone

from landfall.hazard.tracks import get_track
from landfall.hazard.wind import WIND_TIMESTEP_H, resample_track_hazard, wind_field_timeseries
from landfall.impact.engine import (
    CACHE_DIR as IMPACT_CACHE_DIR,
    IMPF_CALIBRATION_APPROACH,
    IMPF_POINT_QUANTILE,
    PHILIPPINES_IMPF_ID,
    _cache_key,
    run,
)
from landfall.impact.municipality import damage_by_municipality
from landfall.exposure.hybrid import asset_exposure
from landfall.scenario import ScenarioConfig, perturb_track
from landfall.storms import STORMS

CACHE_DIR = IMPACT_CACHE_DIR.parent / "timeseries"

# Frame cadence: subsample the ROI-transit window (positions where the storm produces any
# >= intensity_thres wind in the ROI) so the frame count never exceeds MAX_FRAMES. Stride
# N = ceil(window_len / MAX_FRAMES), giving ceil(window_len / N) <= MAX_FRAMES frames; a
# storm whose transit window is <= MAX_FRAMES resampled 0.5h steps animates every step (a
# very fast, short transit thus yields fewer than MAX_FRAMES frames — disclosed per storm in
# the output). The final frame is ALWAYS the running max over ALL resampled positions (not
# just the subsampled ones), so subsampling can never drop the true peak from the reconciling
# frame. Target band is ~40-80 frames; the cap fixes the upper bound, the lower bound floats
# with how many 0.5h steps the storm actually spends over the ROI.
MAX_FRAMES = 80
FRAME_CADENCE_RULE = (
    f"subsample the ROI-transit window (positions with any >=17.5 m/s wind in the ROI) at "
    f"stride N = max(1, ceil(window_len / {MAX_FRAMES})), capping the frame count at {MAX_FRAMES}; "
    f"the final frame is forced to the running max over ALL resampled positions so it equals the "
    f"full max-swath exactly"
)

# Final-frame vs single-pass baseline: the two wind fields are bit-identical (running max of the
# stored per-position vectors == the collapsed intensity, 0.0 abs diff), so the reconciliation
# difference is expected to be ~0. $1.00 is far below any material significance for the
# billion-USD totals and leaves headroom for any last-bit float noise from the double norm.
RECONCILE_TOLERANCE_USD = 1.0


def _timeseries_cache_key(scenario: ScenarioConfig, storm_config) -> str:
    """Keyed on everything the impact `_cache_key` folds in (calibration, ROI, wind timestep,
    scenario fields) PLUS the frame cadence — changing MAX_FRAMES changes which frames exist,
    so it must invalidate the cache the same way a calibration change invalidates the impact
    cache (see engine._cache_key's docstring for that discipline)."""
    fingerprint = {
        "impact_cache_key": _cache_key(scenario, storm_config),
        "max_frames": MAX_FRAMES,
    }
    canonical = json.dumps(fingerprint, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _frame_positions(active_first: int, active_last: int) -> list[int]:
    """Subsampled resampled-track position indices spanning the transit window, per
    FRAME_CADENCE_RULE. `active_last` is always the final entry (it carries the full running
    max) even when the stride would step past it."""
    window_len = active_last - active_first + 1
    stride = max(1, -(-window_len // MAX_FRAMES))  # ceil(window_len / MAX_FRAMES)
    positions = list(range(active_first, active_last + 1, stride))
    if positions[-1] != active_last:
        positions.append(active_last)
    return positions


def _position_magnitudes(windfields: sparse.csr_matrix, ncentroids: int, i: int) -> np.ndarray:
    """Wind-speed magnitude at every centroid for track position `i`, from the stored
    per-position velocity vectors (shape (npositions, ncentroids*2) -> (ncentroids, 2))."""
    row = windfields.getrow(i).toarray().reshape(ncentroids, 2)
    return np.linalg.norm(row, axis=1)


def run_timeseries(scenario: ScenarioConfig, use_cache: bool = True) -> dict:
    storm_config = STORMS[scenario.storm_key]
    cache_path = CACHE_DIR / f"{_timeseries_cache_key(scenario, storm_config)}.json"
    if use_cache and cache_path.exists():
        return json.loads(cache_path.read_text())

    # The single-pass baseline this timeseries must reconcile against (cache hit if already run).
    baseline = run(scenario, use_cache=use_cache)
    baseline_total = baseline["total_damage_usd"]
    baseline_by_muni = {
        (r["province"], r["municipality"]): r["damage_usd"] for r in baseline["damage_by_municipality"]
    }

    tracks = get_track(scenario.storm_key)
    if not scenario.is_historical_baseline():
        tracks = perturb_track(tracks, scenario)

    wind = wind_field_timeseries(tracks, storm_config.roi_bounds)
    resampled = resample_track_hazard(tracks)  # same densification wind used, for per-frame track coords
    track = resampled.data[0]

    ncentroids = wind.centroids.lat.size
    windfields = wind.windfields[0]
    npositions = windfields.shape[0]
    intensity_thres = 17.5

    # One pass over all positions: maintain the elementwise running max, snapshot at frame
    # positions. Which positions are "active" (storm producing damaging wind in the ROI) is
    # found on the same pass.
    thresholded_mag = []
    active = []
    for i in range(npositions):
        mag = _position_magnitudes(windfields, ncentroids, i)
        thresholded = np.where(mag >= intensity_thres, mag, 0.0)
        thresholded_mag.append(thresholded)
        if thresholded.any():
            active.append(i)

    if not active:
        raise ValueError(
            f"{scenario.storm_key}: no track position produces >= {intensity_thres} m/s wind in the "
            f"ROI — cannot build a damage timeseries (this should have been caught by ROICoverageError)."
        )
    frame_positions = _frame_positions(active[0], active[-1])
    final_frame_pos = frame_positions[-1]

    impf_set = ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(
        calibration_approach=IMPF_CALIBRATION_APPROACH, q=IMPF_POINT_QUANTILE
    )
    asset_exp = asset_exposure(storm_config.roi_bounds)
    asset_exp.gdf["impf_TC"] = PHILIPPINES_IMPF_ID

    frame_set = set(frame_positions)
    running = np.zeros(ncentroids)
    snapshots: dict[int, np.ndarray] = {}
    for i in range(npositions):
        running = np.maximum(running, thresholded_mag[i])
        if i in frame_set:
            snapshots[i] = running.copy()
    # The final frame must be the running max over ALL resampled positions (== full max-swath),
    # even if the last active position sits before npositions-1.
    snapshots[final_frame_pos] = running.copy()

    frames = []
    for pos in frame_positions:
        frame_wind = snapshots[pos]
        frame_tc = copy.copy(wind)
        frame_tc.intensity = sparse.csr_matrix(frame_wind.reshape(1, -1))
        frame_tc.fraction = sparse.csr_matrix(frame_tc.intensity.shape)
        impact = ImpactCalc(asset_exp, impf_set, frame_tc).impact()
        damage_per_point = impact.imp_mat[0].toarray().flatten()
        by_muni = damage_by_municipality(asset_exp, damage_per_point, storm_config.roi_bounds)
        frames.append(
            {
                "frame_index": pos,
                "time": np.datetime_as_string(track.time.values[pos], unit="s") + "Z",
                "cumulative_total_damage_usd": float(impact.at_event[0]),
                "cumulative_damage_by_municipality": by_muni.to_dict(orient="records"),
                "track_lat": float(track.lat.values[pos]),
                "track_lon": float(track.lon.values[pos]),
                "track_vmax_kn": float(track.max_sustained_wind.values[pos]),
            }
        )

    final = frames[-1]
    difference = final["cumulative_total_damage_usd"] - baseline_total
    within_rounding = abs(difference) <= RECONCILE_TOLERANCE_USD
    reconcile = {
        "baseline_total_damage_usd": baseline_total,
        "final_frame_total_damage_usd": final["cumulative_total_damage_usd"],
        "difference": difference,
        "tolerance_usd": RECONCILE_TOLERANCE_USD,
        "within_rounding": within_rounding,
    }

    result = {
        "scenario_hash": scenario.scenario_hash(),
        "scenario": scenario.model_dump(),
        "wind_timestep_h": WIND_TIMESTEP_H,
        "max_frames": MAX_FRAMES,
        "frame_cadence_rule": FRAME_CADENCE_RULE,
        "frame_count": len(frames),
        "calibration_approach": IMPF_CALIBRATION_APPROACH,
        "calibration_point_quantile": IMPF_POINT_QUANTILE,
        "frames": frames,
        "final_frame_reconciles_with_baseline": reconcile,
    }

    if not within_rounding:
        # Fail loud, do NOT cache a result that violates its own reconciliation invariant
        # (CLAUDE.md: "Fail loud, not plausible"; PRD §6: reconciliation is the exit test).
        raise ValueError(
            f"{scenario.storm_key}: final-frame cumulative damage {final['cumulative_total_damage_usd']:.2f} "
            f"does not reconcile with single-pass baseline {baseline_total:.2f} "
            f"(difference {difference:.2f} USD > tolerance {RECONCILE_TOLERANCE_USD:.2f}). "
            f"This is a real finding about running-max-vs-single-pass impact, not a rounding artifact — "
            f"do not widen the tolerance to force it green; investigate before proceeding (PRD §6 fallback)."
        )

    # Per-municipality final-frame reconciliation is verified in the test suite (against
    # damage.json); the total identity above is the write-time gate.
    _ = baseline_by_muni

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, indent=2))
    return result


def run_timeseries_baseline(storm_key: str, use_cache: bool = True) -> dict:
    return run_timeseries(ScenarioConfig(storm_key=storm_key), use_cache=use_cache)


def frame_wind_grids(scenario: ScenarioConfig, wind) -> list[dict]:
    """Per-frame running-max wind fields (the raster arrays the viz paints), aligned 1:1 with
    `run_timeseries`'s cached damage frames by `frame_index`. Numbers-free by the export
    discipline: this is a deterministic re-derivation of the hazard field (like export_viz's
    max_swath), not a new damage figure. Returns, per frame, the centroid-ordered running-max
    wind values plus lat/lon so export_viz can grid them.

    `wind` MUST be the same `wind_field_timeseries(...)` TropCyclone (store_windfields=True) the
    caller already computed for this scenario -- passed in rather than recomputed here so the
    export makes exactly ONE `get_track`/`from_tracks` call per process. Opening the same
    IBTrACS netCDF a second time in one process segfaults HDF5 (observed), and recomputing the
    windfield twice is wasteful regardless.

    The grids are kept out of the timeseries cache on purpose: the cache holds the damage
    *numbers*; the wind grids are large and rebuilt at export time from the windfield, exactly
    as max_swath.json already is."""
    ts = run_timeseries(scenario)
    frame_positions = [f["frame_index"] for f in ts["frames"]]
    final_frame_pos = frame_positions[-1]

    ncentroids = wind.centroids.lat.size
    windfields = wind.windfields[0]
    npositions = windfields.shape[0]

    frame_set = set(frame_positions)
    running = np.zeros(ncentroids)
    snapshots: dict[int, np.ndarray] = {}
    for i in range(npositions):
        mag = _position_magnitudes(windfields, ncentroids, i)
        running = np.maximum(running, np.where(mag >= 17.5, mag, 0.0))
        if i in frame_set:
            snapshots[i] = running.copy()
    snapshots[final_frame_pos] = running.copy()

    lats = wind.centroids.lat
    lons = wind.centroids.lon
    return [
        {"frame_index": pos, "lats": lats, "lons": lons, "values": snapshots[pos]}
        for pos in frame_positions
    ]


if __name__ == "__main__":
    import sys

    for storm_key in sys.argv[1:] or STORMS.keys():
        result = run_timeseries_baseline(storm_key)
        rec = result["final_frame_reconciles_with_baseline"]
        print(
            f"--- {storm_key} --- frames={result['frame_count']} "
            f"reconcile_diff={rec['difference']:.6f} within_rounding={rec['within_rounding']}"
        )
