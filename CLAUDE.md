# Landfall — Claude Code instructions

Counterfactual typhoon damage simulation for the Philippines. Full spec: `landfall-prd.md`.
This file carries the PRD's **binding boundaries** — they override any in-session ambition.

## Core principle

**Physics computes, LLM narrates.** No load-bearing number may originate in a language
model. CLIMADA's impact engine produces all damage/affected-population figures; the LLM
layer only (a) compiles natural-language scenarios into validated JSON configs and
(b) narrates cached engine output, with every numeric claim mechanically verified.

## Hard non-goals (v1) — do not build, do not suggest building

- No flood, storm surge, or rainfall modeling. **Wind hazard only.**
- No real-time or operational forecasting; no real-time data ingestion paths.
- No casualty/mortality estimation. Damage and affected-population only.
- No custom fragility curves — published/calibrated impact functions only.
- No web deployment in v1. Local CLI + notebook-grade outputs.
- No nationwide coverage — only regions affected by Haiyan (2013), Rolly (2020), Odette (2021).

Scope creep toward surge/flood is a known failure pattern. If a task drifts there, stop
and point at this section. Roadmap items live in PRD §11 and are post-v1.

## Engineering rules

- Deterministic core: every scenario run is cached to disk keyed on a scenario-config hash.
  Narration must only reference cached impact output.
- Scenario compiler: strict JSON schema + deterministic range validation. Reject invalid
  physics with a human-readable refusal — never guess or clamp silently.
- Narrator verifier: extract every numeric token from drafts, match against cached output
  within declared rounding tolerance; unmatched numbers → regenerate or redact, log it.
- Fail loud, not plausible. Honest error is the product — validation error factors are
  reported, not hidden.
- Stack: Python, CLIMADA + NumPy/xarray/GeoPandas, matplotlib/folium, SQLite for cache
  metadata, bge-m3 local embeddings for RAG, Haiku-class API models. Plain Python + thin
  CLI; no orchestration framework until one is demonstrably needed.

## Ethics

Research/preparedness demonstration only — disclaimer stays at line one of the README.
Counterfactuals are labeled hypothetical in all outputs. Tagalog output gets the same
groundedness verification as English.

## Landfall Viz (companion project, see landfall-viz-prd.md)

The "no web deployment in v1" non-goal above applies to *Landfall itself* (the CLI/
engine/narrator/RAG). It does not block the separate, explicitly-scoped visualization
companion described in `landfall-viz-prd.md` — that PRD's own §2 draws this boundary
deliberately, not as scope creep. Working rules for that project specifically:

- One phase at a time — do not start a phase before the prior one's exit criterion is
  met and confirmed.
- Design before code — for each phase, present the design and wait for explicit go-ahead
  before implementing.
- No new numbers — the viz renders committed scenario caches only; it never computes.
  If a view needs data the engine doesn't emit, the engine changes first (in this repo,
  with its own correctness check), then the viz consumes it.
- Every rendered value must trace to a committed cache and a config hash — provenance
  visible in the UI, not just assumed.

## Layout

- `src/landfall/hazard/` — IBTrACS ingestion, track perturbation, CLIMADA TropCyclone wind fields
- `src/landfall/exposure/` — LitPop exposure (OSM/PSA upgrade only if validation implicates it)
- `src/landfall/impact/` — impact engine runs, scenario-hash cache
- `src/landfall/llm/` — scenario compiler, narrator, sitrep RAG interrogator
- `src/landfall/verify/` — numeric groundedness verifier
- `evals/` — E1 (validation), E2 (groundedness), E3 (compiler accuracy) tables + code
- `data/` — tracks, sitrep PDFs, scenario cache (gitignored where large)
- `docs/` — plans, error-analysis write-ups
