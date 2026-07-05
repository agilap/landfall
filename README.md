> ⚠️ **Landfall is a research and preparedness demonstration. It is NOT an operational
> forecasting tool and must not be used for emergency decision-making.** Damage estimates
> from tropical cyclone models of this class are routinely off by 2–5×; documenting that
> error honestly is the point of this project.

# Landfall

[![GitHub](https://img.shields.io/badge/GitHub-agilap%2Flandfall-blue?logo=github)](https://github.com/agilap/landfall)

**Counterfactual typhoon damage simulation for the Philippines.**

A deterministic hazard–exposure–vulnerability engine (CLIMADA) computes all damage
figures for three historical Philippine typhoons — Haiyan (2013), Rolly (2020), and
Odette (2021) — and for counterfactual scenarios (track offset, bearing, intensity delta).
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

Phases 1–8 of the PRD (`landfall-prd.md`) are done. What's built and what isn't, honestly:

**Built:** IBTrACS track ingestion for all three storms; Holland (1980) wind fields;
LitPop exposure nationally, with a hybrid OSM-buildings + PSA-census layer for
Catanduanes/Albay/Camarines Sur (v1.1 Phase 3 — see E1 below); WP2-calibrated impact
functions (Eberenz et al. 2021, RMSF calibration as of v1.1 Phase 1 — see E1 below); per-municipality
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
50-case eval set was instead authored by the same coding agent that built the compiler.
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

See `docs/phase1-plan.md` through `docs/phase8-result.md` (v1) and `docs/v1.1-phase1-result.md`
through `docs/v1.1-phase4-result.md` (v1.1's underestimation fix) for the session-by-session
build log, including three real bugs caught before they reached a shipped number (a wrong
IBTrACS storm ID, a stale post-redaction groundedness report, and a wasted GPU-torch
install), each described alongside how it was caught.

## Usage

```
pip install -e .
landfall run haiyan                                   # historical replay
landfall run rolly --offset-km 100 --bearing 0         # counterfactual: 100 km north
landfall narrate odette --intensity-delta 20           # + verified narration
landfall compile "Shift Rolly 50 km south"              # NL -> ScenarioConfig
landfall ask "What happened in Catanduanes?" --storm rolly   # sitrep RAG interrogator
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

**Odette's verdict — the credibility check for the whole exercise.** Odette was the
only storm that started in-range (2.5–5.0× under). It now sits at **3.9–7.7× over** — a
full reversal, not a drift, and it happened entirely in Phase 1; Phases 2 and 3 never
touched it (zero ROI overlap). This is the honest risk this table can't paper over:
**the single fix that did the most good is the same fix that broke the one storm that
was previously fine.** A single national WP2 curve, fit on aggregate historical damage,
cannot obviously fit both a narrow, concentrated storm (Rolly) and a broad one (Odette
— Phase 5's municipality analysis showed damage spread across Metro Cebu at a scale
Haiyan's narrower track didn't) at the same time. This table should not be read as "the
model is now well-calibrated" — it's better calibrated for two of three storms, at the
cost of the third, and that trade stays visible here rather than getting rounded off
into "2 of 3 improved."

### What's still unexplained

- **Why Odette flipped, specifically** — concentrated-vs-spread damage profile is a
  hypothesis, not a confirmed cause.
- **Rolly's residual 2.54× under** — real, but exposure Phase 3 was reached through an
  incomplete OSM dataset in two of three provinces, so this number itself carries
  uncertainty in an unclear direction.
- **The flood/rain share of Rolly's damage** — genuinely unanswerable from this corpus,
  not just undone.
- **The $233M vs ≈$318.6M Rolly reference-figure discrepancy** surfaced in Phase 4 —
  unreconciled.
- **Bato's anomalously low simulated wind** (Phase 2) relative to its neighbors, despite
  being Rolly's reported landfall municipality — unexplained, not investigated further.

## E2 — Narration groundedness

```
N briefings: 63
Raw groundedness (no verifier):    188/220 = 85.5%
Final groundedness (with verifier): 189/189 = 100.0%
```

The 14.5% raw gap is not fabricated statistics — the model never invented a damage or
population figure across 63 generations. Every ungrounded number traced to the model
restating a scenario *input* (track offset/bearing/intensity delta) embedded in its own
prompt — true, but not cached impact-engine *output*, so the verifier correctly flags it
per PRD §5.2's literal rule. Full derivation, including a bug caught in the verifier
itself before this number was trusted, in `docs/phase4-result.md`.

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

## Per-municipality breakdown

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

40 natural-language scenarios with ground-truth configs (exact match on all four schema
fields required), plus 10 deliberately invalid scenarios that must be refused — over-limit
offsets and intensity deltas, an unregistered storm, storm surge/rainfall requests the
wind-only schema cannot express, an unnamed storm, and a 400° bearing that must be
rejected rather than silently normalized. Compiler: `gpt-4o-mini` at temperature 0,
extraction-only, with pydantic re-validating every emitted config against the same hard
ranges as a hand-written one.

| Prompt iteration | Exact-config accuracy | Rejection correctness |
|---|---|---|
| v1 | 30/40 = 75.0% | 10/10 = 100% |
| v2 (fields default to 0; ranges restated; deterministic name-alias mapping) | **39/40 = 97.5%** | **10/10 = 100%** |

Every v1 miss was in the safe direction — valid requests wrongly refused, never an
invalid config accepted. The v2 residual miss is the same shape: "Typhoon Rai shifted
150 km northeast" is refused as an unknown storm (Rai is Odette's international name)
instead of compiled. Iteration stopped there deliberately: further prompt tuning against
these fixed 50 cases would be overfitting the exam.

## Repo layout

- `src/landfall/hazard/`, `exposure/`, `impact/` — the deterministic core
- `src/landfall/scenario.py` — counterfactual config, validation, track perturbation
- `src/landfall/llm/` — scenario compiler, narrator, RAG interrogator
- `src/landfall/verify/` — groundedness verifier
- `src/landfall/cli.py` — `landfall` console-script entry point
- `evals/` — E2 groundedness eval; E3 compiler-accuracy eval + its 50-case dataset
- `docs/` — phase-by-phase build log and honest results, including every bug caught
