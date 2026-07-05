"""One-time data prep for v1.1 Phase 3's hybrid exposure layer (see
docs/v1.1-phase3-result.md and landfall/exposure/hybrid.py). Downloads and caches:

- OSM building footprints for Catanduanes, Albay, Camarines Sur (live Overpass query,
  via osmnx, clipped to each province's real GADM boundary).
- PSA 2020 Census barangay-level population, via HDX (psa.gov.ph itself returns 403
  from this environment) -- converted from the source xlsx to CSV since re-reading a
  48MB xlsx on every run is slow and unnecessary.
- PSA 2020 Census occupied-housing-unit counts by province, via HDX -- used only for
  Phase 3's sanity check (OSM building counts vs PSA housing units), not by the
  exposure layer itself.

Re-run only if the cached files under data/exposure_v1_1/ are missing or you want a
fresher OSM snapshot. Requires network access to overpass-api.de and data.humdata.org.

Usage: python scripts/prepare_hybrid_exposure_data.py
"""

import time
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd
import requests

from landfall.exposure.hybrid import DATA_DIR, GADM_PATH, TARGET_PROVINCES

RAW_DIR = DATA_DIR / "raw"
OSM_DIR = DATA_DIR / "osm"

POPULATION_XLSX_URL = (
    "https://data.humdata.org/dataset/11530271-63a5-4749-8c11-bc5de0bf6a8f/resource/"
    "444f71d1-41f3-474e-a93e-df6cfe8ad642/download/2020-census-total-popn_single-age_malefemale_admin4.xlsx"
)
HOUSING_XLSX_URL = (
    "https://data.humdata.org/dataset/d2098d7b-23f5-4da2-a17d-3c56674fbd49/resource/"
    "08b6441c-d3cc-4d36-8c04-fdc37fa274e2/download/housing_roof_wall_census2020.xlsx"
)


def _download(url: str, out_path: Path) -> None:
    if out_path.exists():
        print(f"already have {out_path}")
        return
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    out_path.write_bytes(response.content)
    print(f"downloaded {out_path} ({len(response.content):,} bytes)")


def prepare_osm_buildings() -> None:
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    ox.settings.overpass_settings = "[out:json][timeout:180]{maxsize}"
    provinces = gpd.read_file(GADM_PATH, layer="ADM_ADM_1")
    provinces = provinces[provinces["NAME_1"].isin(TARGET_PROVINCES)]

    for _, row in provinces.iterrows():
        slug = row["NAME_1"].lower().replace(" ", "_")
        out_path = OSM_DIR / f"{slug}_buildings.gpkg"
        if out_path.exists():
            print(f"already have {out_path}")
            continue
        t0 = time.time()
        buildings = ox.features_from_polygon(row.geometry, tags={"building": True})
        buildings = buildings[buildings.geom_type.isin(["Polygon", "MultiPolygon"])]
        cols = [c for c in ["building", "building:levels", "geometry"] if c in buildings.columns]
        buildings = buildings[cols].reset_index(drop=True)
        buildings.to_file(out_path, driver="GPKG")
        print(f"{row['NAME_1']}: {len(buildings)} buildings, {time.time() - t0:.1f}s -> {out_path}")
        time.sleep(2)


def prepare_population_csv() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    xlsx_path = RAW_DIR / "population_admin4_2020census.xlsx"
    csv_path = RAW_DIR / "population_admin4_2020census.csv"
    _download(POPULATION_XLSX_URL, xlsx_path)
    if csv_path.exists():
        print(f"already have {csv_path}")
        return
    pop = pd.read_excel(xlsx_path, sheet_name="Brgy_adm4")
    pop[["Region", "Province", "Mun", "Bgy", "BgyCode_new", "Total_MF"]].to_csv(csv_path, index=False)
    print(f"saved {csv_path}")


def prepare_housing_units_xlsx() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    _download(HOUSING_XLSX_URL, RAW_DIR / "housing_units_census2020.xlsx")


if __name__ == "__main__":
    prepare_population_csv()
    prepare_housing_units_xlsx()
    prepare_osm_buildings()
