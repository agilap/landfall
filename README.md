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

Phases 1–6 of the PRD (`landfall-prd.md`) are done. What's built and what isn't, honestly:

**Built:** IBTrACS track ingestion for all three storms; Holland (1980) wind fields;
LitPop exposure; WP2-calibrated impact functions (Eberenz et al. 2021); per-municipality
damage and affected-population breakdown (GADM administrative boundaries, spatially
joined against impact-engine output — Odette's top municipality is Cebu City, Haiyan's is
Tacloban City, both matching real-world reporting); a validated, hard-range-checked
counterfactual scenario schema (track offset/bearing, intensity delta) with a
scenario-hash disk cache; an LLM narrator with a groundedness verifier that regenerates or
redacts any numeric claim it can't trace to cached impact output; a local RAG interrogator
(bge-m3 embeddings, no API calls) over NDRRMC sitreps with source citations; an answer-
synthesis layer on top of that retrieval, with its own groundedness check — **and a real
limitation that check surfaced**, see below.

Also built: the **NL → scenario-config compiler** (`src/landfall/llm/compiler.py`) and
its E3 eval — with a disclosed caveat. PRD §6 says E3's ground-truth configs are
hand-labeled by the author and not delegable; at the author's explicit direction, the
50-case eval set was instead authored by the same coding agent that built the compiler.
That is a circularity risk (an agent writing both sides of its own exam), so it is
stated here rather than hidden, and the eval set is plain JSON
(`evals/e3_dataset.json`) open to author audit.

**Not built / deferred:**
- **Tagalog narration** — English only so far; same verifier applies once added.
- **Query rewriting and table-aware PDF extraction** for the RAG layer — see the
  groundedness-vs-attribution finding below.
- **Stack deviation:** PRD §5.2 specifies an Anthropic Haiku-class model for the narrator;
  no Anthropic key was available in the build environment, so the narrator uses OpenAI's
  `gpt-4o-mini` instead, per the author's direction. Functionally equivalent for this
  project's purposes.

See `docs/phase1-plan.md` through `docs/phase6-result.md` for the session-by-session build
log, including three real bugs caught before they reached a shipped number (a wrong
IBTrACS storm ID, a stale post-redaction groundedness report, and a wasted GPU-torch
install), each described alongside how it was caught.

## E1 — Historical validation

| Storm | Simulated damage (USD) | NDRRMC-recorded damage (USD, approx.) | Error factor |
|---|---|---|---|
| Haiyan (2013) | $49.3M | ~$917M | **18.6× under** |
| Rolly (2020) | $0.40M | ~$233M | **575× under** |
| Odette (2021) | $184.1M | $459M–$915M | **2.5–5.0× under** |

No target error factor — this table exists to be honest, not to hit a number (PRD §6).
Odette lands inside the PRD's own stated expectation for typical TC-model error (2–5×);
Haiyan and Rolly do not, and that gap is understood, not hand-waved: the WP2 calibrated
damage curve is close to zero below ~30 m/s wind speed and still only ~3.6% at 80 m/s.
Rolly's compact wind field (Goni's real-world reputation) left most of its exposed value
below that curve's effective start, while Odette's broader wind field pushed far more
value into the curve's higher-damage range. Full derivation in `docs/phase2-result.md`.

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

**Caveat, restated:** PRD §6 requires this eval set be hand-labeled by the author; it was
instead authored by the coding agent at the author's direction (see Status above).

## Repo layout

- `src/landfall/hazard/`, `exposure/`, `impact/` — the deterministic core
- `src/landfall/scenario.py` — counterfactual config, validation, track perturbation
- `src/landfall/llm/` — scenario compiler, narrator, RAG interrogator
- `src/landfall/verify/` — groundedness verifier
- `evals/` — E2 groundedness eval; E3 compiler-accuracy eval + its 50-case dataset
- `docs/` — phase-by-phase build log and honest results, including every bug caught

Part of the Verified AI portfolio (Mulat · Receipts · **Landfall**).
