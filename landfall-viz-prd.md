# PRD: Landfall Viz

**3D terrain visualization and time-dynamic replay of Landfall scenarios**

| | |
|---|---|
| Author | Alexander Penuliar (agilap) |
| Status | Draft v1.0 |
| Date | July 2026 |
| Baseline | Landfall v1.3 (current `main`; reconciled 2026-07-06 — see landfall-prd.md for full phase history): CLIMADA wind-hazard engine, **4** historical replays (Haiyan 2013, Rolly 2020, Odette 2021, **Mangkhut 2018**), E1 validation (point estimate + interquartile range since v1.2), E2 narration groundedness, cached scenario outputs keyed by a calibration/ROI-aware fingerprint (`_cache_key()`, v1.3 Phase 3 — a bare config hash alone was found to silently serve stale results across a calibration change). **No `v1.0` tag exists** — only `v1.1` is tagged; the repo has moved to v1.3 untagged since. Phase 0 below addresses this directly rather than assuming v1.0 exists. |
| Scope | Tier 1 (3D visualization of cached outputs) + Tier 2 (time-dynamic replay). Tier 3 (physical 3D simulation) is explicitly rejected, not deferred — see §2 |
| Project type | Solo, evening sessions, phased and gated |
| Mission context | Verified AI portfolio. The visualization inherits Landfall's core guarantee: every rendered value traces to a committed scenario cache and config hash. Even the pretty pictures are reproducible. |

---

## 1. Problem statement

Landfall's outputs are scientifically honest and visually inert. Static matplotlib maps communicate to people who already read hazard maps; they do not communicate to recruiters, LGU staff, students, or anyone scrolling past a link. The 575× Rolly finding — a compact, rapidly-weakening storm whose damaging core a coarse model smeared away — is fundamentally a *spatial and temporal* story that a static image cannot tell and an animated replay tells in ten seconds.

A browser-based 3D visualization of existing cached outputs converts finished work into a legible, shareable artifact at near-zero modeling risk, because it adds no new numbers — only new views of committed ones.

## 2. Goals and non-goals

### Goals

1. **Tier 1:** Render any cached Landfall scenario in the browser — wind field draped over Philippine 3D terrain, per-municipality damage as extruded columns, storm track as a 3D path — from committed cache files only.
2. **Tier 2:** Time-dynamic replay — a timeline scrubber animating the storm's progression, wind swath painting and damage accumulating per timestep, for all four historical storms and any counterfactual.
3. Every rendered value traceable: the UI displays the scenario config hash and links to the cached data that produced the view.
4. Shippable as a static site (GitHub Pages) with no server, no database, no auth.

### Non-goals

- **Tier 3 — physical 3D simulation (rejected, permanently for this project).** Game-engine scenes, 3D atmospheric flow, building-level wind response. Rationale: adds a research group's workload and zero validation credibility; the damage numbers come from the hazard×exposure×vulnerability engine regardless. Parametric wind fields plus calibrated impact functions are the actual cat-modeling industry standard. A game engine on top is theater, and theater is off-brand.
- Real-time or live-storm data paths (operational-tool boundary, unchanged from Landfall's PRD).
- In-browser scenario computation. The viz reads caches; it never runs the model.
- Mobile-optimized UI (desktop browser is the target; mobile merely must not crash).
- New basemap/terrain infrastructure (use hosted terrain — see §5 stack).

## 3. Users and use cases

Primary: portfolio viewers (recruiters, engineers) — the animated Goni replay over Catanduanes is the money shot for the eventual distribution post. Secondary: the author, for debugging (Phase 2 hazard-config comparisons become visually inspectable — two wind-field configs rendered side by side is a better sanity check than two matplotlib PNGs). Tertiary: PH civic-tech/education audiences.

Representative interactions: pick a scenario (historical or counterfactual) → orbit the terrain → scrub the timeline → hover a municipality for its damage figure and config-hash provenance → toggle between two scenarios of the same storm for comparison.

## 4. Product principles

1. **No new numbers.** The viz renders committed caches. If a desired view requires data the engine doesn't emit, the engine changes first (in the Landfall repo, with its own eval), then the viz consumes it.
2. **Provenance visible.** Config hash and cache link in the UI, always. A screenshot of the viz should be self-citing.
3. **Honest rendering.** No interpolation that manufactures spatial precision the model doesn't have (150 arcsec cells render as 150 arcsec cells, not smoothed gradients implying building-level accuracy). Color scales include units and thresholds; damage columns scale linearly or log with the scale stated.
4. **The disclaimer travels.** Research/preparedness demonstration, not operational forecasting — rendered in the UI footer, not just the README.

## 5. System design

### 5.1 Stack decision

**deck.gl over CesiumJS** as the primary framework, with the reasoning recorded:

- deck.gl's layer model maps 1:1 onto the data (TerrainLayer for elevation, GridCellLayer/ColumnLayer for damage, PathLayer for track, a custom or BitmapLayer approach for wind rasters); CesiumJS's strength — global streaming context, CZML time-dynamics — is heavier than needed for a 3-region, pre-cached dataset.
- deck.gl is React-friendly (matches existing frontend skills), tree-shakes to a static bundle, and needs no ion token/account dependency.
- Time dynamics in deck.gl are a controlled `currentTime` prop over pre-bucketed timestep data — simpler and more inspectable than CZML for this use case.
- Revisit trigger: if smooth global-context flyovers or terrain streaming quality become blocking, Cesium is the fallback; the export pipeline (§5.2) is framework-agnostic by design.

Terrain: AWS Terrain Tiles (terrarium encoding, free) via deck.gl TerrainLayer. Basemap: free vector tiles (e.g., CARTO basemap styles). No paid keys anywhere.

### 5.2 Data pipeline (lives in the Landfall repo)

A new export module: `landfall export-viz <scenario-hash>` producing a self-contained bundle per scenario:

- `meta.json` — storm, scenario config, config hash, model version, units, timestep index
- `track.json` — track points with per-timestep intensity (both historical and counterfactual tracks)
- `wind/` — per-timestep wind-field rasters (PNG-encoded or binary grids at native 150 arcsec resolution) plus the max-swath composite
- `damage.json` — per-municipality final damage + per-timestep cumulative damage series (requires the engine to emit timestep-resolved impact — see §6 engine change)
- `boundaries.json` — municipality polygons (simplified, PSGC-coded)

Bundles are committed (or Git-LFS'd if size demands) so the static site deploys with its data and every view is reproducible from the repo alone.

### 5.3 Viz app (`viz/` in the repo or `landfall-viz` companion)

React + deck.gl static site. Components: scenario picker (reads a manifest of exported bundles), 3D view (terrain + layers), timeline scrubber (Tier 2), hover tooltip (municipality name, damage, provenance), scenario A/B toggle, footer disclaimer + hash display. Deployed via GitHub Pages from CI on tag.

## 6. Required engine change (the one real risk)

Tier 2's damage accumulation needs **timestep-resolved impact output**; Landfall (confirmed by direct inspection of `landfall/impact/engine.py` and `landfall/hazard/wind.py`, 2026-07-06: no timestep or cumulative-damage logic exists anywhere in either) computes final impact from a single max-wind-swath hazard event — `TropCyclone.from_tracks()` produces one event for the whole track, and `ImpactCalc(...).impact()` runs once against it. This risk is not hypothetical, it is the current, verified state of the engine. The change: compute impact per track timestep from the incremental wind field and emit the cumulative series. This is a Landfall-repo change with its own correctness check: **the final timestep's cumulative damage must equal the existing single-pass E1 result within rounding** — that equality is the phase's exit test, run for all **four** storms (Haiyan, Rolly, Odette, Mangkhut). If reconciliation fails, Tier 2 pauses until it's understood; the viz never ships numbers that disagree with the validated ones.

Fallback if the change proves nasty: Tier 2 animates wind and track only, with final damage appearing as a single reveal at landfall+N — honest, still compelling, no engine change needed.

## 7. Phase plan (gated, exit-criterion driven)

**Phase 0 — Repo hygiene gate (four minutes, blocking).**
Both repos get About descriptions and topics; both get version tags — reconciled 2026-07-06: no `v1.0` tag was ever cut (only `v1.1` exists, and `main` has since moved to v1.3 untagged), so this gate tags the Landfall repo's actual current state (`v1.3`) rather than a `v1.0` that was never real. Exit: the metadata exists. Rationale: no visualization work begins while the repos it advertises remain unfindable. This has been pending across multiple reviews; it is now a gate.

**Phase 1 — Export pipeline (Tier 1 data).**
`export-viz` module emitting meta/track/max-swath/final-damage/boundaries for all four historical scenarios (Haiyan, Rolly, Odette, Mangkhut). Exit: four committed bundles, each hash-verified against its scenario cache.

**Phase 2 — Static 3D scene (Tier 1).**
Terrain + max wind swath + damage columns + track path + tooltip provenance for one storm (Haiyan), then the picker for all four. Exit: GitHub Pages URL renders all four storms; a hovered municipality shows damage + hash; the disclaimer footer exists.

**Phase 3 — Timestep engine change (Tier 2 prerequisite).**
Timestep-resolved impact in the Landfall engine. Exit: cumulative-final equals single-pass E1 within rounding, all four storms, reconciliation table committed. Fallback decision point lives here.

**Phase 4 — Time-dynamic replay (Tier 2).**
Scrubber, animated wind painting, accumulating damage columns, per-timestep intensity on the track. Exit: the Goni/Catanduanes replay plays end to end in the browser — the compact-core story, visible.

**Phase 5 — Comparison mode + ship.**
A/B scenario toggle (historical vs counterfactual; later, waterfall configs), README section with embedded GIF, tagged release. Exit: release tagged, GIF in both the viz README and Landfall's README. **The distribution post remains a named deliverable of this phase** — the animated replay was the stated reason to defer posting; when it exists, the deferral expires.

Slippage policy: Mulat and applications first; Landfall v1.1 waterfall phases may interleave (Phase 2's side-by-side rendering actively helps hazard-config debugging); phases pause at boundaries; no Phase 4 before Phase 3's reconciliation table.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Timestep impact never reconciles with E1 | §6 fallback (wind-only animation); the discrepancy itself gets documented — it would be a real finding about swath-vs-incremental impact computation |
| Bundle sizes bloat the repo | Native-resolution grids are small (regional 150 arcsec); PNG-encode rasters; Git-LFS threshold decided in Phase 1 |
| Rendering implies false precision | §4.3 is binding: cell-faithful rendering, stated scales, no smoothing |
| deck.gl terrain quality disappoints | Revisit trigger to Cesium is pre-declared; export format is framework-agnostic |
| Scope creep toward Tier 3 / game-engine polish | §2 rejects Tier 3 permanently; "would this change any number?" — if no and it costs >1 session, roadmap it |
| Viz becomes the new reason the post never ships | Phase 5 names the post as a deliverable; Phase 0 gates the metadata now |

## 9. Definition of shipped

Live GitHub Pages URL; all four historical storms renderable in 3D with provenance tooltips; Goni time-dynamic replay working; reconciliation table committed (or fallback documented); GIF in both READMEs; release tagged; distribution post published with the replay as the hook.

---

*Every rendered value in this product traces to a committed scenario cache and config hash. The visualization adds views, never numbers.*
