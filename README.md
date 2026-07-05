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

See `docs/phase1-plan.md` through `docs/phase8-result.md` for the session-by-session build
log, including three real bugs caught before they reached a shipped number (a wrong
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

## E1 — Historical validation

**v1.1, Phase 1 (vulnerability curve recalibration)** replaced the WP2 (Philippines)
impact function's `TDR` calibration with `RMSF` — both are published calibrations of the
same Eberenz et al. 2021 curve (NHESS 21:393–415,
https://doi.org/10.5194/nhess-21-393-2021), not an invented parameter. TDR fits an
anomalously flat curve for WP2 by the paper's own admission (*"TDR gives larger weight to
events with large damage values... these results indicate that these events are
systematically overestimated by the model in the regions WP2–4"*); RMSF weights every
matched historical event equally instead. Curve shapes compared in
`docs/impact_curves_tdr_vs_rmsf.png`. Full derivation, including the honest Odette
finding below, in `docs/v1.1-phase1-result.md`.

**v1.1, Phase 2 (hazard-layer investigation)** tested whether Rolly's remaining 29.6×
gap was hazard-side: compared IBTrACS' USA/JTWC vs Tokyo/JMA agency tracks directly
(converting Tokyo's 10-min winds to 1-min-sustained via the same Knapp & Kruk 2010
factor CLIMADA applies internally), checked the simulated peak wind over Catanduanes
against the storm's observed landfall intensity, and ran three sensitivity tests
(alternate agency, RMW, grid resolution). One finding worth flagging on its own: the
task's "~62 m/s 1-min sustained" reference figure turned out to be JMA's raw 10-minute
value mislabeled — properly rescaled, the correct 1-min-sustained comparison range is
81.9–87.5 m/s, against which the current pipeline's simulated peak (73.8 m/s) is a real
but modest ~10–16% shortfall, nowhere near enough to explain a 29.6× damage error on its
own. All three sensitivity levers tested (agency, RMW, grid resolution) left the peak
essentially unchanged or slightly worse — a clean negative result, not reworked until
something moved. **No configuration change is adopted**; E1's Phase 2 column is
unchanged from Phase 1 for exactly that reason. Full derivation, including an
unexplained anomaly (Bato, Rolly's actual landfall municipality, shows a much lower
simulated wind than its neighbors) flagged for future investigation, in
`docs/v1.1-phase2-result.md`.

**v1.1, Phase 3 (exposure upgrade)** replaced LitPop with real OSM building footprints
+ PSA 2020 census population for the three Rolly-affected provinces (Catanduanes,
Albay, Camarines Sur) — LitPop's nightlights weighting structurally undervalues rural,
low-luminosity areas exactly like these. Each building's value comes from its footprint
area × a construction-cost rate (₱9,949/m², a commercial QS-guide national average —
PSA's own regional building-permit cost statistics are blocked from this environment,
so this is a disclosed lower-authority substitute) converted at the World Bank's 2020
average exchange rate (₱49.624/USD). Population comes from PSA's actual 2020 census,
barangay by barangay (80.0% exact name-match to GADM boundaries; the rest filled by an
area-proportional split that conserves each municipality's true PSA total exactly — two
real name-join bugs, PSA's parenthetical alt-names and City-name word-order
differences, were caught and fixed here rather than left as silent undercounts).
**Sanity check, reported as found**: Catanduanes' total exposed value jumped 27.79×
over LitPop's figure ($27.9M → $774.7M) — checked against per-capita plausibility
(LitPop implied $103/person, implausibly low; the new figure implies ~$2,850/person,
plausible against ~$3,300 Philippine per-capita GDP) rather than assumed correct.
**Important caveat**: OSM building-mapping completeness is wildly uneven across the
three provinces — 102% of PSA's housing-unit count in Catanduanes, but only 57.8% in
Albay and just 19.2% in Camarines Sur — so this phase's result likely still
*undercounts* true exposure in two of three provinces. Full derivation in
`docs/v1.1-phase3-result.md`.

| Storm | Baseline (TDR) | Fix 1: RMSF calibration | Fix 2: hazard-layer (Phase 2) | Fix 3: hybrid exposure (Phase 3) | NDRRMC actual |
|---|---|---|---|---|---|
| Haiyan (2013) | $49.3M (18.6× under) | $775.6M (1.18× under) | no change | $775.6M (unchanged) | ~$917M |
| Rolly (2020) | $0.40M (575× under) | $7.86M (29.6× under) | no change | **$91.6M (2.54× under)** | ~$233M |
| Odette (2021) — **held out** | $184.1M (2.5–5.0× under) | $3,532.1M (3.9–7.7× over) | no change | $3,532.1M (unchanged) | $459M–$915M |

No target error factor — this table exists to be honest, not to hit a number (PRD §6).
Fit on Haiyan + Rolly only; Odette was never previewed or used to choose RMSF over
TDR/EDR. **The RMSF fix flips Odette from underestimation to overestimation** — this is
reported as the headline result of this phase, not minimized as "2 of 3 improved." A
curve that overestimates the one storm it wasn't tuned against by a margin comparable to
what it fixed elsewhere has not been shown to generalize; see
`docs/v1.1-phase1-result.md` for two candidate explanations (concentrated-vs-spread-out
storm damage profiles; a possible second, independent error in Rolly's hazard/exposure
layers that RMSF doesn't touch), neither investigated further in this phase by design.

v1's original error-analysis narrative (before this recalibration) is preserved in
`docs/phase2-result.md`.

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
