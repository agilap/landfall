> ⚠️ **Landfall is a research and preparedness demonstration. It is NOT an operational
> forecasting tool and must not be used for emergency decision-making.** Damage estimates
> from tropical cyclone models of this class are routinely off by 2–5×; documenting that
> error honestly is the point of this project.

# Landfall

**Counterfactual typhoon damage simulation for the Philippines.**

A deterministic hazard–exposure–vulnerability engine (CLIMADA) computes all damage
figures for three historical Philippine typhoons — Haiyan (2013), Rolly (2020), and
Odette (2021) — and for natural-language counterfactuals ("shift Haiyan's track 100 km
north"). An LLM layer only compiles scenarios into validated configs and narrates
results; **every numeric claim in generated briefings is mechanically verified against
the impact engine's cached output before it reaches the user.**

Physics computes. The LLM narrates. No load-bearing number originates in a language model.

## Status

Pre-Week-1. See `landfall-prd.md` for the full spec and `docs/week1-plan.md` for the
current milestone.

## Planned deliverables

- **E1 — Historical validation:** simulated vs NDRRMC-recorded damage per storm/region,
  with an honest error-factor analysis.
- **E2 — Narration groundedness:** hallucination rate of raw narration vs verified
  narration across ≥50 briefings (English and Tagalog).
- **E3 — Scenario compiler accuracy:** exact-config accuracy on 40 labeled scenarios plus
  rejection correctness on 10 invalid ones.

Part of the Verified AI portfolio (Mulat · Receipts · **Landfall**).
