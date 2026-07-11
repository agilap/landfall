"""Regression test for the export-viz bundle pipeline (landfall/export_viz.py).

Checks that an exported bundle is a faithful, traceable view of its source scenario
cache -- per landfall-viz-prd.md's "no new numbers" principle, every value in a bundle
must either equal a cached value exactly or be reproducibly derived from the same cached
scenario config. This is a check on an *existing* export, not the (slow, CLIMADA-compute)
export itself -- skips cleanly if `landfall export-viz --all-baselines` hasn't been run.

Run without pytest: python tests/test_export_viz.py
Run with pytest if installed: pytest tests/test_export_viz.py
"""

import json

from landfall.export_viz import VIZ_DATA_DIR, find_cache_by_scenario_hash
from landfall.hazard.tracks import get_track
from landfall.hazard.wind import ARCSEC_150_IN_DEG
from landfall.impact.engine import CACHE_DIR, _cache_key
from landfall.scenario import ScenarioConfig
from landfall.storms import STORMS

_SKIP = "no exported bundles under viz/public/data/ -- run `landfall export-viz --all-baselines` first"


def _bundle_dir_for(storm_key: str):
    scenario_hash = ScenarioConfig(storm_key=storm_key).scenario_hash()
    bundle_dir = VIZ_DATA_DIR / scenario_hash
    return bundle_dir if bundle_dir.is_dir() else None


def _exported_baseline_storm_keys():
    return [k for k in sorted(STORMS) if _bundle_dir_for(k) is not None]


def test_bundles_exist_for_all_four_baselines():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    assert exported == sorted(STORMS), f"expected all {len(STORMS)} baselines exported, got {exported}"


def test_meta_scenario_hash_matches_bundle_dir_name():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    for storm_key in exported:
        bundle_dir = _bundle_dir_for(storm_key)
        meta = json.loads((bundle_dir / "meta.json").read_text())
        assert meta["scenario_hash"] == bundle_dir.name


def test_source_cache_key_recomputes_and_exists():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    for storm_key in exported:
        bundle_dir = _bundle_dir_for(storm_key)
        meta = json.loads((bundle_dir / "meta.json").read_text())
        scenario = ScenarioConfig(storm_key=storm_key)
        recomputed_key = _cache_key(scenario, STORMS[storm_key])
        assert meta["source_cache_key"] == recomputed_key
        assert (CACHE_DIR / f"{recomputed_key}.json").exists()


def test_damage_json_matches_cache_exactly():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    for storm_key in exported:
        bundle_dir = _bundle_dir_for(storm_key)
        scenario_hash = bundle_dir.name
        damage = json.loads((bundle_dir / "damage.json").read_text())
        cache = json.loads(find_cache_by_scenario_hash(scenario_hash).read_text())

        assert damage["total_damage_usd"] == cache["total_damage_usd"]
        assert damage["total_damage_usd_range"] == cache["total_damage_usd_range"]
        assert damage["affected_population"] == cache["affected_population"]
        assert damage["damage_by_municipality"] == cache["damage_by_municipality"]
        assert damage["affected_population_by_municipality"] == cache["affected_population_by_municipality"]


def test_track_matches_source_netcdf():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    for storm_key in exported:
        bundle_dir = _bundle_dir_for(storm_key)
        track = json.loads((bundle_dir / "track.json").read_text())
        src = get_track(storm_key).data[0]

        assert len(track) == src.time.size
        for i, point in enumerate(track):
            assert point["lat"] == float(src.lat.values[i])
            assert point["lon"] == float(src.lon.values[i])
            assert point["max_sustained_wind_kn"] == float(src.max_sustained_wind.values[i])
            assert point["central_pressure"] == float(src.central_pressure.values[i])
            assert point["radius_max_wind"] == float(src.radius_max_wind.values[i])


def test_wind_grid_shape_matches_roi_bounds_at_150_arcsec():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    for storm_key in exported:
        bundle_dir = _bundle_dir_for(storm_key)
        wind = json.loads((bundle_dir / "wind" / "max_swath.json").read_text())
        lon_min, lat_min, lon_max, lat_max = STORMS[storm_key].roi_bounds

        expected_rows = round((lat_max - lat_min) / ARCSEC_150_IN_DEG) + 1
        expected_cols = round((lon_max - lon_min) / ARCSEC_150_IN_DEG) + 1

        assert wind["shape"] == [expected_rows, expected_cols]
        assert len(wind["values"]) == expected_rows
        assert all(len(row) == expected_cols for row in wind["values"])
        assert wind["bounds"] == [lon_min, lat_min, lon_max, lat_max]


# Golden pins for the wind grid's peak cell, (row, col, value in m/s), extracted from the
# reviewed Phase 1 export whose orientation was independently verified against each track's
# peak-intensity point. Shape checks alone can't catch a hand-edited value or a north-south
# row flip (which preserves shape); the peak's position and magnitude catch both. If these
# fail after an intentional hazard/calibration change, re-verify orientation against the
# track before re-pinning -- do not update the numbers just to make the test green.
_WIND_PEAK_PINS = {
    "haiyan": (47, 108, 80.65),
    "odette": (37, 157, 68.03),
    "rolly": (27, 71, 82.32),
    "mangkhut": (35, 104, 73.66),
}


def test_wind_grid_peak_cell_matches_pinned_values():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    for storm_key in exported:
        bundle_dir = _bundle_dir_for(storm_key)
        wind = json.loads((bundle_dir / "wind" / "max_swath.json").read_text())
        values = wind["values"]

        peak_val = max(v for row in values for v in row)
        peak_row, peak_col = next(
            (r, row.index(peak_val)) for r, row in enumerate(values) if peak_val in row
        )
        expected_row, expected_col, expected_val = _WIND_PEAK_PINS[storm_key]
        assert (peak_row, peak_col, peak_val) == (expected_row, expected_col, expected_val), (
            f"{storm_key}: wind grid peak {peak_val} at ({peak_row}, {peak_col}) != pinned "
            f"{expected_val} at ({expected_row}, {expected_col}) -- value drift or orientation flip"
        )


def test_manifest_lists_all_exported_bundles():
    exported = _exported_baseline_storm_keys()
    if not exported:
        import pytest

        pytest.skip(_SKIP)
    manifest_path = VIZ_DATA_DIR / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    listed_hashes = {e["scenario_hash"] for e in manifest}
    for storm_key in exported:
        assert _bundle_dir_for(storm_key).name in listed_hashes


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = []
    skipped = []
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failures.append(t.__name__)
        except BaseException as e:  # pytest's Skipped subclasses BaseException, not Exception
            if type(e).__name__ == "Skipped":
                print(f"[SKIP] {t.__name__}: {e}")
                skipped.append(t.__name__)
            else:
                raise
    print(f"\n{len(tests) - len(failures) - len(skipped)}/{len(tests)} passed, {len(skipped)} skipped")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
