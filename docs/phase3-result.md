# Phase 3 result — counterfactual mechanism working end to end

## What was built

- **`landfall/scenario.py`** — `ScenarioConfig` (pydantic): `storm_key`, `track_offset_km`,
  `track_bearing_deg`, `intensity_delta_kn`. Hard range validation on every field (not
  clamping — out-of-range values raise `ValidationError`, verified below). `perturb_track()`
  applies a geodesic offset (via `geopy.distance.geodesic(...).destination(...)`, already a
  CLIMADA dependency) to every track point's lat/lon, and adds `intensity_delta_kn` to
  `max_sustained_wind` (clipped at 0).
- **Scenario-hash disk cache** — folded into `landfall/impact/engine.py`. Every run
  (baseline or counterfactual) is a `ScenarioConfig`; the historical baseline is simply one
  with zero perturbation. Results cache to `data/cache/scenarios/<hash>.json`, keyed on a
  SHA-256 of the canonical config — matches PRD §5.1's "every scenario run is cached to
  disk keyed on a scenario-config hash."
- Regression-checked the refactor against the exact Phase 1/2 Haiyan baseline number
  ($49,327,691.86 / 9,168,006) before trusting it — unchanged.

## Validation (fail loud, not plausible)

```
ScenarioConfig(storm_key='not_a_storm')        -> ValidationError (unregistered storm)
ScenarioConfig(storm_key='haiyan', track_offset_km=99999)     -> ValidationError (> 500km cap)
ScenarioConfig(storm_key='haiyan', intensity_delta_kn=500)    -> ValidationError (> 60kn cap)
```

All three reject outright rather than clamping to a nearest valid value.

## DoD: "Haiyan, 100 km north" vs. historical baseline

```
                          baseline          counterfactual (+100km north)
total_damage_usd          49,327,691.86     5,902,268.00
affected_population       9,168,006         1,081,467

damage ratio (cf/baseline):              0.120
affected population ratio (cf/baseline): 0.118
```

Shifting the track 100km north pushes Haiyan's core wind field away from the historical
landfall corridor (Guiuan → Tacloban → Cebu), which is exactly the densely-exposed
Leyte/Samar/Cebu belt this ROI was built around. Damage and affected population both drop
to ~12% of baseline — a large effect, but directionally exactly what should happen when a
Cat. 5 storm's eyewall moves off the cities it actually hit. This is the kind of sanity
check worth doing on every counterfactual before trusting a number: does the direction and
rough magnitude of the change make physical sense, even before any narration layer exists
to describe it.

## Known simplifications (documented, not hidden)

- **`central_pressure` is not adjusted** alongside `intensity_delta_kn` — a wind-only
  intensity perturbation becomes mildly inconsistent with the Holland model's implied
  pressure-wind relationship for nonzero intensity deltas. Not exercised by the "100km
  north" DoD case (`intensity_delta_kn=0`); revisit before leaning on intensity-delta
  scenarios for anything beyond "however wrong" exploration.
- **No landfall-coordinate targeting** ("make landfall at X, Y") — PRD §5.2 lists this as
  an alternative scenario parameter alongside track offset/bearing. Implemented offset +
  bearing only, since it directly covers the PRD's own worked example. Coordinate-targeting
  would need an optimization/search step (find the offset that produces landfall nearest a
  target point) — deferred, not attempted as a shortcut.

## Deliberately not started this phase

**LLM scenario compiler (NL → `ScenarioConfig`) and the E3 eval set** — per PRD §6, E3's 40
hand-labeled ground-truth configs must be labeled by the author, not the agent building the
compiler being evaluated against them; an agent-authored eval would be circular. Flagged to
the user rather than fabricated. The compiler itself (structured-output call to a
Haiku-class model, validating against `ScenarioConfig`) is a self-contained follow-up once
that dataset exists or a decision is made about how to source it.

## Next (Phase 4, pending the above)

Narrator + groundedness verifier, sitrep RAG with citations, E2 run. E3 and the scenario
compiler can slot in whenever the labeled dataset question is resolved — they don't block
Phase 4's narration work, which operates on cached impact output regardless of how a
scenario config was produced (hand-written or compiled).
