# Phase 1 result — first damage number (Haiyan)

**Definition of done met:** one damage number for Haiyan over the Visayas ROI, produced by
the full hazard → exposure → impact pipeline described in PRD §5.1.

## Result

```
total_damage_usd:     49,327,691.86
affected_population:  9,168,006  (population under any nonzero hazard intensity, i.e.
                                  >= intensity_thres ~17.5 m/s — a crude proxy, not a
                                  damage-function-based estimate; see landfall/impact/haiyan.py)
impf_id:              7
impf_region:          WP2 (Western Pacific), Eberenz et al. 2021
calibration_approach:  TDR (total damage ratio, TDR=1.0)
hazard_model:          H1980 (Holland 1980, per PRD §5.1)
```

Reproduce with: `python -m landfall.impact.haiyan` (inside the `landfall` conda env).

## Honest assessment

This number is **very low** against Haiyan's actual recorded damage — NDRRMC/EM-DAT
figures for Haiyan are commonly cited in the $2–3B+ range (some estimates higher), putting
today's error factor far outside the PRD's own stated expectation of a typical 2–5× model
error. Per PRD §4.3 ("honest error is the product"), this is recorded rather than tuned
away. Hypotheses to test in Phase 2's validation pass, in priority order:

1. **`fin_mode='pc'` (produced capital) may be the wrong or an incomplete total-value
   base.** NDRRMC damage figures typically aggregate agriculture, housing, and
   infrastructure loss more broadly than produced-capital stock alone.
2. **WP2 calibrated damage ratios may be conservative** at the wind speeds this ROI
   mostly saw (core Cat. 5 winds only hit a narrow band; see `haiyan_wind.png`).
3. **Exposure resolution/coverage** — worth comparing against a coarser sanity check
   (e.g. total PHL produced capital × rough damage fraction) to see if the ROI clip or
   grid-matching is silently dropping value.

Do not adjust the calibration or exposure to hit a target number — attribute the error
across layers first, per PRD §6 (E1 acceptance criterion: "the table exists and is
honest").

## Known deviations from a clean run (both necessary, both documented in code)

1. **`ignore_distance_to_coast=True`** in `landfall/hazard/wind.py` — CLIMADA's default
   coastal-distance filter needs a NASA raster download that returned 403 from this
   network. Wind is computed everywhere in the ROI, not just near-coast, as a result.
2. **GPW population substitute** — CLIMADA's LitPop exposure unconditionally loads a GPW
   population raster (confirmed: even with the population exponent set to 0). The
   official file requires a free NASA Earthdata account and a manual SEDAC download;
   SEDAC's server was unresponsive both from the user's browser and via a direct `curl`
   from this machine. Substituted WorldPop's Philippines population raster instead
   (`scripts/build_gpw_substitute.py`), padded to fully enclose the national boundary
   polygon and placed at the path CLIMADA expects. Total substituted population
   (~110.2M) matches the Philippines' actual 2020 population — a legitimate substitute,
   not an approximation of last resort. **Revisit if/when a real GPW download succeeds**
   (retry SEDAC later, or ask the user again) — the substitute script would then be
   unnecessary, though the WorldPop-based result is arguably higher-resolution than
   native GPW (3 arc-sec vs. 30 arc-sec) and could reasonably just stay.

## Next (Phase 2)

NDRRMC sitrep extraction for Haiyan, Rolly, and Odette; E1 table with the error
attribution above formalized; exposure sanity checks (total PHL `pc` value vs. total
disaggregated ROI value, as a basic conservation check).
