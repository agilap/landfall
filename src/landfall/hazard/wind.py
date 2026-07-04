"""Visayas wind-field synthesis from a TCTracks track — Week 1 scope, Haiyan only.

Counterfactual perturbation (track offset / intensity delta) is Week 3.
"""

from climada.hazard import Centroids, TCTracks, TropCyclone

ARCSEC_150_IN_DEG = 150 / 3600  # ~0.04167°, ~4.5 km at this latitude, per PRD §5.1

# Visayas region of interest: covers Samar, Leyte, Cebu, Bohol, Negros, Panay —
# the landfall corridor Haiyan's Cat. 5 segment crossed (see haiyan_track.png).
VISAYAS_BOUNDS = (121.5, 8.0, 126.5, 13.0)  # (lon_min, lat_min, lon_max, lat_max)


def visayas_centroids(bounds=VISAYAS_BOUNDS, res_deg=ARCSEC_150_IN_DEG) -> Centroids:
    return Centroids.from_pnt_bounds(bounds, res_deg)


def haiyan_wind_field(tracks: TCTracks, centroids: Centroids | None = None) -> TropCyclone:
    """Holland (1980) max-sustained-wind field, per PRD §5.1 — no custom meteorology."""
    if centroids is None:
        centroids = visayas_centroids()
    # ignore_distance_to_coast: CLIMADA's default coastal filter needs a NASA raster
    # download that is currently blocked (403) from this network. Revisit once that's
    # resolved — until then this computes wind everywhere in the ROI, not just near-coast.
    return TropCyclone.from_tracks(tracks, centroids, model="H1980", ignore_distance_to_coast=True)
