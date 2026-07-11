# Landfall Viz

Browser-based **3D visualization of committed Landfall scenario bundles**. This is the
companion app described in [`../landfall-viz-prd.md`](../landfall-viz-prd.md) — Phase 2
(static Tier 1 scene): terrain + max wind swath + per-municipality damage columns +
storm track, with always-visible provenance.

> Research/preparedness demonstration only; counterfactuals are hypothetical.

## Run it

```bash
cd viz
npm install
npm run dev
```

Then open the printed local URL (default http://localhost:5173) in a **desktop** browser.
The terrain and basemap load from public keyless tile services (AWS Terrain Tiles +
CARTO basemap), so an internet connection is required for the ground; the scenario data
itself is served locally from `public/data/`.

## What it renders

Pick one of the four historical storms (Haiyan 2013, Mangkhut 2018, Odette 2021, Rolly
2020) in the top-left panel. For the selected scenario the scene draws:

- **Terrain** — AWS Terrain Tiles (terrarium elevation) draped with the CARTO basemap.
- **Max wind swath** — `wind/max_swath.json` rasterized to a `BitmapLayer`, one texel per
  model cell at native 150″ (0.0417°) resolution with **nearest-neighbour sampling — no
  smoothing**. Sequential color ramp keyed to m/s; the legend (top-right) states the units
  and the value range it spans. Cells below ~17 m/s are transparent.
- **Damage columns** — a `ColumnLayer` extruded at each municipality centroid, joined from
  `boundaries.json` to `damage.json`'s `damage_by_municipality` by `(province,
  municipality)`. Height is **log-scaled** (`log₁₀(USD)`, 7 km per decade above $1k); the
  scale is labeled in the legend, not just in code.
- **Storm track** — a `PathLayer` from `track.json`, ordered by time.

Hover a damage column for its province, municipality, damage (USD), affected population,
and the bundle's `source_cache_key`. The footer shows the disclaimer, `scenario_hash`,
`source_cache_key`, and `landfall_version` **at all times**, not only on hover.

## Data source and boundaries

This app **consumes committed bundles only — it never computes**. Every rendered value
traces to a bundle under `public/data/<scenario_hash>/` (listed in
`public/data/manifest.json`), which Phase 1's `landfall export-viz` produced from a
scenario cache. If a view needs data the engine doesn't emit, the engine changes first
(in the Landfall repo, with its own correctness check), then the viz consumes it — see
the PRD's product principle "No new numbers."

Nothing here depends on the Python `landfall` package; it is a pure static frontend.

## Stack

Vite + React + TypeScript + [deck.gl](https://deck.gl) v9 (`@deck.gl/core`, `/react`,
`/layers`, `/geo-layers`). deck.gl over CesiumJS per PRD §5.1. Centroids are computed
in-app (shoelace centroid of the largest exterior ring) — no heavy geo dependency.

## Scope (Phase 2)

Static 3D scene only. **No timeline / animation** — that is Phase 4, gated behind the
Phase 3 timestep engine change that has not happened. No in-browser scenario computation,
no mobile optimization (desktop-first; must not crash on mobile), no game-engine effects
(Tier 3 is permanently rejected — PRD §2).
