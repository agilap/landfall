# Phase 5 result — per-municipality damage breakdown

## Why this phase exists

Asked "what's still missing" against the PRD after Phase 4b, the honest answer was: the
impact engine only ever returned one total per ROI. PRD §5.1 specifies "per-municipality
damage estimates and affected-population counts," and the PRD's own representative queries
(§3) — *"which municipalities in Cebu see the highest housing damage?"* — literally
couldn't be answered by anything built through Phase 4. This phase closes that gap.

## Data source

GADM (gadm.org) publishes free administrative boundaries for every country, no login
required — confirmed reachable before committing to it (unlike SEDAC/ndrrmc.gov.ph
earlier in this project). Downloaded `gadm41_PHL.gpkg` (75.7MB, cached under
`data/cache/gadm/`, gitignored).

GADM's Philippines hierarchy, confirmed by inspection rather than assumed:
`ADM_ADM_0` = country, `ADM_ADM_1` = **province**, `ADM_ADM_2` = **municipality/city**
(1,647 units — e.g. "Bogo City", "Carcar" under province "Cebu"), `ADM_ADM_3` = barangay
(41,948 units, too fine-grained for this purpose). `ADM_ADM_2` is the layer used.

## Implementation

`landfall/impact/municipality.py`:
- `load_municipalities(bounds)` — reads the `ADM_ADM_2` layer clipped to a storm's ROI
  bounding box.
- `damage_by_municipality()` / `affected_population_by_municipality()` — spatial join
  (point-in-polygon) between exposure-grid points and municipality polygons, then grouped
  sum. Uses **positional** alignment between CLIMADA's `imp_mat` (per-exposure-point
  damage) and the exposure GeoDataFrame's geometry array, not pandas-index alignment —
  the ROI clip upstream (`.cx[]` slicing) leaves a non-contiguous index, and `imp_mat`'s
  columns are ordered by row position, not index label.

`engine.py`'s `run()` now attaches `damage_by_municipality` and
`affected_population_by_municipality` (lists of `{province, municipality, value}`,
sorted descending) to every cached result, alongside the existing ROI-wide totals.
Cleared the entire existing scenario cache (21 stale entries) so every future run — and
every scenario already exercised in Phases 2–4 — recomputes with the new fields rather
than silently missing them.

## Validation: does the breakdown match history?

**Odette** (total damage unchanged at $184,074,084.28, confirming the refactor didn't
touch the ROI-wide aggregate): top municipality is **Cebu City** ($66.9M), followed by
**Lapu-Lapu City** and **Mandaue City** — Metro Cebu dominates. This matches real-world
reporting closely: Odette/Rai hit Cebu Island far harder than initially forecast (its
track crossed directly over Cebu rather than the more southerly path originally
expected), a widely reported surprise at the time.

**Haiyan** (total unchanged at $49,327,691.86): top municipality is **Tacloban City,
Leyte** ($12.0M) — the single most iconic ground-zero location in Haiyan's actual
historical devastation. Second is Santa Fe, then Ormoc City, both also Leyte.

Both results land exactly where independent knowledge of these storms says they should,
without having been tuned to do so — the municipality boundaries and the wind field are
computed from entirely independent data sources (GADM vs. IBTrACS/CLIMADA) that only
agree because the underlying physics and geography are real.

## What this doesn't fix

- Still ROI-scoped: a municipality entirely outside a storm's defined ROI bounds won't
  appear at all, even if it experienced some nonzero wind (per Phase 1-2's ROI-widening
  process, this should be rare, but isn't impossible for storms whose real extent exceeds
  the bounding box chosen from the track plot).
- `affected_population_by_municipality` inherits the same crude "any nonzero wind"
  threshold proxy as the ROI-wide figure — not a damage-function-based estimate, per
  PRD's casualty-modeling non-goal.
- Not yet surfaced through the narrator or RAG layers — this is impact-engine output only;
  wiring a "top N municipalities" briefing into the narrator (with the same groundedness
  verification) is a natural next step, not done here.
