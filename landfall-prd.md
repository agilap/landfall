# PRD: Landfall

**Counterfactual typhoon damage simulation for the Philippines**

| | |
|---|---|
| Author | Alexander Penuliar (agilap) |
| Status | Draft v1.0 |
| Date | July 2026 |
| Project type | Solo build, ~4 weeks of evening sessions |
| Mission context | Third artifact of the Verified AI portfolio (Mulat, Receipts, Landfall) |

---

## 1. Problem statement

The Philippines experiences roughly 20 tropical cyclones per year, yet the tools for understanding typhoon impact are inaccessible to nearly everyone outside specialist agencies. PAGASA bulletins report hazard (wind signals, rainfall warnings) but not localized consequence. NDRRMC situation reports document damage only after the fact. There is no accessible way for a student, LGU staffer, researcher, or journalist to ask: "What would Haiyan have done if it had tracked 100 km north?" or "Which municipalities in Batangas lose the most housing under a category 5 landfall at Infanta?"

Meanwhile, LLMs are increasingly used to answer disaster-related questions, and they confidently invent numbers. A hallucinated storm surge height or casualty estimate in a disaster context is the most dangerous form of the grounding failure this portfolio exists to address.

Landfall demonstrates the alternative: a deterministic hazard–exposure–vulnerability engine computes all damage figures; an LLM layer only translates questions into scenarios and narrates results, with every numeric claim mechanically verified against model output before it reaches the user.

## 2. Goals and non-goals

### Goals

1. Replay three historical Philippine typhoons (Haiyan 2013, Rolly 2020, Odette 2021) through a wind-hazard damage model and validate simulated damage against recorded NDRRMC figures, reporting the error factor honestly.
2. Support counterfactual scenarios (track shift, intensity change, alternate landfall point) specified in natural language and compiled to validated simulation configs by an LLM.
3. Generate per-locality plain-language impact briefings (English and Tagalog) in which 100% of numeric claims are traceable to impact-engine output, enforced by an automated verifier.
4. Publish two evaluation tables (validation error, narration groundedness) and an honest write-up of model limitations.

### Non-goals (v1)

- Flood, storm surge, or rainfall modeling. Wind hazard only.
- Real-time or operational forecasting of any kind.
- Nationwide coverage. Regions of interest are limited to areas affected by the three replay storms.
- Custom fragility-curve research. Published/calibrated impact functions only.
- Web deployment. v1 is a local tool with notebook-grade outputs and a CLI/simple interface; deployment is a post-validation decision.
- Casualty modeling. Damage and affected-population estimates only. Mortality estimation carries ethical weight beyond a portfolio project's scope.

## 3. Users and use cases

**Primary user (v1): the builder.** Landfall is first a demonstration of verified-AI architecture applied to a physically grounded domain, evaluated against historical ground truth.

**Secondary audiences:** recruiters and engineers assessing the portfolio; the PH civic-tech and disaster-research community (DOST, Project NOAH lineage, UP Resilience Institute circles) as potential readers of the write-up; students and journalists as hypothetical downstream users of a matured version.

**Representative queries:**

- "Replay Odette. Which municipalities in Cebu see the highest housing damage?"
- "Shift Haiyan's track 100 km north. Compare affected population against the historical run."
- "Category 5 landfall at Infanta, Quezon. Brief me on Metro Manila exposure in Tagalog."
- "What did the sitreps actually record for Rolly in Catanduanes, and how far off is the model?"

## 4. Product principles

1. **Physics computes, LLM narrates.** No load-bearing number originates in a language model. This is the project's reason to exist.
2. **Fail loud, not plausible.** The scenario compiler rejects physically invalid inputs rather than guessing. The narrator refuses to emit a number it cannot trace.
3. **Honest error is the product.** Tropical cyclone damage models are routinely off by 2–5×. Documenting Landfall's error factor and its causes is a deliverable, not an embarrassment.
4. **Not an operational tool.** A visible disclaimer from line one of the README: research and preparedness demonstration, not for emergency decision-making.

## 5. System architecture

### 5.1 Deterministic core

**Hazard layer.** CLIMADA `TropCyclone` module. Input: IBTrACS best-track records for the three storms; counterfactuals apply parametric perturbations (track translation, intensity delta, landfall relocation) to the track before wind-field synthesis. Output: max sustained wind grids at 150 arcsec (~4.5 km) resolution over regions of interest. Holland (1980) parametric wind model as implemented by CLIMADA; no custom meteorology.

**Exposure layer.** CLIMADA `LitPop` (population × nightlights proxy) as the v1 baseline. Upgrade path to OSM building footprints + PSA barangay census, triggered only if validation error analysis implicates exposure quality.

**Vulnerability layer.** CLIMADA's calibrated tropical-cyclone impact functions (Emanuel-type sigmoid), using regional calibration for the Western Pacific/Philippines from published literature. Cited, not derived.

**Impact engine.** Hazard × exposure × vulnerability → per-municipality damage estimates and affected-population counts. Fully deterministic; every scenario run is cached to disk keyed on a scenario-config hash, making all downstream narration reproducible and verifiable.

### 5.2 LLM layer

**Scenario compiler.** Natural-language scenario → JSON config conforming to a strict schema (storm ID, track offset km/bearing, intensity delta, landfall coordinates, region of interest). Hard validation rejects out-of-range or physically incoherent parameters with a human-readable refusal. Cheap API model (Haiku-class); structured output mode.

**Narrator.** Impact-engine output (tables, per-municipality figures) → plain-language briefing in English or Tagalog. Post-generation verifier extracts every numeric token from the draft and matches it against the cached impact output (exact or within declared rounding); any unmatched number causes regeneration or redaction. This is the Receipts verification pattern reapplied.

**Interrogator (RAG).** Corpus of NDRRMC situation reports and PAGASA bulletins for the three storms (public PDFs), chunked and embedded locally. Supports "what actually happened" queries and powers the sim-vs-reality comparison view. Retrieval must attach source-document citations.

### 5.3 Stack

Python throughout. CLIMADA + NumPy/xarray/GeoPandas for the core; matplotlib/folium for maps. SQLite for scenario cache metadata. Local models on RTX 3050 4GB: bge-m3 embeddings for RAG. API models: Haiku-class for compilation and narration drafts. Orchestration: plain Python with a thin CLI; no framework until one is needed. Development in Claude Code with `CLAUDE.md` carrying this PRD's boundaries.

### 5.4 Hardware and cost envelope

CLIMADA at regional 150-arcsec resolution runs comfortably in 14 GB RAM on CPU. All datasets (IBTrACS, LitPop inputs, OSM, sitreps) are free. Projected total LLM spend for the build: $5–10. No GPU training. No hosting costs in v1.

## 6. Evaluation plan

Evaluation is the primary deliverable. Three tables:

**E1 — Historical validation.** Simulated vs NDRRMC-recorded damage (PHP) and affected population, per storm and per region. Metric: error factor (ratio), with a written analysis attributing error across hazard, exposure, and vulnerability layers. Acceptance: the table exists and is honest; there is no target error factor, because pretending to one would be the exact failure this portfolio argues against.

**E2 — Narration groundedness.** N ≥ 50 generated briefings. Metric: percentage of numeric claims traceable to cached impact output. Reported both without the verifier (baseline hallucination rate of raw narration) and with it (target ~100%). The delta between the two rows is the thesis in one number.

**E3 — Scenario compiler accuracy.** 40 hand-written natural-language scenarios with hand-labeled correct configs (labeled by the author; ground truth is not delegable). Metrics: exact-config accuracy, plus rejection correctness on 10 deliberately invalid scenarios.

## 7. Milestones

**Phase 0 (pre-work, owed):** Close out Receipts fully — demo video recorded and linked, one distribution post published. Landfall does not begin until Receipts is at 100%.

**Phase 1 — First number.** CLIMADA installed and running; IBTrACS Haiyan track ingested; wind field rendered over the Visayas; first uncalibrated damage figure produced. Definition of done: one damage number for one storm, however wrong.

**Phase 2 — Validation (load-bearing phase).** All three replays running; exposure sanity checks; sitrep damage figures extracted; E1 table drafted with first error analysis.

**Phase 3 — Counterfactuals.** Scenario compiler with schema validation; E3 eval set written and run; counterfactual runs working end to end ("Haiyan, 100 km north") with comparison output against the historical baseline.

**Phase 4 — Narration and ship.** Narrator + groundedness verifier; E2 run; sitrep RAG with citations; README with all three eval tables, limitation discussion, hazard maps as hero images; write-up published: *"I simulated three typhoons and checked my model against what actually happened. It was off by X — here's why that's the point."*

Slippage policy: Mulat and job-search activities take precedence. Landfall tolerates stretching to six weeks; it does not tolerate stopping at 95%.

## 8. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Validation error is embarrassing (>5×) | Medium | It is the finding. Attribute error across layers; upgrade exposure (OSM/PSA) only if implicated. Frame in write-up. |
| Wind-only hazard misses flood-dominated damage (Odette especially) | High | State it prominently. Report wind-attributable share where sitreps allow; scope surge to roadmap. |
| CLIMADA learning curve consumes Phase 1 | Medium | Phase 1 DoD is deliberately minimal (one number). Use CLIMADA tutorials verbatim before customizing. |
| Scenario compiler accepts nonsense | Medium | Schema + range validation is deterministic; the eval includes invalid-input rejection cases. |
| Narrator verifier false-positives on rounded/aggregated numbers | Medium | Declare rounding rules; verifier matches within declared tolerance; log all redactions for review. |
| Scope creep toward surge/flood modeling | High (known pattern) | Non-goals section is binding. `CLAUDE.md` carries the boundary. Roadmap absorbs ambition. |
| Misuse perception (looks operational) | Low | Disclaimer from line one; no real-time data paths exist in the codebase by design. |

## 9. Ethical boundaries

Landfall is a research and preparedness demonstration. It must not present itself as, or be usable as, an operational forecasting or emergency-response tool. No casualty estimates. No real-time track ingestion. Counterfactuals are clearly labeled as hypothetical in all outputs. The narrator's Tagalog output receives the same groundedness verification as English — accessibility does not lower the evidence bar.

## 10. Definition of shipped

Public repo; three eval tables with real numbers; limitation write-up; hazard-map hero images; demo video; one distribution post (PH civic-tech / dev community); resume bullet drafted from measured results only. Deployment is explicitly not part of shipped.

## 11. Roadmap (post-v1, do not build now)

Storm surge via published hazard maps (Project NOAH rasters); OSM/PSA exposure upgrade; additional storms; interactive map UI; evacuation-behavior agent layer (Multo pattern); multilingual briefings beyond Tagalog.

---

*Every quantitative claim in this document describes targets or public facts about datasets and tools; all measured results will be committed alongside the evaluation code that produced them.*
