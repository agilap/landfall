"""Storm-generic wind-field synthesis from a TCTracks track.

Counterfactual perturbation (track offset / intensity delta) is Phase 3.
"""

from climada.hazard import Centroids, TCTracks, TropCyclone

ARCSEC_150_IN_DEG = 150 / 3600  # ~0.04167°, ~4.5 km at this latitude, per PRD §5.1


def roi_centroids(bounds: tuple[float, float, float, float], res_deg=ARCSEC_150_IN_DEG) -> Centroids:
    return Centroids.from_pnt_bounds(bounds, res_deg)


def wind_field(tracks: TCTracks, bounds: tuple[float, float, float, float]) -> TropCyclone:
    """Holland (1980) max-sustained-wind field, per PRD §5.1 — no custom meteorology."""
    centroids = roi_centroids(bounds)
    # ignore_distance_to_coast: CLIMADA's default coastal filter needs a NASA raster
    # download that is currently blocked (403) from this network. Revisit once that's
    # resolved — until then this computes wind everywhere in the ROI, not just near-coast.
    return TropCyclone.from_tracks(tracks, centroids, model="H1980", ignore_distance_to_coast=True)
