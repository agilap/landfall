> ⚠️ **Landfall is a research and preparedness demonstration. It is NOT an operational
> forecasting tool and must not be used for emergency decision-making.** Damage estimates
> from tropical cyclone models of this class are routinely off by 2–5×; documenting that
> error honestly is the point of this project.

# Landfall

[![GitHub](https://img.shields.io/badge/GitHub-agilap%2Flandfall-blue?logo=github)](https://github.com/agilap/landfall)

**Counterfactual typhoon damage simulation for the Philippines.**

A deterministic hazard–exposure–vulnerability engine (CLIMADA) computes all damage
figures for four historical Philippine typhoons — Haiyan (2013), Rolly (2020),
Odette (2021), and Mangkhut (2018) — and for counterfactual scenarios (track offset,
bearing, intensity delta).
An LLM layer narrates cached engine output as a plain-language briefing; **every numeric
claim in generated briefings is mechanically verified against the impact engine's cached
output before it reaches the user, with ungrounded claims regenerated or redacted.** A
local retrieval layer answers "what actually happened" questions against NDRRMC situation
reports, with citations.

Physics computes. The LLM narrates. No load-bearing number originates in a language model.

## Hazard maps

Holland (1980) max-sustained-wind fields, synthesized from IBTrACS best-track data over
each storm's regional exposure corridor:

| Haiyan (2013) | Rolly (2020) | Odette (2021) |
|---|---|---|
| ![Haiyan wind field](outputs/maps/haiyan_wind.png) | ![Rolly wind field](outputs/maps/rolly_wind.png) | ![Odette wind field](outputs/maps/odette_wind.png) |

## Status

Phases 1–8 of the PRD (`landfall-prd.md`) are done; v1.3 added a 4th storm — see below.
What's built and what isn't, honestly:

**Built:** IBTrACS track ingestion for all four storms; Holland (1980) wind fields;
LitPop exposure nationally, with a hybrid OSM-buildings + PSA-census layer for
Catanduanes/Albay/Camarines Sur (v1.1 Phase 3 — see E1 below); WP2-calibrated impact
functions (Eberenz et al. 2021, EDR calibration with an interquartile uncertainty range
as of v1.2 Phase 1 — see below); per-municipality
damage and affected-population breakdown (GADM administrative boundaries, spatially
joined against impact-engine output — Odette's top municipality is Cebu City, Haiyan's is
Tacloban City, both matching real-world reporting); a validated, hard-range-checked
counterfactual scenario schema (track offset/bearing, intensity delta) with a
scenario-hash disk cache; an LLM narrator with a groundedness verifier that regenerates or
redacts any numeric claim it can't trace to cached impact output; a local RAG interrogator
(bge-m3 embeddings, no API calls) over NDRRMC sitreps with source citations, using
table-aware extraction (`pdfplumber`) so a retrieved number stays attached to its own
table row instead of a neighboring one, plus LLM-assisted query rewriting to compensate
for retrieval missing a passage that a terser keyword query finds; an answer-synthesis
layer on top of that retrieval, with its own groundedness check — **and a real
limitation that check surfaced and Phase 8 partially fixed**, see below.

Also built: the **NL → scenario-config compiler** (`src/landfall/llm/compiler.py`) and
its E3 eval — with a disclosed caveat. PRD §6 says E3's ground-truth configs are
hand-labeled by the author and not delegable; at the author's explicit direction, the
eval set (now 85 cases, after adding range-phrased, storm-name, and refusal-phrasing
test cases) was instead authored by
the same coding agent that built the compiler.
That is a circularity risk (an agent writing both sides of its own exam), so it is
stated here rather than hidden, and the eval set is plain JSON
(`evals/e3_dataset.json`) open to author audit.

**Not built / deferred:**
- **Tagalog narration** — English only so far; same verifier applies once added.
- **Attribution as a proven property in general** — Phase 8's table-aware extraction
  fixes the specific documented misattribution (a province-level subtotal read as
  belonging to one municipality), but doesn't guarantee every retrieved row is about the
  entity a question asks about; an eval for retrieval/attribution quality analogous to
  E2/E3 isn't built, for the same reason E3 flagged — it needs human-checked ground truth,
  not agent-generated ground truth. See `docs/phase8-result.md`.
- **Stack deviation:** PRD §5.2 specifies an Anthropic Haiku-class model for the narrator;
  no Anthropic key was available in the build environment, so the narrator uses OpenAI's
  `gpt-4o-mini` instead, per the author's direction. Functionally equivalent for this
  project's purposes.

See `docs/phase1-plan.md` through `docs/phase8-result.md` (v1), `docs/v1.1-phase1-result.md`
through `docs/v1.1-phase5-result.md` (v1.1's underestimation fix),
`docs/v1.2-phase1-result.md` through `docs/v1.2-phase2-result.md` (v1.2's
calibration-uncertainty fix), and `docs/v1.3-phase1-result.md` (v1.3's 4th storm) for
the session-by-session build log, including real bugs caught before they reached a
shipped number (a wrong IBTrACS storm ID, a stale post-redaction groundedness report, a
wasted GPU-torch install, and a hardcoded per-storm year dict that crashed on the 4th
storm), each
described alongside how it was caught.

## Usage

```
pip install -e .
landfall run haiyan                                   # historical replay
landfall run rolly --offset-km 100 --bearing 0         # counterfactual: 100 km north
landfall narrate odette --intensity-delta 20           # + verified narration
landfall compile "Shift Rolly 50 km south"              # NL -> ScenarioConfig
landfall ask "What happened in Catanduanes?" --storm rolly   # sitrep RAG interrogator
```

Damage is a point estimate plus an interquartile range (v1.2 — see below for why a
range, not a single number). `landfall run haiyan`:

```
Total damage (USD): 695,357,863.53 point estimate (range: 49,596,773.73 - 2,891,237,057.79)
Affected population: 9,329,251
Top municipalities by damage:
  Tacloban City, Leyte: $166,503,494.24
  Ormoc City, Leyte: $76,725,557.55
  ...
```

`landfall narrate odette --intensity-delta 20` narrates the range directly, with the
groundedness verifier rejecting any figure the model might invent between the two
bounds (e.g. an averaged midpoint):

```
In this counterfactual scenario based on Typhoon Odette (2021), the damage is estimated
to be between $341,982,930 and $29,251,253,997.68. The affected population is
approximately 9,248,109 people. The scenario reflects a change in the typhoon's track
and intensity, which could lead to significant economic impacts.

[groundedness: 4/4 final, 4/4 raw]
```

## E1 — Historical validation (v1 baseline)

| Storm | Simulated damage (USD) | NDRRMC-recorded damage (USD, approx.) | Error factor |
|---|---|---|---|
| Haiyan (2013) | $49.3M | ~$917M | **18.6× under** |
| Rolly (2020) | $0.40M | ~$233M | **575× under** |
| Odette (2021) | $184.1M | $459M–$915M | **2.5–5.0× under** |

No target error factor — this table exists to be honest, not to hit a number (PRD §6).
Odette landed inside the PRD's own stated expectation for typical TC-model error
(2–5×); Haiyan and Rolly did not. Full original derivation in `docs/phase2-result.md`.
This table is kept exactly as it stood before v1.1 — the before is part of the story
the section below tells.

## v1.1 — the underestimation fix, and what it cost

Four phases, each holding everything but one layer fixed, Odette held out of every
calibration decision throughout:

| Storm | Baseline (TDR curve) | +PHL curve (Phase 1: RMSF) | +hazard config (Phase 2) | +Bicol exposure (Phase 3) | NDRRMC actual |
|---|---|---|---|---|---|
| Haiyan (2013) | $49.3M — 18.6× under | $775.6M — **1.18× under** | no change | $775.6M — 1.18× under | ~$917M |
| Rolly (2020) | $0.40M — 575× under | $7.86M — 29.6× under | no change | $91.6M — **2.54× under** | ~$233M |
| Odette (2021) — **held out** | $184.1M — 2.5–5.0× under | $3,532.1M — **3.9–7.7× over** | no change | $3,532.1M — 3.9–7.7× over | $459M–$915M |

**Layer 1 — vulnerability curve (Phase 1).** The WP2 (Philippines) impact function's
`TDR` calibration was swapped for `RMSF` — both are published Eberenz et al. 2021
calibrations of the *same* curve (NHESS 21:393–415,
https://doi.org/10.5194/nhess-21-393-2021), not an invented parameter. The paper itself
names TDR as producing an anomalously flat curve for WP2–4 specifically, because it
lets a region's largest-damage historical events dominate the fit; RMSF weights every
matched event equally instead. This one config change did almost all of Haiyan's
recovery (18.6×→1.18× under) and a meaningful chunk of Rolly's (575×→29.6×). Curve
shapes compared in `docs/impact_curves_tdr_vs_rmsf.png`; full derivation in
`docs/v1.1-phase1-result.md`.

**Layer 2 — hazard configuration (Phase 2), a negative result.** Tested whether Rolly's
remaining 29.6× gap was hazard-side: compared IBTrACS' USA/JTWC vs Tokyo/JMA tracks
directly, checked simulated peak wind over Catanduanes against observed landfall
intensity (correcting the investigation's own reference figure along the way — "~62
m/s 1-min sustained" turned out to be JMA's raw 10-minute value mislabeled; properly
converted, the true comparison range is 81.9–87.5 m/s), and ran three sensitivity tests
(alternate agency, RMW, grid resolution). None improved the peak-wind estimate. No
configuration change adopted — reported as a clean negative result, not reworked until
something moved. Full derivation, including an unexplained anomaly (Bato, Rolly's
actual landfall municipality, shows far lower simulated wind than its neighbors), in
`docs/v1.1-phase2-result.md`.

**Layer 3 — exposure (Phase 3), the layer that actually closed most of Rolly's gap.**
LitPop's population×nightlights weighting undervalues rural, low-luminosity provinces —
exactly Catanduanes, Albay, and Camarines Sur. Replaced with real OSM building
footprints (footprint area × ₱9,949/m² construction-cost rate, a commercial QS-guide
national average — PSA's own regional cost statistics are blocked from this
environment, a disclosed lower-authority substitute) and PSA's actual 2020 census
population by barangay (two real name-join bugs — PSA's parenthetical alt-names and
city-name word-order differences — were caught mid-build because they were silently
dropping entire municipalities' population, not left in). Catanduanes' total exposed
value jumped 27.79× over LitPop's figure, checked against per-capita plausibility
before being trusted (LitPop implied an implausible $103/person; the new figure's
~$2,850/person is plausible against ~$3,300 Philippine per-capita GDP). **Caveat that
matters**: OSM building-mapping completeness is wildly uneven — 102% of PSA's
housing-unit count in Catanduanes, but only 57.8% in Albay and 19.2% in Camarines Sur —
so Rolly's 2.54×-under result was reached *despite* an incomplete building dataset in
two of three provinces; the true remaining gap may be smaller still. Full derivation in
`docs/v1.1-phase3-result.md`.

**The flood/rain-attributable remainder — not answerable from these sitreps.** Phase 4
tried to estimate how much of Rolly's recorded damage a wind-only model should be
expected to miss, using the NDRRMC sitrep already in the RAG corpus (`sitrep_12.pdf`,
as of 11 November 2020). Its infrastructure (₱12.87B nationwide, ₱12.23B in Region V
alone) and agriculture (₱5.01B nationwide, ₱3.58B in Region V, sourced explicitly to
the Department of Agriculture) tables categorize damage by economic **sector**, not by
physical **cause** — a rice paddy destroyed by wind and one destroyed by flood
inundation are indistinguishable line items. A handful of free-text descriptions
explicitly name flooding (e.g. a Camarines Sur water facility: *"Flooded office
building... submerged water meters"*), but too sparsely to extrapolate a percentage.
**No defensible flood/rain-share range is reported here** — inventing one would imply
precision the source data doesn't have. One suggestive side-observation: the same
sitrep *does* carry an explicit "FLOOD CONTROL" cost line for MIMAROPA (₱2.51B) but
none at all for Region V — weak evidence, not proof, that NDRRMC itself didn't
consider Bicol's damage flood-dominated enough to break out separately. A separate,
unresolved discrepancy this investigation surfaced: this same sitrep's own Region V
infra+agri total (≈$318.6M) is higher than the ~$233M figure used as Rolly's "actual"
throughout this table — not reconciled here. Full derivation in
`docs/v1.1-phase4-result.md`.

**Odette's verdict — the credibility check for the whole exercise, now explained.**
Odette was the only storm that started in-range (2.5–5.0× under). It now sits at
**3.9–7.7× over** — a full reversal, not a drift, and it happened entirely in Phase 1;
Phases 2 and 3 never touched it (zero ROI overlap). v1.1 Phase 5 investigated why,
rather than leaving it as a hypothesis. The first suspect — Metro Cebu's concentrated,
high-value exposure (72% of Odette's total damage, at a moderate simulated 49–58 m/s) —
turned out to be where the dollars sit, not why the total overshot: Metro Cebu's
*share* of the total barely moved between curves (72.7%→72.2%). **The real mechanism
is arithmetic**: the TDR→RMSF curve swap multiplies every storm's total by a
near-uniform factor (15.72× for Haiyan, 19.43× for Rolly, 19.19× for Odette — all in
the same band, verified exactly, not estimated), because each storm's damage-weighted
exposure sits somewhere in the curve's sensitive middle range regardless of its
specific wind-speed distribution. Applying each storm's own multiplier to its
pre-existing TDR-era deficit **predicts the post-RMSF error factor for all three
storms almost exactly** (e.g. Odette: 2.5–5.0× under ÷ 19.19 → 3.84–7.68× over,
matching the actual 3.9–7.7× over). **Odette didn't get a uniquely bad multiplier — it
started closest to correct under TDR, so the same proportional fix that rescues Haiyan
and Rolly necessarily overshoots the one storm that needed the least correcting.** This
is a structural property of swapping one single national `v_half` for another, not a
storm-specific bug: no single v_half can close an 18.6×, a 575×, and a 2.5–5× deficit
simultaneously without over- or under-shooting at least one. This table should not be
read as "the model is now well-calibrated" — it's better calibrated for two of three
storms, at the cost of the third, by mathematical necessity, and that trade stays
visible here rather than getting rounded off into "2 of 3 improved." Full derivation in
`docs/v1.1-phase5-result.md`.

### What's still unexplained

- **Rolly's residual 2.54× under** — real, but exposure Phase 3 was reached through an
  incomplete OSM dataset in two of three provinces, so this number itself carries
  uncertainty in an unclear direction.
- **The flood/rain share of Rolly's damage** — genuinely unanswerable from this corpus,
  not just undone.
- **The $233M vs ≈$318.6M Rolly reference-figure discrepancy** surfaced in Phase 4 —
  unreconciled.
- **Bato's anomalously low simulated wind** (Phase 2) relative to its neighbors, despite
  being Rolly's reported landfall municipality — unexplained, not investigated further.

## v1.2 — reporting genuine calibration uncertainty instead of a doomed point estimate

v1.1 Phase 5 proved the Odette problem was structural: swapping one national `v_half`
for another multiplies every storm's damage total by a near-uniform ~16–19×, so no
single point-estimate curve can close Haiyan's 18.6×, Rolly's 575×, and Odette's
2.5–5× deficits simultaneously without overshooting the shallowest one. v1.2 stopped
searching for a better single number and asked whether the calibration data CLIMADA
already ships could report a *range* instead.

**Ruled out first**: filtering Eberenz et al. 2021's 83-event WP2 calibration dataset
(each event individually fitted, tagged with `Surge`/`Rain`/`Flood`/`Slide` flags —
Haiyan itself is in it, individually fitted to `v_half=50.9`, flagged `Surge=True`) down
to the 47 "clean," unflagged wind-dominated events gives a median `v_half=81.0` —
nearly identical to the RMSF value already in use, and not statistically distinguishable
from the 36 flagged events (p=0.16). Per-event variance swamps any hazard-contamination
signal; this isn't where the problem lives.

**What works**: CLIMADA exposes any quantile of that same 83-event distribution
(`calibration_approach="EDR", q=...`) — already-published, already-bundled data, not a
new curve. Computing the interquartile range (q0.25–q0.75) for all three storms under
the current pipeline:

| Storm | q0.25 (high damage) | Point estimate (q0.5) | q0.75 (low damage) | NDRRMC actual | Bracketed? |
|---|---|---|---|---|---|
| Haiyan (2013) | $2,891.2M | $695.4M | $49.6M | $917M | **✓** |
| Rolly (2020) | $456.8M | $81.4M | $5.4M | $233M | **✓** |
| Odette (2021) — held out | $23,530.7M | $3,095.2M | $185.1M | $459–915M | **✓** |

**All three storms' actual recorded damage falls inside the interquartile range —
including Odette, the storm every point-estimate approach in v1.1 broke.** This is the
first thing tried across the whole v1.1/v1.2 effort that works for all three
simultaneously. Not a new fragility curve — CLAUDE.md's hard non-goal on custom curves
is unaffected; it's a different quantile selection from data already cited in Phase 1.

**The honest catch, stated plainly rather than hidden**: the ranges are wide, and
Odette's upper bound ($23.5B) is not a plausible standalone damage estimate for any
Philippine typhoon on record — it's what the published distribution's low-`v_half`
tail produces when applied to Odette's exposure. It is reported un-trimmed here rather
than capped to look more credible: deciding in advance which parts of a genuinely messy
published uncertainty distribution to hide would be a worse failure mode than an
uncomfortably wide number. The width is itself the finding — a wind-only model
calibrated this way cannot narrow Philippine typhoon damage down to better than roughly
two orders of magnitude for some storms.

Not touched in Phase 1: the narrator, verifier, and CLI still spoke in the single
point-estimate number (`total_damage_usd` unchanged in shape, so nothing downstream
broke). Full derivation in `docs/v1.2-phase1-result.md`.

**v1.2 Phase 2** closed that gap: the narrator now states damage as a low–high range
("an estimated $185.1M to $23,530.7M in damage") instead of a point estimate, with the
system prompt explicitly forbidding the model from averaging the two bounds into a new
figure — that would be exactly the kind of invented statistic the groundedness verifier
exists to catch, so both bounds are permitted reference values and nothing between them
is. Verified end to end for a historical replay (Odette: correctly stated $185,091,240.57
to $23,530,739,646.49, 4/4 grounded) and a counterfactual (Rolly +100km/+20kn: correctly
labeled as a counterfactual, range stated correctly, 4/4 grounded). Per-municipality
breakdown remains point-estimate only. Full derivation in `docs/v1.2-phase2-result.md`.

## v1.3 — a 4th historical storm (Mangkhut/Ompong, 2018), and what adding one broke

PRD §2's original v1 non-goal ("no nationwide coverage — only regions affected by the
three replay storms") was a deliberate boundary. Adding a 4th storm was explicit author
direction, not organic scope creep — same verification discipline, one storm at a time.

**Two candidates checked before picking one.** Mangkhut/Ompong (2018, Northern Luzon)
and Bopha/Pablo (2012, Mindanao→Visayas) were both fetched and verified via IBTrACS
before choosing — an initial guess at both storms' SIDs was wrong and had to be
corrected by searching IBTrACS by name instead of guessing the ID pattern. Bopha's real
PH-transit track substantially overlaps **both** Haiyan's and Odette's existing ROIs,
reopening the multi-storm overlap complexity from v1.1 Phase 3; Mangkhut's Northern
Luzon corridor overlaps none of the other three. Sourced the same way as the original
three: IBTrACS SID `2018250N12170` (verified against the fetched track's own name),
PH-local name "Ompong" (confirmed via two independent sources, not recalled from
memory), ROI bounds derived from the actual PH-transit segment's coordinates, and the
sitrep (NDRRMC Update SitRep No. 50) found on ReliefWeb — `ndrrmc.gov.ph` blocks
automated requests, same as before.

**E1 ground truth**: the sitrep's own "COST OF DAMAGES" table gives a combined
Infrastructure + Agriculture total of ₱33,692,891,286.73, converted at the World Bank's
2018 annual-average rate (₱52.6614/USD, fetched directly — not reused from Rolly's 2020
rate) to **$639,802,058.47**.

| Storm | Point estimate | Interquartile range | NDRRMC actual | Error factor | Bracketed? |
|---|---|---|---|---|---|
| Mangkhut (2018) | $125,983,187.57 | $7,589,941.04 – $931,567,868.90 | $639,802,058.47 | **5.08× under** | **✓** |

The actual figure lands inside the interquartile range — a real out-of-sample check of
v1.2's range-calibration finding, on a storm it had never seen, not just a fourth data
point restating what three storms already showed. 5.08× under sits in the same rough
band as the other three storms' final error factors, consistent with v1.1 Phase 5's
finding that no single calibration fits all of them precisely. Geographic sanity check:
top-damage municipality is Laoag City, Ilocos Norte — sitting almost exactly on the
track's real exit path, independently consistent with real-world reporting.

**A wind-field sanity check that could have looked like a bug but wasn't.** Itogon,
Benguet — where a rain-triggered landslide killed ~100 people, the storm's single
deadliest incident — showed **0 m/s** simulated wind at the nearest centroid. Checked
before trusting it: a full north-south transect shows a smooth, continuous field (0 kn
below 16.83°N, ramping through the ~17.5 m/s threshold, peaking near Baggao's landfall
latitude, decaying smoothly north), not a cliff or ROI-boundary artifact. Itogon's
near-zero simulated wind is a genuine model output — a clean, independent illustration
of the wind-only blind spot, since the deadliest incident here was rain/geohazard-
driven, the same category of gap already flagged for Rolly's flood share.

**A second real compiler bug, found the same way as the first.** Testing the new
storm's name handling found "Typhoon Mangkut" (missing the "h") silently accepted as
Mangkhut, stable across repeats. An explicit contrastive prompt example — the same fix
that resolved "Yolande" and "Ray" — did **not** resolve this one; still 4/4 wrongly
accepted after the fix. Harder and more stable than the flaky "Typhoon Rai" case.
Given the earlier oscillation risk documented in E3's own history (fixing one alias
broke another, repeatedly), further tuning against this single case wasn't attempted —
disclosed as a known-failing case in `evals/e3_dataset.json` (id 85) instead of excluded
to protect the accuracy number. Full suite with it included: 48/48 exact-config (100%),
36/37 rejection (97.3%) — no regressions on any previously-fixed case.

**A real bug found by adding a 4th storm at all: duplicated, drifting state.**
`landfall narrate mangkhut` crashed outright — `cli.py` had a hardcoded
`{"haiyan": 2013, "rolly": 2020, "odette": 2021}` year lookup with no entry for the new
storm. The identical hardcoded dict was independently duplicated in
`evals/e2_groundedness.py` (twice). Fixed at the root: added `year` to `StormConfig`
itself (verified against each storm's actual fetched track timestamps, including
double-checking the original three rather than assuming they were already right), and
every call site now reads `STORMS[key].year` — nothing hardcodes "three" (or "four")
anywhere anymore, so a 5th storm can't silently break the same way.

Full derivation in `docs/v1.3-phase1-result.md`.

**v1.3 Phase 2 — a real "fail loud, not plausible" violation in the physics layer
itself, not just the compiler's input schema.** Pushing `track_offset_km` toward the
compiler's own stated max (500 km) surfaced a suspicious pair of numbers: Mangkhut
shifted 500 km south returned $0.00 damage but 137,355 affected population. Traced to
the actual computation, not assumed: `wind_field()`'s centroid grid is built from each
storm's **static, registry-fixed ROI box**, sized once to the historical track and
never re-derived for a counterfactual. A large enough offset pushes the perturbed
track's core outside that box, and confirmed directly at the wind-field level for
Rolly (`track_offset_km=300, bearing=0`): `wind.intensity.max() == 0.0` across the
*entire* grid — a hard coverage cliff, not a smooth decay. A sweep across all four
storms found this varies drastically by ROI box size — **Rolly's box is smallest and
hits exactly $0 at just 150 km, only 30% of the compiler's 500 km max** (Mangkhut 300
km/60%, Haiyan and Odette 400 km/80%). A perfectly reasonable request — "shift Rolly's
track 200 km north" — is well inside the schema's valid range and returns a confident-
looking, groundedness-verifier-clean $0 that actually means "the grid never covered
where this storm went," not "this shift causes no damage."

Fixed with `ROICoverageError`: `run()` now checks immediately after computing the wind
field (before the expensive exposure/impact calc) and refuses with a clear message
instead of silently returning zeros, if wind intensity is zero everywhere in the ROI
grid. The check is deliberately narrow — it only fires on a *complete* absence of wind,
not "below some damage threshold" — so it doesn't trip on legitimate low-damage
counterfactuals with mild-but-present wind; verified against all four storms' baselines
and a modest in-bounds counterfactual (Rolly +50km@90°, $34.2M) computing normally, and
confirmed no scenario in E2's fixed variant set trips it (re-run: 336/336 = 100% final,
no exceptions). Compiler-side testing in the same round (prompt-injection-style and
degenerate input) found no bugs — every attempt was refused or partially compiled
correctly, confirming the system prompt was never the security boundary here;
`ScenarioConfig`'s pydantic validation is, and it held. Full derivation in
`docs/v1.3-phase2-result.md`.

**v1.3 Phase 3 — the scenario cache trusted a stale calibration silently.**
`CLAUDE.md`'s own engineering rule states every run is "cached to disk keyed on a
scenario-config hash" — but that hash (`ScenarioConfig.scenario_hash()`) covers only
the user-facing fields (storm, offset, bearing, intensity delta), never the calibration
approach/quantiles or ROI bounds that also determine the output, and both of those
**have** changed for real in this project's history (calibration: TDR → RMSF → EDR
across v1.1/v1.2). Confirmed directly, not just architecturally: hand-tampered a real
cached result's `total_damage_usd` to a fake `1.23` and its `calibration_approach` to
`"TDR"`, called `run()` again for the identical `ScenarioConfig` — **it returned the
tampered value unchanged**, with no way to detect the mismatch. A stale post-
recalibration cache entry would be served identically forever; this project has
recalibrated twice already, and Phase 2's guard (above) required manually clearing the
cache to test — nothing enforces that step.

Fixed with `_cache_key()`: folds the calibration constants and the storm's ROI bounds
into the cache fingerprint alongside the scenario hash, so a future calibration or ROI
change naturally produces a different key instead of silently reusing output computed
under a methodology the current code no longer uses. Verified the fix directly: a
tampered file planted at the *old-style* key (scenario hash alone — what a genuinely
stale pre-fix entry looks like) is now correctly ignored and recomputed fresh. Pinned
with a new regression test, `tests/test_engine_cache.py` (3 cases, one real engine
computation for setup). All four storms' baselines recompute to the exact values
already verified this session; E3 unaffected (48/48, 36/37); E2 unaffected (336/336 =
100% final). Full derivation in `docs/v1.3-phase3-result.md`.

## E2 — Narration groundedness

```
N briefings: 63
Raw groundedness (no verifier):    252/264 = 95.5%
Final groundedness (with verifier): 252/252 = 100.0%
```

The raw gap is not fabricated statistics — the model never invented a damage or
population figure across 63 generations. Every ungrounded number traced to the model
restating a scenario *input* (track offset/bearing/intensity delta) embedded in its own
prompt — true, but not cached impact-engine *output*, so the verifier correctly flags it
per PRD §5.2's literal rule. Full derivation, including a bug caught in the verifier
itself before this number was trusted, in `docs/phase4-result.md`.

**A second verifier bug, found by directly stress-testing its number parsing.** The
verifier is the load-bearing correctness boundary, so its extraction was probed head-on
rather than only through the LLM — and a real hole turned up: **abbreviated magnitude
figures ("$49.3M", "₱1.2B") silently bypassed it entirely.** Extraction truncated them
to 49.3 / 1.2, which then fell under the small-number (< 100) exemption, so a fabricated
"$49.3M" against a true ~$695M figure passed with *zero* flagged claims, while the
identical "$49.3 million" was correctly caught. Fixed by parsing currency-prefixed
attached abbreviations — carefully, because the naive fix (treat any "M"/"B" as a
magnitude) is *unsafe* on this corpus: a scan of all 6,255 chunks showed "20m"/"3.8m"
mean *metres* in road-damage tables (dozens of them) and "₱2,229,439.00 b" is a peso
amount followed by a list-marker "b.", both of which the naive fix would wildly
magnify. The guards (require a currency prefix; require the suffix be directly attached)
were validated against the whole corpus — only the one legitimate token "₱400M"
qualifies. A bare un-prefixed "49.3M" is left deliberately un-parsed, since "m" can't be
disambiguated from metres here. Pinned by the project's first unit-test file,
`tests/test_groundedness.py` (11 cases, no API). E2 was re-run afterward: raw 95.5%,
final still 100.0%, no regression.

**v1.3 re-run, now four storms.** `evals/e2_groundedness.py` iterates the `STORMS`
registry directly, so adding Mangkhut scaled it automatically — 84 briefings (up from
63), no code change needed beyond the year-lookup fix described in the v1.3 section
above. Result: **336/360 = 93.3% raw, 336/336 = 100.0% final** — the same ratio as the
three-storm run, holding exactly under a fourth, previously-unseen storm.

## RAG answer synthesis — groundedness is not the same as correct attribution

An LLM synthesis layer sits on top of the sitrep retrieval, reusing the same verify/
regenerate/redact pattern — but against a harder problem. There's no fixed reference pair
here; every number the model states must trace back to *some* number present in the
retrieved passages. Testing it surfaced a real, important limitation rather than a clean
win: a query about Catanduanes water-infrastructure damage retrieved a passage and
produced a fully "grounded" answer (5/5, no regeneration needed) attributing ₱293,000,000
to a specific municipality. Checking the raw extracted PDF text shows that figure sitting
among fragments of what looks like an entirely different province's damage table —
`pdftotext`/`pypdf`'s linear extraction flattens multi-column tables, scrambling
row/column structure. **The number is real and present in the source document; whether it
means what the synthesized answer claims is a different question, and nothing built so
far checks that.** Groundedness proves numeric fidelity, not semantic correctness — worth
stating plainly rather than letting a 5/5 score imply more than it does. Full write-up,
including a second finding (retrieval quality is sensitive to whether a question is
phrased as natural language vs. keywords), in `docs/phase6-result.md`.

**v1.2 follow-up — storm/date phrasing robustness, a clean result.** Directly tested
whether the interrogator confuses storm identity or dates: PH-local vs. international
storm names with no `--storm` filter (retrieval correctly resolves both, since the
sitreps self-identify with both names in their own headers), a bare-date query with no
storm name at all, and — the more adversarial cases — a `--storm` filter deliberately
mismatched against a query naming a *different* storm or year, and a compound query
spanning two storms at once. All 9 cases passed: the `storm_key` filter correctly
restricts retrieval, and the model correctly declines rather than fabricating a
cross-storm or cross-date answer, with zero ungrounded claims in the raw draft even for
the adversarial cases. One thing worth disclosing about the check itself: the first
version of this eval used too strict a pass criterion (asserting zero claims stated at
all) and wrongly flagged two of these correct, safe declines as failures — a correct
decline often restates a truthfully-grounded date while explaining the mismatch (e.g.
"they only reference events in November 2020"), which is legitimate context, not
fabrication. Caught by reading the actual failing output before trusting the eval's
verdict, and fixed to check for ungrounded claims specifically.

**Multi-storm comparison edge cases — a real bug, and a new instance of "groundedness
!= correct attribution."** Extending the same testing to genuine multi-entity
*comparison* queries (three-way rankings, mixed PH-local/international aliases across
two different storms, a registered-vs-unregistered comparison) found the same safe
decline behavior in every actually-cross-storm case — the system correctly recognizes
it can't compare across storms and says so. But a *within-storm* region comparison
surfaced a genuine, stable bug: **"Which suffered more damage, Catanduanes or Albay,
during Rolly?" answered "Catanduanes suffered more" while citing 293,000,000 for
Catanduanes against 1,271,000,000 for Albay** — the model's own cited numbers
contradicted its own stated conclusion, reproduced on 4 of 4 repeated calls. Every
individual number was grounded (present in a retrieved passage); the *comparison*
drawn between them was simply wrong — a new instance of the "groundedness ≠ correct
attribution" limitation from `docs/phase6-result.md`, extended from misattributing a
single number to mis-comparing two correctly-attributed ones. Fixed by adding an
explicit instruction to `rag_answer.py`'s system prompt: write out the specific cited
numbers for each side and numerically compare the digits before concluding, rather than
stating a conclusion first and rationalizing it afterward. Verified 5 of 5 correct
after the fix (up from 0 of 4 before it), with no regression across the other 13 cases.
Reusable regression check for all of the above: `evals/rag_storm_date_cases.py`.

**Why computation queries need no such fix — the verifier's guarantee boundary,
characterized.** A natural follow-up worry: if a wrong *comparison* slips past the
verifier, do wrong *sums, averages, and percentages* too? Testing computation-shaped
queries ("total infrastructure damage across all of Region V," "average damage per
Catanduanes municipality," "add up all the water-infrastructure figures") shows they
don't — and the reason is precisely the difference from the comparison case.
Arithmetic emits a **new number** the passages don't contain, which the mechanical
verifier catches by construction: asked to average three figures, one draft computed
₱606,941,680 (their sum) and ₱202,314,226.67 (its stated average — LLM arithmetic that
doesn't even divide cleanly, a second reason not to trust it), and the verifier flagged
both and forced a regeneration that declined; asked outright to "add up" the figures,
another draft computed ₱565,926,680 and was likewise caught. A wrong comparison, by contrast,
emits no new number — only a wrong conclusion drawn over numbers that are each already
grounded — which is exactly why it slipped through and needed a prompt fix. So the
boundary is clean and now explicit: **the verifier reliably stops fabricated *and
computed* numbers (anything it can't trace to a passage), but not wrong *reasoning*
over correctly-grounded ones.** The genuinely-summed grand total, when one exists as a
line item in the source (e.g. Region V's ₱12,867,014,693.78), is correctly retrieved
and cited rather than recomputed — grounded, not derived.

The PRD's representative queries (§3) ask things like *"which municipalities in Cebu see
the highest housing damage?"* — answerable now via a spatial join against GADM
administrative boundaries:

```
Odette — top municipalities by damage:        Haiyan — top municipalities by damage:
  Cebu City, Cebu:        $66.9M                 Tacloban City, Leyte:  $12.0M
  Lapu-Lapu City, Cebu:   $47.2M                 Santa Fe, Leyte:        $5.6M
  Mandaue City, Cebu:     $19.6M                 Ormoc City, Leyte:      $4.9M
```

Both rankings land exactly where independent knowledge of these storms says they should
— Odette's real-world damage concentrated in Metro Cebu (its track crossed directly over
Cebu Island, a widely reported surprise at the time), and Tacloban City is the single most
iconic ground-zero location in Haiyan's actual history — without either boundary dataset
(GADM) or wind model (IBTrACS/CLIMADA) having been tuned to produce that match. Full
derivation in `docs/phase5-result.md`.

## E3 — Scenario compiler accuracy

48 natural-language scenarios with ground-truth configs (exact match on all four schema
fields required), plus 37 deliberately invalid scenarios that must be refused —
over-limit offsets and intensity deltas, an unregistered storm, storm surge/rainfall
requests the wind-only schema cannot express, an unnamed storm, a 400° bearing that
must be rejected rather than silently normalized, 17 range-phrased requests spanning
all three numeric fields, 5 storm-name-error cases, and 5 tricky-refusal-phrasing
cases (rhetorical questions, compound valid+out-of-scope requests, indirect storm
references, sarcastic tone). Compiler: `gpt-4o-mini` at temperature 0, extraction-only,
with pydantic re-validating every emitted config against the same hard ranges as a
hand-written one.

| Prompt iteration | Exact-config accuracy | Rejection correctness |
|---|---|---|
| v1 | 30/40 = 75.0% | 10/10 = 100% |
| v2 (fields default to 0; ranges restated; deterministic name-alias mapping) | 39/40 = 97.5% | 10/10 = 100% |
| v3 (explicit range-rejection instruction; +6 track-offset range cases) | 40/40 = 100%* | 16/16 = 100% |
| v3, extended (+11 more range cases: intensity, bearing, compound) | 40/40 = 100%* | 27/27 = 100% |
| v4 (exact storm-name matching + category-prefix stripping; +6 valid, +9 invalid cases) | 46/46 = 100%* | 36/36 = 100% |
| v5 (4th storm added; +2 valid, +1 known-failing invalid case) | **48/48 = 100%*** | **36/37 = 97.3%** |

Every v1 miss was in the safe direction — valid requests wrongly refused, never an
invalid config accepted. The v3 range-rejection instruction was added after directly
testing range-phrased inputs and finding a real bug: **"Shift Rolly 50 to 200 km south"
was silently accepted, picking the range's high end (200) instead of refusing** — the
prompt had no explicit instruction covering ranges at all. Extending the same test to
intensity- and bearing-phrased ranges, and a compound case with two ranged fields at
once, found no further bugs.

**v4's storm-name testing found a second real bug and then a real prompt-tuning
trade-off, not a clean one-shot fix.** Testing storm-name edge cases directly found
**"Typhoon Yolande" — a one-letter misspelling of the registered alias "Yolanda" — was
silently accepted as Haiyan** (stable across 4 repeated calls). Adding an
exact-match-only instruction fixed Yolande but broke two previously-valid cases:
"Rai" and "Goni" (both registered aliases) started getting refused as unrecognized,
because the instruction's wording made the model treat *any* non-primary name as
suspect. Rewriting to explicitly reassure that all six recognized spellings — aliases
included — are equally valid fixed Rai/Goni back, but reintroduced acceptance of
"Typhoon Ray" (a one-letter difference from "Rai") as Odette. A further revision
telling the model to compare character-by-character against the six strings and
ignore real-world naming knowledge fixed Ray too, as a side effect fixing all of Yolande/
Rai/Goni/Ray simultaneously — but broke "STY Rolly" (a Philippine storm-category
abbreviation prefix), which started being refused as unrecognized. A final, narrower
addition — explicitly strip category-prefix tokens ("Typhoon," "STY," "TY," etc.)
before comparing the remaining name — fixed that without reopening any of the earlier
three. The final prompt was verified with two full consolidated passes (18 cases each,
0 mismatches) before any of it was added to the dataset.

**v5, from adding a 4th storm (v1.3): the same fuzzy-matching bug recurred, and this
time it didn't fully resolve.** "Typhoon Mangkut" (missing the "h") was silently
accepted as Mangkhut, stable across repeats. The same contrastive-example fix that
resolved Yolande and Ray was added, but this one **remained wrong 4/4 calls after the
fix** — harder and more stable than the flaky Rai case. Given the oscillation already
seen twice in this section (each fix trading one broken case for another), further
tuning against this single case wasn't attempted. Disclosed as a known-failing case in
the dataset (id 85) rather than excluded to keep the accuracy number clean — hence
36/37, not 37/37, on this row.

*\*Neither the v3, v4, nor v5 100% exact-config figures are stable guarantees. The v2 residual miss
("Typhoon Rai shifted 150 km northeast") is genuinely non-deterministic at
temperature=0: direct isolated testing found 3 of 4 repeated calls compiled it
correctly, 1 of 4 refused it as an unrecognized storm. Every full-suite eval run
reported here scored 100%/100%, but that specific case (and possibly others at the
same margin) can still fail on a given run — reported honestly rather than presented
as a stable guarantee.*

## Repo layout

- `src/landfall/hazard/`, `exposure/`, `impact/` — the deterministic core
- `src/landfall/scenario.py` — counterfactual config, validation, track perturbation
- `src/landfall/llm/` — scenario compiler, narrator, RAG interrogator
- `src/landfall/verify/` — groundedness verifier
- `src/landfall/cli.py` — `landfall` console-script entry point
- `evals/` — E2 groundedness eval; E3 compiler-accuracy eval + its 85-case dataset;
  RAG storm/date phrasing robustness check
- `tests/` — unit tests for the groundedness verifier (deterministic, no API) and the
  scenario cache key (one real engine computation for setup, no API)
- `docs/` — phase-by-phase build log and honest results, including every bug caught
