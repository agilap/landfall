"""Hybrid exposure: OSM building footprints + PSA barangay census population for
Catanduanes, Albay, and Camarines Sur (the three Bicol provinces Rolly/Goni hit);
LitPop everywhere else in a storm's ROI.

v1.1 Phase 3: LitPop distributes national produced-capital value by population x
nightlights (Eberenz et al. 2020), which structurally undervalues low-luminosity rural
areas -- exactly these three provinces. This module replaces LitPop's *distribution*
for them with a bottom-up build: one exposure point per real OSM building, valued by
footprint floor area, plus one point per barangay valued by its actual 2020 census
population -- then stitches the result into LitPop's ROI-wide layer so nothing outside
these three provinces changes.

Data sources and vintages (documented per the working rules -- Rolly hit 31 Oct-1 Nov
2020):
- OSM building footprints: live Overpass query, extracted here on 2026-07-05 (dataset
  itself is a rolling snapshot of OSM's current state, not a fixed historical vintage --
  a real, disclosed temporal mismatch against Rolly's 2020 landfall; see "what this
  doesn't resolve" in docs/v1.1-phase3-result.md for what that means for interpretation).
- Population: PSA 2020 Census of Population and Housing, barangay level, redistributed
  via HDX (https://data.humdata.org/dataset/cod-ps-phl, resource
  "2020-census-total-popn_single-age_malefemale_admin4.xlsx") since psa.gov.ph itself
  returns HTTP 403 from this environment. Same year as Rolly -- no mismatch here.
- Barangay boundaries: GADM v4.1 ADM_ADM_3 (already cached locally from Phase 5), name-
  joined to the PSA population table -- see BARANGAY_MATCH_RATE below, a real, reported
  gap, not silently patched away.
- Construction cost rate: PHP 9,949/m^2, a commercial quantity-surveyor industry
  estimate (national average, single-family residential) -- not PSA's own
  region-specific "Approved Building Permits" statistics, which are also blocked
  (psa.gov.ph, 403). This is a disclosed lower-authority substitute, applied uniformly
  to all three provinces since no Bicol-specific figure could be independently
  confirmed. See docs/v1.1-phase3-result.md for the full sourcing discussion.
- Exchange rate: PHP 49.624 per USD, World Bank World Development Indicators series
  PA.NUS.FCRF, 2020 annual average (official exchange rate, LCU per US$, period
  average) -- fetched directly from the World Bank API, not invented.
"""

import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from climada.entity import Exposures
from shapely.geometry import box

from landfall.exposure.litpop import asset_exposure as litpop_asset_exposure
from landfall.exposure.litpop import population_exposure as litpop_population_exposure

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "exposure_v1_1"
GADM_PATH = Path(__file__).resolve().parents[3] / "data" / "cache" / "gadm" / "gadm41_PHL.gpkg"
POPULATION_CSV = DATA_DIR / "raw" / "population_admin4_2020census.csv"

TARGET_PROVINCES = ["Catanduanes", "Albay", "Camarines Sur"]
UTM_51N = "EPSG:32651"  # Bicol region falls entirely within UTM zone 51N

PHP_PER_SQM = 9_949.0  # commercial QS-guide national average, single-family residential
PHP_PER_USD_2020 = 49.624  # World Bank WDI, PA.NUS.FCRF, 2020 annual average


def _norm(s: str) -> str:
    # NFKD + drop combining marks strips accents (e.g. "SAGÑAY" -> "SAGNAY") -- PSA and
    # GADM don't always agree on diacritics for the same place name.
    ascii_s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return "".join(ch for ch in ascii_s.upper().strip() if ch.isalnum())


def _norm_mun(s: str) -> str:
    """Municipality-name normalization for the GADM<->PSA join, on top of `_norm`:
    PSA appends parenthetical alt-names to some municipalities (e.g. "Virac
    (Capital)", "San Andres (Calolbon)") that GADM's plain names don't carry, and the
    two disagree on word order for cities ("City of Naga" vs GADM's "Naga City") --
    both stripped/normalized here, unlike `_norm`'s barangay-level use, where a
    parenthetical often disambiguates two real, distinct barangays (e.g. "Bonga
    (Upper)") and must not be stripped."""
    base = _norm(str(s).split("(")[0])
    if base.startswith("CITYOF"):
        return base[len("CITYOF") :]
    if base.endswith("CITY"):
        return base[: -len("CITY")]
    return base


def province_boundary(name: str) -> gpd.GeoSeries:
    gdf = gpd.read_file(GADM_PATH, layer="ADM_ADM_1")
    return gdf[gdf["NAME_1"] == name].geometry


def target_provinces_union():
    gdf = gpd.read_file(GADM_PATH, layer="ADM_ADM_1")
    target = gdf[gdf["NAME_1"].isin(TARGET_PROVINCES)]
    return target.union_all()


def _parse_levels(raw) -> float:
    """OSM's building:levels is free-text (ranges, "1;2", "yes", ...); anything that
    doesn't parse to a plausible positive number defaults to 1 story, the same default
    CLIMADA and most exposure-building pipelines use for untagged buildings."""
    try:
        v = float(str(raw).split(";")[0])
        return v if 0 < v <= 100 else 1.0
    except (ValueError, TypeError, AttributeError):
        return 1.0


def osm_asset_exposure(province: str) -> Exposures:
    """One exposure point per OSM building footprint in `province`, valued at
    floor_area_m2 * PHP_PER_SQM / PHP_PER_USD_2020."""
    slug = province.lower().replace(" ", "_")
    buildings = gpd.read_file(DATA_DIR / "osm" / f"{slug}_buildings.gpkg")

    projected = buildings.to_crs(UTM_51N)
    footprint_area_m2 = projected.geometry.area.to_numpy()
    levels = buildings["building:levels"].map(_parse_levels) if "building:levels" in buildings.columns else 1.0
    floor_area_m2 = footprint_area_m2 * np.asarray(levels)
    value_usd = floor_area_m2 * PHP_PER_SQM / PHP_PER_USD_2020

    centroids = projected.geometry.centroid.to_crs("EPSG:4326")
    gdf = gpd.GeoDataFrame({"value": value_usd, "geometry": centroids.geometry}, crs="EPSG:4326")
    return Exposures(data=gdf)


def _barangay_population(province: str) -> gpd.GeoDataFrame:
    """GADM barangay geometries name-joined to PSA 2020 census population, with an
    area-proportional fallback (within each municipality only) for barangays that
    don't name-match -- see BARANGAY_MATCH_RATE / docs/v1.1-phase3-result.md for the
    match rate and why some GADM barangay names can't be matched at all (a handful are
    GADM data-quality gaps -- generic "Barangay N" placeholders -- not just formatting
    differences)."""
    pop = pd.read_csv(POPULATION_CSV)
    pop["prov_norm"] = pop["Province"].map(_norm)
    pop["mun_norm"] = pop["Mun"].map(_norm_mun)
    pop["bgy_norm"] = pop["Bgy"].map(_norm)
    pop = pop[pop["prov_norm"] == _norm(province)]

    gadm = gpd.read_file(GADM_PATH, layer="ADM_ADM_3")
    barangays = gadm[gadm["NAME_1"] == province].copy()
    barangays["mun_norm"] = barangays["NAME_2"].map(_norm_mun)
    barangays["bgy_norm"] = barangays["NAME_3"].map(_norm)

    merged = barangays.merge(
        pop[["mun_norm", "bgy_norm", "Total_MF"]], on=["mun_norm", "bgy_norm"], how="left"
    )
    merged["area"] = merged.to_crs(UTM_51N).geometry.area

    mun_totals = pop.groupby("mun_norm")["Total_MF"].sum()
    matched_totals = merged.groupby("mun_norm")["Total_MF"].sum(min_count=1).fillna(0)
    unmatched_area_by_mun = merged.loc[merged["Total_MF"].isna()].groupby("mun_norm")["area"].sum()

    def _fill(row):
        if pd.notna(row["Total_MF"]):
            return row["Total_MF"]
        remainder = mun_totals.get(row["mun_norm"], 0) - matched_totals.get(row["mun_norm"], 0)
        area_total = unmatched_area_by_mun.get(row["mun_norm"], 0)
        return remainder * (row["area"] / area_total) if area_total > 0 else 0.0

    merged["population"] = merged.apply(_fill, axis=1)
    return merged[["NAME_2", "NAME_3", "population", "geometry"]].rename(
        columns={"NAME_2": "municipality", "NAME_3": "barangay"}
    )


def census_population_exposure(province: str) -> Exposures:
    """One exposure point per barangay centroid in `province`, valued at its 2020
    census population count."""
    barangays = _barangay_population(province)
    centroids = barangays.to_crs(UTM_51N).geometry.centroid.to_crs("EPSG:4326")
    gdf = gpd.GeoDataFrame({"value": barangays["population"].to_numpy(), "geometry": centroids.geometry}, crs="EPSG:4326")
    return Exposures(data=gdf)


def _hybrid(bounds: tuple[float, float, float, float], litpop_fn, osm_fn) -> Exposures:
    base = litpop_fn(bounds)
    union = target_provinces_union()
    outside_mask = ~base.gdf.geometry.within(union)
    base_outside = base.gdf[outside_mask]

    parts = [base_outside]
    for province in TARGET_PROVINCES:
        boundary = province_boundary(province).union_all()
        if not boundary.intersects(box(*bounds)):
            continue
        parts.append(osm_fn(province).gdf)

    combined = pd.concat(parts, ignore_index=True)
    return Exposures(data=gpd.GeoDataFrame(combined, crs="EPSG:4326"))


def asset_exposure(bounds: tuple[float, float, float, float]) -> Exposures:
    return _hybrid(bounds, litpop_asset_exposure, osm_asset_exposure)


def population_exposure(bounds: tuple[float, float, float, float]) -> Exposures:
    return _hybrid(bounds, litpop_population_exposure, census_population_exposure)
