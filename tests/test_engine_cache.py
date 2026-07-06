"""Regression test for the scenario-result cache key (landfall/impact/engine.py).

`ScenarioConfig.scenario_hash()` alone is not a safe cache key: it hashes only the
user-facing scenario fields (storm, offset, bearing, intensity delta), not the
calibration approach/quantiles or ROI bounds that also determine the output — and both
HAVE changed for real in this project's history (calibration: TDR -> RMSF -> EDR across
v1.1/v1.2). Directly tampering a cache file keyed the old way (calibration_approach set
to "TDR", damage set to an obviously-fake 1.23) and calling `run()` again for the
identical `ScenarioConfig` confirmed the tampered value was returned unchanged, with no
detection — a stale post-recalibration cache entry would be served identically,
forever. `_cache_key()` fixes this by folding calibration constants and ROI bounds into
the key itself, so a future change to either naturally produces a new key rather than
silently reusing output computed under a methodology the current code no longer uses.

Requires one real engine run for setup (CLIMADA compute, ~15-20s) — not a pure/fast
unit test like test_groundedness.py, but still no API calls.

Run without pytest: python tests/test_engine_cache.py
Run with pytest if installed: pytest tests/test_engine_cache.py
"""

import json

from landfall.impact.engine import _cache_key, run, CACHE_DIR
from landfall.scenario import ScenarioConfig
from landfall.storms import STORMS

_CONFIG = ScenarioConfig(storm_key="haiyan")
_STORM_CONFIG = STORMS["haiyan"]


def test_cache_key_changes_with_calibration_constants():
    # same scenario_hash, different calibration/ROI fingerprint -> different cache key
    key_a = _cache_key(_CONFIG, _STORM_CONFIG)
    fake_storm_config = type(_STORM_CONFIG)(
        key=_STORM_CONFIG.key,
        ibtracs_sid=_STORM_CONFIG.ibtracs_sid,
        ibtracs_name=_STORM_CONFIG.ibtracs_name,
        roi_bounds=(121.5, 8.0, 126.5, 13.5),  # lat_max nudged 13.0 -> 13.5
        year=_STORM_CONFIG.year,
    )
    key_b = _cache_key(_CONFIG, fake_storm_config)
    assert key_a != key_b


def test_stale_old_style_cache_is_not_served():
    # a real computation, cached under the CURRENT (correct) fingerprinted key
    real_result = run(_CONFIG)
    real_damage = real_result["total_damage_usd"]
    assert real_damage > 0  # sanity: Haiyan has substantial real damage

    # plant a tampered file at the OLD-style key (scenario_hash() alone) -- what a
    # pre-fix cache file, or a file surviving a calibration change, would look like
    old_style_path = CACHE_DIR / f"{_CONFIG.scenario_hash()}.json"
    tampered = {**real_result, "total_damage_usd": 1.23, "calibration_approach": "TDR"}
    old_style_path.write_text(json.dumps(tampered))

    try:
        result = run(_CONFIG)  # same ScenarioConfig, use_cache=True (default)
        assert result["total_damage_usd"] == real_damage  # NOT 1.23
        assert result["calibration_approach"] != "TDR"
    finally:
        old_style_path.unlink(missing_ok=True)


def test_current_fingerprinted_cache_is_still_trusted_and_reused():
    # calling run() twice for the same scenario should hit the (correct) cache, not
    # recompute -- verified via the file actually existing at the new key
    run(_CONFIG)
    current_path = CACHE_DIR / f"{_cache_key(_CONFIG, _STORM_CONFIG)}.json"
    assert current_path.exists()
    cached = json.loads(current_path.read_text())
    assert cached["calibration_approach"] == "EDR"


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = []
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failures.append(t.__name__)
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
