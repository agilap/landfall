"""LitPop exposure for the Visayas ROI — Week 1 scope, produced-capital value only.

Upgrade path to OSM/PSA exposure is deliberately not built here; PRD §5.1 gates that
upgrade behind validation error analysis in Week 2.
"""

from climada.entity import Exposures, LitPop

from landfall.hazard.wind import ARCSEC_150_IN_DEG, VISAYAS_BOUNDS

RES_ARCSEC = 150  # matches the hazard grid resolution, per PRD §5.1


def _clip_to_visayas(exp: Exposures, bounds=VISAYAS_BOUNDS) -> Exposures:
    lon_min, lat_min, lon_max, lat_max = bounds
    clipped = exp.copy()
    clipped.data = clipped.gdf.cx[lon_min:lon_max, lat_min:lat_max]
    return clipped


def visayas_asset_exposure(fin_mode: str = "pc") -> Exposures:
    """Produced-capital ('pc') asset exposure for the Philippines, clipped to Visayas."""
    exp = LitPop.from_countries("PHL", res_arcsec=RES_ARCSEC, fin_mode=fin_mode)
    return _clip_to_visayas(exp)


def visayas_population_exposure() -> Exposures:
    """Population-count exposure, same grid — used for the affected-population proxy."""
    return visayas_asset_exposure(fin_mode="pop")
