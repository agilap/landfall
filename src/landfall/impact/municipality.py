"""Per-municipality damage and affected-population breakdown.

PRD §5.1: the impact engine is specified to produce "per-municipality damage estimates
and affected-population counts" — the ROI-wide totals in `engine.run()` alone can't
answer representative queries like "which municipalities in Cebu see the highest housing
damage?" (PRD §3). This module adds that breakdown via a spatial join against GADM
administrative boundaries.

GADM's Philippines hierarchy: ADM_1 = province, ADM_2 = municipality/city (confirmed by
inspection — ADM_2 has 1,647 named units like "Bogo City", "Carcar" under NAME_1="Cebu").
ADM_3 (41,948 units) is barangay-level, too fine for this purpose.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from climada.entity import Exposures
from climada.hazard import TropCyclone

GADM_PATH = Path(__file__).resolve().parents[3] / "data" / "cache" / "gadm" / "gadm41_PHL.gpkg"


def load_municipalities(bounds: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Municipality/city boundaries (GADM ADM_2) intersecting `bounds`."""
    lon_min, lat_min, lon_max, lat_max = bounds
    gdf = gpd.read_file(GADM_PATH, layer="ADM_ADM_2", bbox=bounds)
    return gdf[["NAME_1", "NAME_2", "geometry"]].rename(columns={"NAME_1": "province", "NAME_2": "municipality"})


def _points_gdf(exp: Exposures, values: np.ndarray, value_col: str) -> gpd.GeoDataFrame:
    # Positional alignment, not pandas-index alignment: imp_mat/value arrays are ordered
    # by exposure row position, and exp.gdf may carry a non-contiguous index after the
    # earlier `.cx[]` ROI clip.
    return gpd.GeoDataFrame(
        {value_col: values, "geometry": exp.gdf.geometry.to_numpy()},
        crs=exp.gdf.crs,
    )


def damage_by_municipality(asset_exp: Exposures, damage_imp_mat_row: np.ndarray, bounds: tuple) -> pd.DataFrame:
    points = _points_gdf(asset_exp, damage_imp_mat_row, "damage_usd")
    municipalities = load_municipalities(bounds)
    joined = gpd.sjoin(points, municipalities, how="inner", predicate="within")
    result = joined.groupby(["province", "municipality"], as_index=False)["damage_usd"].sum()
    return result.sort_values("damage_usd", ascending=False).reset_index(drop=True)


def affected_population_by_municipality(
    pop_exp: Exposures, wind: TropCyclone, bounds: tuple
) -> pd.DataFrame:
    intensities = wind.intensity[0, pop_exp.gdf["centr_TC"]].toarray().flatten()
    affected_values = np.where(intensities > 0, pop_exp.gdf["value"].to_numpy(), 0.0)
    points = _points_gdf(pop_exp, affected_values, "affected_population")
    municipalities = load_municipalities(bounds)
    joined = gpd.sjoin(points, municipalities, how="inner", predicate="within")
    result = joined.groupby(["province", "municipality"], as_index=False)["affected_population"].sum()
    return result.sort_values("affected_population", ascending=False).reset_index(drop=True)
