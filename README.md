> ⚠️ **Landfall is a research and preparedness demonstration. It is NOT an operational
> forecasting tool and must not be used for emergency decision-making.** Damage estimates
> from tropical cyclone models of this class are routinely off by 2–5×; documenting that
> error honestly is the point of this project.

# Landfall

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

Phases 1–4 of the PRD (`landfall-prd.md`) are done. What's built and what isn't, honestly:

**Built:** IBTrACS track ingestion for all three storms; Holland (1980) wind fields;
LitPop exposure; WP2-calibrated impact functions (Eberenz et al. 2021); a validated,
hard-range-checked counterfactual scenario schema (track offset/bearing, intensity delta)
with a scenario-hash disk cache; an LLM narrator with a groundedness verifier that
regenerates or redacts any numeric claim it can't trace to cached impact output; a local
RAG interrogator (bge-m3 embeddings, no API calls) over NDRRMC sitreps with source
citations.

**Not built / deferred:**
- **The NL → scenario-config compiler (and its E3 eval)** — PRD §6 requires E3's 40
  ground-truth configs be hand-labeled by the project's author, not the agent building the
  compiler being evaluated against them. Counterfactuals currently run from
  directly-specified configs (`ScenarioConfig(...)`), not natural language.
- **Tagalog narration** — English only so far; same verifier applies once added.
- **RAG answer synthesis** — the interrogator returns cited passages, not a synthesized
  narrative answer.
- **Stack deviation:** PRD §5.2 specifies an Anthropic Haiku-class model for the narrator;
  no Anthropic key was available in the build environment, so the narrator uses OpenAI's
  `gpt-4o-mini` instead, per the author's direction. Functionally equivalent for this
  project's purposes.

See `docs/phase1-plan.md` through `docs/phase4b-result.md` for the session-by-session build
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

## E3 — Scenario compiler accuracy

Not run. Requires 40 hand-written scenarios with hand-labeled ground-truth configs,
labeled by the project's author (PRD §6) — an agent-authored eval of an agent-built
compiler would be circular.

## Repo layout

- `src/landfall/hazard/`, `exposure/`, `impact/` — the deterministic core
- `src/landfall/scenario.py` — counterfactual config, validation, track perturbation
- `src/landfall/llm/` — narrator, RAG interrogator
- `src/landfall/verify/` — groundedness verifier
- `evals/` — E2 groundedness eval
- `docs/` — phase-by-phase build log and honest results, including every bug caught

Part of the Verified AI portfolio (Mulat · Receipts · **Landfall**).
