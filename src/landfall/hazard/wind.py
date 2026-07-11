"""Storm-generic wind-field synthesis from a TCTracks track.

Counterfactual perturbation (track offset / intensity delta) is Phase 3.
"""

import copy

from climada.hazard import Centroids, TCTracks, TropCyclone

ARCSEC_150_IN_DEG = 150 / 3600  # ~0.04167°, ~4.5 km at this latitude, per PRD §5.1

# v1.4 two-eye fix: IBTrACS tracks are 3-hourly, so the eye moves ~46-98 km/step (Rolly)
# while the compact eyewall RMW is as small as ~9-20 km. CLIMADA's from_tracks paints one
# wind snapshot per native track point and takes the per-cell max with NO interpolation
# between points, so at native cadence the eyewall footprints don't overlap and the swath
# breaks into discrete high-wind rings with low-wind gaps between them (Rolly's >=33 m/s
# swath split into 4 disconnected blobs; see docs/v1.4-phase1-result.md). Resampling the
# track to a fine even timestep before from_tracks closes the gap. 0.5 h is the coarsest
# step tested that fully closes it even on the fastest, most compact segment: at Rolly's
# peak forward speed (~32.6 km/h) 0.5 h gives ~16 km eye spacing, below ~2x the compact
# eyewall radius, and the >=33 m/s hi-wind cell count has converged (native->1.0h->0.5h
# ->0.25h = 349->743->812->831; the +9% from 1.0->0.5 vs +2% from 0.5->0.25 shows 1.0h
# still under-fills fast segments). The timestep is folded into the impact cache key
# (engine._cache_key) so changing it invalidates stale caches rather than serving them.
WIND_TIMESTEP_H = 0.5


def roi_centroids(bounds: tuple[float, float, float, float], res_deg=ARCSEC_150_IN_DEG) -> Centroids:
    return Centroids.from_pnt_bounds(bounds, res_deg)


def resample_track_hazard(tracks: TCTracks) -> TCTracks:
    """Deep-copy `tracks` and densify to WIND_TIMESTEP_H — the v1.4 two-eye fix (see the
    WIND_TIMESTEP_H comment for why sub-hourly resampling is required before from_tracks).

    Returns a new object; the caller's track keeps its observed cadence. equal_timestep()
    mutates in place, and wind_field's caller (export_viz.export_scenario) writes track.json
    from the same tracks object right after — densifying it in place would silently turn the
    exported "raw observed IBTrACS track" into a sub-hourly interpolation we never observed.
    Densification is a hazard-internal step, so it happens on a copy here. The impact
    timeseries (impact/timeseries.py) shares this exact resampling so its running-max wind
    reconciles with wind_field's single max-swath to floating-point precision."""
    tracks = copy.deepcopy(tracks)
    tracks.equal_timestep(time_step_h=WIND_TIMESTEP_H)
    return tracks


def _tc_from_tracks(tracks: TCTracks, bounds, store_windfields: bool) -> TropCyclone:
    tracks = resample_track_hazard(tracks)
    centroids = roi_centroids(bounds)
    # ignore_distance_to_coast: CLIMADA's default coastal filter needs a NASA raster
    # download that is currently blocked (403) from this network. Revisit once that's
    # resolved — until then this computes wind everywhere in the ROI, not just near-coast.
    return TropCyclone.from_tracks(
        tracks, centroids, model="H1980", ignore_distance_to_coast=True, store_windfields=store_windfields
    )


def wind_field(tracks: TCTracks, bounds: tuple[float, float, float, float]) -> TropCyclone:
    """Holland (1980) max-sustained-wind field, per PRD §5.1 — no custom meteorology."""
    return _tc_from_tracks(tracks, bounds, store_windfields=False)


def wind_field_timeseries(tracks: TCTracks, bounds: tuple[float, float, float, float]) -> TropCyclone:
    """Same field as `wind_field`, but with `store_windfields=True` so the per-position wind
    vectors are retained (TropCyclone.windfields). The elementwise running max of those
    per-position vector magnitudes, thresholded at intensity_thres (17.5 m/s), equals
    `wind_field`'s collapsed `intensity` at the final position — verified 0.0 max abs diff.
    Used by impact/timeseries.py to compute cumulative damage frame by frame."""
    return _tc_from_tracks(tracks, bounds, store_windfields=True)
