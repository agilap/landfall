"""Export a committed scenario cache to a self-contained bundle for Landfall Viz.

landfall-viz-prd.md §5.2 / CLAUDE.md's "Landfall Viz" section: the viz renders committed
scenario caches only, it never computes. This module is the one-way door between the two
projects -- every number in an exported bundle either comes verbatim from
`data/cache/scenarios/*.json` (damage, affected population) or is recomputed
deterministically from the same cached scenario config (track, wind grid), never guessed
or interpolated. Boundaries come from the same GADM source the engine already joins
against for `damage_by_municipality`.

The user-facing `ScenarioConfig.scenario_hash()` is not the on-disk cache filename (see
`landfall.impact.engine._cache_key`'s docstring for why) -- so resolving a scenario-hash
argument to its cache file means scanning cache contents, not doing a path lookup.
"""

import json
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np

from landfall.hazard.tracks import get_track
from landfall.hazard.wind import ARCSEC_150_IN_DEG, wind_field
from landfall.impact.engine import CACHE_DIR, _cache_key, run_baseline
from landfall.impact.municipality import GADM_PATH
from landfall.scenario import ScenarioConfig, perturb_track
from landfall.storms import STORMS

REPO_ROOT = Path(__file__).resolve().parents[2]
VIZ_DATA_DIR = REPO_ROOT / "viz" / "public" / "data"

DISCLAIMER = "Research/preparedness demonstration only; counterfactuals are hypothetical."

# ~500m -- well below the 150-arcsec (~4.5km) hazard cell size, so simplification adds no
# false precision relative to what the model actually resolves. Per landfall-viz-prd.md §4.3.
BOUNDARY_SIMPLIFY_TOLERANCE_DEG = 0.005

# Display-side rounding only; damage.json is untouched (copied verbatim from the cache).
WIND_VALUE_ROUNDING = 0.01


class ScenarioNotFoundError(ValueError):
    """Raised when a scenario-hash argument doesn't resolve to exactly one cache file."""


class ExportIntegrityError(RuntimeError):
    """A provenance or grid-consistency check failed during export.

    A real exception, not an `assert` -- these checks are the module's fail-loud
    guarantee (CLAUDE.md) and must survive `python -O`, which strips asserts.
    """


def _git_describe() -> str:
    result = subprocess.run(
        ["git", "describe", "--tags", "--always"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def find_cache_by_scenario_hash(scenario_hash: str) -> Path:
    """Scan `data/cache/scenarios/*.json` for the file whose embedded `scenario_hash`
    matches -- the cache filename is `_cache_key()`, a different hash (see module
    docstring), so this can't be a path lookup."""
    matches = []
    for path in sorted(CACHE_DIR.glob("*.json")):
        cache = json.loads(path.read_text())
        if cache.get("scenario_hash") == scenario_hash:
            matches.append(path)

    if not matches:
        # .get(): a legacy/malformed cache without the key should be skipped in this
        # error-message listing, not turn the refusal into a KeyError.
        embedded = (json.loads(p.read_text()).get("scenario_hash") for p in CACHE_DIR.glob("*.json"))
        available = sorted(h for h in embedded if h is not None)
        raise ScenarioNotFoundError(
            f"No cached scenario found with scenario_hash={scenario_hash!r}. "
            f"Available scenario hashes ({len(available)}): {available}"
        )
    if len(matches) > 1:
        raise ScenarioNotFoundError(
            f"Ambiguous scenario_hash={scenario_hash!r}: matched {len(matches)} cache files "
            f"{[p.name for p in matches]}. Cache keys are content hashes of the full scenario "
            f"+ calibration + ROI fingerprint, so this should never happen -- investigate before "
            f"trusting either file."
        )
    return matches[0]


def _write_meta(bundle_dir: Path, scenario: ScenarioConfig, storm_config, cache: dict, cache_path: Path, wind) -> None:
    meta = {
        "storm_key": scenario.storm_key,
        "storm_name": scenario.storm_key.title(),
        "ibtracs_sid": storm_config.ibtracs_sid,
        "ibtracs_name": storm_config.ibtracs_name,
        "year": storm_config.year,
        "scenario": scenario.model_dump(),
        "scenario_hash": cache["scenario_hash"],
        "source_cache_key": cache_path.stem,
        "calibration_approach": cache["calibration_approach"],
        "calibration_point_quantile": cache["calibration_point_quantile"],
        "calibration_range_quantiles": cache["calibration_range_quantiles"],
        "hazard_model": cache["hazard_model"],
        "units": {
            "damage": "USD",
            # Verified empirically against `TropCyclone.units` (CLIMADA's H1980 max-sustained-wind
            # field), not assumed -- do not hardcode "kn" here even though the track's
            # max_sustained_wind field (track.json) is in knots; the two units genuinely differ.
            "wind": wind.units,
        },
        "landfall_version": _git_describe(),
        "disclaimer": DISCLAIMER,
        "provenance": (
            f"impact values copied verbatim from scenario cache {cache_path.stem}; "
            "wind grid recomputed deterministically from cached track via wind_field(); "
            "boundaries GADM v4.1 GID_2 (PSGC crosswalk: roadmap)"
        ),
    }
    (bundle_dir / "meta.json").write_text(json.dumps(meta, indent=2))


def _write_track(bundle_dir: Path, tracks) -> None:
    track = tracks.data[0]
    times = track.time.values
    records = [
        {
            "time": np.datetime_as_string(t, unit="s") + "Z",
            "lat": float(lat),
            "lon": float(lon),
            "max_sustained_wind_kn": float(wind_kn),
            "central_pressure": float(pressure),
            "radius_max_wind": float(rmw),
        }
        for t, lat, lon, wind_kn, pressure, rmw in zip(
            times,
            track.lat.values,
            track.lon.values,
            track.max_sustained_wind.values,
            track.central_pressure.values,
            track.radius_max_wind.values,
        )
    ]
    (bundle_dir / "track.json").write_text(json.dumps(records, indent=2))


def _write_wind(bundle_dir: Path, wind, bounds: tuple[float, float, float, float]) -> None:
    lon_min, lat_min, lon_max, lat_max = bounds
    rows = round((lat_max - lat_min) / ARCSEC_150_IN_DEG) + 1
    cols = round((lon_max - lon_min) / ARCSEC_150_IN_DEG) + 1

    lats = wind.centroids.lat
    lons = wind.centroids.lon
    intensity = wind.intensity[0].toarray().flatten()
    if lats.size != rows * cols:
        raise ExportIntegrityError(
            f"centroid count {lats.size} != rows*cols {rows}*{cols} -- ROI bounds or resolution "
            f"assumption is wrong, do not silently reshape a mismatched array"
        )

    # Grid position is computed from each centroid's actual lat/lon, not trusted from
    # flatten order -- confirmed empirically to already be row-major (north-to-south,
    # west-to-east) for CLIMADA's Centroids.from_pnt_bounds, but this makes the mapping
    # correct by construction rather than by an unstated assumption about internal ordering.
    row_idx = np.round((lat_max - lats) / ARCSEC_150_IN_DEG).astype(int)
    col_idx = np.round((lons - lon_min) / ARCSEC_150_IN_DEG).astype(int)
    if row_idx.min() < 0 or row_idx.max() >= rows or col_idx.min() < 0 or col_idx.max() >= cols:
        raise ExportIntegrityError(
            f"centroid falls outside the {rows}x{cols} grid (rows {row_idx.min()}..{row_idx.max()}, "
            f"cols {col_idx.min()}..{col_idx.max()}) -- centroid coordinates disagree with ROI bounds"
        )

    grid = np.zeros((rows, cols))
    grid[row_idx, col_idx] = intensity
    grid = np.round(grid, 2)

    payload = {
        "bounds": [lon_min, lat_min, lon_max, lat_max],
        "res_deg": ARCSEC_150_IN_DEG,
        "shape": [rows, cols],
        "units": wind.units,
        "row_order": "row 0 is the north edge (lat_max); row index increases southward",
        "col_order": "col 0 is the west edge (lon_min); col index increases eastward",
        "value_rounding": WIND_VALUE_ROUNDING,
        "values": grid.tolist(),
    }
    wind_dir = bundle_dir / "wind"
    wind_dir.mkdir(exist_ok=True)
    (wind_dir / "max_swath.json").write_text(json.dumps(payload))


def _write_damage(bundle_dir: Path, cache: dict) -> None:
    # Verbatim subset of the cache -- no rounding, no reordering, per landfall-viz-prd.md
    # §4.3 ("no interpolation that manufactures precision") and CLAUDE.md's "no new numbers".
    damage = {
        "total_damage_usd": cache["total_damage_usd"],
        "total_damage_usd_range": cache["total_damage_usd_range"],
        "affected_population": cache["affected_population"],
        "damage_by_municipality": cache["damage_by_municipality"],
        "affected_population_by_municipality": cache["affected_population_by_municipality"],
    }
    (bundle_dir / "damage.json").write_text(json.dumps(damage, indent=2))


def _write_boundaries(bundle_dir: Path, bounds: tuple[float, float, float, float]) -> None:
    # Same GID_2-level GADM source `landfall.impact.municipality.load_municipalities` joins
    # against for damage_by_municipality, but keeping GID_2 (that loader drops it, since the
    # engine only needs province/municipality names to join on).
    gdf = gpd.read_file(GADM_PATH, layer="ADM_ADM_2", bbox=bounds)[["GID_2", "NAME_1", "NAME_2", "geometry"]]
    gdf["geometry"] = gdf.geometry.simplify(BOUNDARY_SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)

    features = [
        {
            "type": "Feature",
            "properties": {
                "gid_2": row.GID_2,
                "province": row.NAME_1,
                "municipality": row.NAME_2,
            },
            "geometry": row.geometry.__geo_interface__,
        }
        for row in gdf.itertuples()
    ]
    feature_collection = {"type": "FeatureCollection", "features": features}
    (bundle_dir / "boundaries.json").write_text(json.dumps(feature_collection))


def _update_manifest(out_dir: Path, scenario: ScenarioConfig, storm_config, is_baseline: bool) -> None:
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []

    if is_baseline:
        label = f"{scenario.storm_key.title()} ({storm_config.year}) -- historical baseline"
    else:
        label = (
            f"{scenario.storm_key.title()} ({storm_config.year}) counterfactual: "
            f"offset {scenario.track_offset_km:.0f}km @ {scenario.track_bearing_deg:.0f}deg, "
            f"intensity {scenario.intensity_delta_kn:+.0f}kn"
        )
    entry = {
        "scenario_hash": scenario.scenario_hash(),
        "storm_key": scenario.storm_key,
        "label": label,
        "is_baseline": is_baseline,
        "path": f"data/{scenario.scenario_hash()}",
    }

    manifest = [e for e in manifest if e["scenario_hash"] != entry["scenario_hash"]]
    manifest.append(entry)
    manifest.sort(key=lambda e: (e["storm_key"], not e["is_baseline"], e["scenario_hash"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))


def export_scenario(scenario_hash: str, out_dir: Path = VIZ_DATA_DIR) -> Path:
    """Export the cached scenario identified by `scenario_hash` to `out_dir/<scenario_hash>/`."""
    cache_path = find_cache_by_scenario_hash(scenario_hash)
    cache = json.loads(cache_path.read_text())
    scenario = ScenarioConfig(**cache["scenario"])
    storm_config = STORMS[scenario.storm_key]

    recomputed_key = _cache_key(scenario, storm_config)
    if cache_path.stem != recomputed_key:
        raise ExportIntegrityError(
            f"cache file {cache_path.name} does not match its own scenario+calibration+ROI "
            f"fingerprint (recomputed: {recomputed_key}) -- refusing to export a bundle whose "
            f"provenance chain doesn't check out"
        )

    bundle_dir = out_dir / scenario_hash
    bundle_dir.mkdir(parents=True, exist_ok=True)

    tracks = get_track(scenario.storm_key)
    if not scenario.is_historical_baseline():
        tracks = perturb_track(tracks, scenario)
    wind = wind_field(tracks, storm_config.roi_bounds)  # not cached -- recomputed deterministically

    _write_meta(bundle_dir, scenario, storm_config, cache, cache_path, wind)
    _write_track(bundle_dir, tracks)
    _write_wind(bundle_dir, wind, storm_config.roi_bounds)
    _write_damage(bundle_dir, cache)
    _write_boundaries(bundle_dir, storm_config.roi_bounds)
    _update_manifest(out_dir, scenario, storm_config, is_baseline=scenario.is_historical_baseline())

    return bundle_dir


def export_all_baselines(out_dir: Path = VIZ_DATA_DIR) -> list[Path]:
    """Export the four historical (zero-perturbation) baselines. Ensures each has a cache
    entry first (`run_baseline` is a cache hit if already run -- see engine.py's `run()`)."""
    bundle_dirs = []
    for storm_key in sorted(STORMS):
        run_baseline(storm_key)
        scenario_hash = ScenarioConfig(storm_key=storm_key).scenario_hash()
        bundle_dirs.append(export_scenario(scenario_hash, out_dir))
    return bundle_dirs
