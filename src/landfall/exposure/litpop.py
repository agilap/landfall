"""LitPop exposure, clipped to a storm's ROI — produced-capital value or population count.

Upgrade path to OSM/PSA exposure is deliberately not built here; PRD §5.1 gates that
upgrade behind validation error analysis (this week's E1 table).
"""

from climada.entity import Exposures, LitPop

RES_ARCSEC = 150  # matches the hazard grid resolution, per PRD §5.1


def _clip_to_bounds(exp: Exposures, bounds: tuple[float, float, float, float]) -> Exposures:
    lon_min, lat_min, lon_max, lat_max = bounds
    clipped = exp.copy()
    clipped.data = clipped.gdf.cx[lon_min:lon_max, lat_min:lat_max]
    return clipped


def asset_exposure(bounds: tuple[float, float, float, float], fin_mode: str = "pc") -> Exposures:
    """Produced-capital ('pc') asset exposure for the Philippines, clipped to `bounds`."""
    exp = LitPop.from_countries("PHL", res_arcsec=RES_ARCSEC, fin_mode=fin_mode)
    return _clip_to_bounds(exp, bounds)


def population_exposure(bounds: tuple[float, float, float, float]) -> Exposures:
    """Population-count exposure, same grid — used for the affected-population proxy."""
    return asset_exposure(bounds, fin_mode="pop")
