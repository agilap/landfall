# Week 1 plan — "First number"

**Definition of done (from PRD §7):** one damage number for one storm (Haiyan), however wrong.

Deliberately minimal. Everything here uses CLIMADA tutorials verbatim before customizing
(PRD risk mitigation: the learning curve is the Week 1 risk, not the physics).

## Session 1 — Environment (highest-risk step, do first)

1. Install mamba/miniforge if not present.
2. `mamba create -n landfall -c conda-forge climada python=3.11`
   - CLIMADA via conda-forge is the supported path; PyPI installs break on GDAL/geo deps.
3. Smoke test: `python -c "from climada.hazard import TropCyclone, TCTracks; print('ok')"`
4. `pip install -e .` inside the env (for the `landfall` package itself).
5. Record exact versions in `docs/environment.md` (CLIMADA pin matters for reproducibility).

**Gate:** do not proceed until the smoke test passes. If install fights back >1 session,
that's the whole session's output and that's fine — log what broke.

## Session 2 — Haiyan track ingestion

1. `TCTracks.from_ibtracs_netcdf(storm_id='2013306N07162')` (Haiyan's IBTrACS ID — verify
   against IBTrACS at fetch time, don't trust this file).
2. Plot the raw track over the Philippines; eyeball landfall over Guiuan/Tacloban.
3. Save the fetched track to `data/tracks/` so subsequent runs are offline + deterministic.
4. Code lands in `src/landfall/hazard/tracks.py` — thin, tutorial-grade, no perturbation
   logic yet (that's Week 3).

## Session 3 — Wind field

1. Define the Visayas region-of-interest centroids at 150 arcsec (~4.5 km), per PRD §5.1.
2. `TropCyclone.from_tracks(...)` → max sustained wind grid (Holland 1980, CLIMADA default).
3. Render the wind field with matplotlib over a basemap → `outputs/maps/haiyan_wind.png`.
   This is a future hero image; don't polish it yet.

## Session 4 — First damage number

1. `LitPop` exposure for the Visayas ROI (this download can be slow — start it early or
   in the background).
2. Attach CLIMADA's calibrated Western Pacific TC impact function (Emanuel-type sigmoid,
   `ImpfTropCyclone`) — cited defaults, zero tuning.
3. `ImpactCalc` → total damage (USD) + affected population for the ROI.
4. **Write the number down** in `docs/week1-result.md` with the exact config that produced
   it. However wrong. That closes Week 1.

## Explicitly deferred

- Rolly/Odette replays, NDRRMC sitrep extraction, E1 table → Week 2.
- Track perturbation, scenario compiler, E3 → Week 3.
- Narrator, verifier, RAG, E2 → Week 4.
- Scenario-hash cache: introduce in Week 2 when there's more than one run to cache.

## Known traps

- IBTrACS full download is ~300 MB on first `from_ibtracs_netcdf` call; it's cached by
  CLIMADA afterward. Do it on a good connection.
- LitPop needs its input rasters downloaded on first use too.
- RAM: regional 150-arcsec is fine in 14 GB (PRD §5.4), but don't accidentally request
  nationwide centroids.
