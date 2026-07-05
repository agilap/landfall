# Phase 2 result — three-storm replay, exposure sanity check, E1 draft

## What changed from Phase 1

Refactored the Haiyan-only pipeline into a storm-generic one (`landfall/storms.py` registry
+ generic `hazard/tracks.py`, `hazard/wind.py`, `exposure/litpop.py`,
`impact/engine.py`). Regression-checked against Phase 1's Haiyan result before trusting the
refactor — identical output ($49,327,691.86 / 9,168,006 affected).

Two IBTrACS SID guesses from initial registry entries were **wrong** and caught immediately
by the `get_track` name-assertion (PRD's "fail loud, not plausible" principle working as
intended): Goni's SID was `2020299N11144`, not the initially-entered `2020296N10133`; Rai's
was `2021346N05145`, not `2021332N05144`. Found the correct SIDs by fetching full-basin/year
IBTrACS data and filtering by name rather than guessing again.

ROI bounds for Rolly and Odette were set by visually inspecting each storm's track and wind
field plot (`outputs/maps/{rolly,odette}_{track,wind}.png`) and widening until the peak
intensity sat comfortably clear of the frame edge, same process as Haiyan's Phase 1 ROI.

## Simulated results (all three storms)

```
storm    total_damage_usd    affected_population   roi_total_pc_usd
haiyan   49,327,691.86       9,168,006             69,132,391,568.90
rolly    404,699.55          731,168               7,572,368,184.79
odette   184,074,084.28      10,541,655            69,278,382,536.27
```

Exposure sanity check: total PHL produced-capital exposure (whole country, `fin_mode='pc'`)
is $645.6B — a plausible order of magnitude for produced-capital wealth accounts in an
economy this size (produced-capital/GDP ratios of 1.5–2x are typical; PHL GDP ~$400B). Not
obviously broken.

## E1 — Historical validation (draft)

| Storm | Simulated damage (USD) | NDRRMC-recorded damage (USD, approx.) | Error factor |
|---|---|---|---|
| Haiyan (2013) | $49.3M | ~$917M (PHP 39.82B infra+agri, Sitrep 104, ~43.4 PHP/USD) | **18.6× under** |
| Rolly (2020) | $0.40M | ~$233M (PHP 11.3B infra+agri, ~48.5 PHP/USD) | **575× under** |
| Odette (2021) | $184.1M | $459M–$915M (PHP 23.4B→47B infra+agri, figure grew as assessment continued; ~51 PHP/USD) | **2.5–5.0× under** |

FX rates are rough historical-period averages, not precise transaction-date rates — good
enough for order-of-magnitude comparison, not for anything tighter. NDRRMC figures
themselves evolved over each event's assessment timeline (Odette's roughly doubled from
Dec 2021 to its later total) — the "ground truth" carries its own uncertainty, which is
worth remembering before treating our error factor as a single precise number.

**Acceptance criterion (PRD §6): the table exists and is honest — there is no target error
factor.** Odette lands close to the PRD's own stated expectation of typical 2–5x TC-model
error. Haiyan and especially Rolly do not, and that gap is now understood mechanistically
rather than hand-waved:

### Root-cause finding: the WP2 calibrated damage curve is very conservative at moderate wind speeds

Inspected the actual WP2 (Eberenz et al. 2021, TDR calibration) mean-damage-ratio curve:

```
wind (m/s):  25    30       35       40       45      50      55      60      70     80
MDR:         0     0.0018%  0.019%   0.068%   0.17%   0.33%   0.58%   0.93%   2.0%   3.6%
```

MDR is essentially zero below ~30 m/s and rises slowly even into Cat. 4/5 wind speeds —
even at 80 m/s (borderline Cat. 5), only ~3.6% of produced-capital value is estimated
damaged. This curve shape, combined with each storm's **value-weighted mean wind intensity
at exposure points**, explains the ranking:

| Storm | Value-weighted mean intensity at exposure (nonzero, m/s) | % of exposure value under any wind |
|---|---|---|
| Haiyan | 28.0 | 84.1% |
| Rolly | 21.7 | 61.2% |
| Odette | 44.0 | 96.5% |

Rolly's value sits mostly **below the curve's effective start** (~25–30 m/s) — consistent
with Goni's real-world reputation as an unusually compact, small-wind-field storm: extreme
peak intensity right at the Catanduanes eyewall, but most of Bicol's economic activity
(Naga, Legazpi, etc.) sat far enough from the direct track to see much lower sustained
winds. Odette's broader wind field pushed far more exposure value well into the curve's
higher-MDR range, which is why its error factor is dramatically better than the other two.

This points at the **impact/vulnerability layer**, not a code bug: either (a) this
particular WP2/TDR-calibrated curve is genuinely conservative for the Philippines relative
to what NDRRMC counts as "damage," or (b) `fin_mode='pc'` (produced capital) is a
structurally different — and larger — value base than whatever mix of housing, agriculture,
and infrastructure NDRRMC sitreps aggregate, diluting a legitimate raw damage number into a
tiny ratio. Both hypotheses point the same direction and neither is fixed by retuning
numbers to match — per PRD §6, that would be exactly the failure this project argues
against.

### What's not yet ruled out

- Whether `fin_mode='gdp'` or a different value base produces a meaningfully different
  (and more defensible) error factor — worth a quick comparison run, not yet done.
- Whether NDRRMC's "damage" figures include categories (standing crops, informal housing)
  that produced-capital accounting excludes by definition, which would mean no exposure
  choice fixes this — the two figures may simply be measuring different things.

## Next (Phase 3)

Scenario compiler (NL → validated config) and counterfactual track perturbation. The
error-attribution work above stays open — E1's final write-up (with the `fin_mode`
comparison) can land alongside Phase 4's full narration pass rather than blocking Phase 3.
