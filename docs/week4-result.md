# Week 4 result — narrator, groundedness verifier, E2

## Stack deviation: OpenAI instead of Anthropic

PRD §5.2/§5.3 specify a Haiku-class Anthropic model for the scenario compiler and
narrator. No `ANTHROPIC_API_KEY` was available in this environment; the user directed a
switch to OpenAI's `gpt-4o-mini` instead (a comparable cheap/fast model), provided via a
`.env` file (gitignored) loaded with `python-dotenv`. `landfall/llm/narrator.py` documents
this. Functionally equivalent for this project's purposes — the verification pattern
doesn't care which vendor drafted the text.

## What was built

- **`landfall/llm/narrator.py`** — takes a scenario description plus exactly the two
  cached figures (total damage, affected population) and asks the model for a short
  briefing, explicitly instructed to state no other numbers.
- **`landfall/verify/groundedness.py`** — extracts every numeric token (handling
  "49.3 million"-style magnitude words) from a draft and checks each against a set of
  reference values within 1% relative tolerance. `redact_ungrounded()` replaces any
  ungrounded number with `[REDACTED]`.
- **`landfall/verify/verified_narrator.py`** — orchestrates: draft, check, regenerate up
  to twice if ungrounded numbers remain, then redact anything still unresolved. Logs
  every redaction.
- **`evals/e2_groundedness.py`** — generates 63 briefings (21 distinct scenarios × 3
  storms × 3 generations each: historical baseline + 6 counterfactual variants per storm)
  and reports aggregate groundedness with and without the verifier.

## A real bug, caught before it corrupted the eval

`redact_ungrounded()` originally returned the **pre-redaction** groundedness report
alongside the post-redaction text — so the "final" groundedness statistic was stale. First
full E2 run reported final groundedness at 92.2%, which should be structurally impossible
(redaction removes every ungrounded number, so post-redaction text should always check out
at 100%). That impossibility was the tell. Fixed by re-running `check()` on the redacted
text rather than reusing the original report; a small synthetic test (`check` a string
with a fabricated casualty figure, then verify `redact_ungrounded` reports 100% after)
confirmed the fix before re-running the full eval.

## E2 result

```
N briefings: 63
Raw groundedness (no verifier):    188/220 = 85.5%
Final groundedness (with verifier): 189/189 = 100.0%
```

(Total claims differ between the two rows because redaction removes ungrounded tokens
from the text entirely — the 189 remaining claims in the final row are exactly the ones
that were always grounded.)

**What's actually causing the 14.5% raw gap:** not fabricated statistics — the model never
invented a damage or population figure. Every ungrounded number traced back to the model
restating a *scenario input* embedded in its own prompt: the counterfactual's track offset
(km), bearing (degrees), or intensity delta (kn) — e.g. "...based on a 100 km northward
shift..." The offset/bearing/intensity values are true, and came from the same prompt as
the two permitted figures, but they are not cached impact-engine *output*, so the verifier
correctly treats them as ungrounded per PRD §5.2's literal rule ("every numeric claim...
traceable to impact-engine output"). This is the verifier doing exactly its job — being
stricter than "is this number true" and enforcing "is this number specifically an impact
result" — and it's worth stating plainly in any write-up rather than implying the raw rate
reflects invented statistics.

## E3 / scenario compiler — still deferred

Unchanged from Week 3: the 40 hand-labeled ground-truth configs need to come from the
user, not be authored by the agent building the compiler being evaluated.

## Next

Sitrep RAG interrogator (local embeddings, citations) and README polish (all three eval
tables, hazard-map hero images, limitation write-up) remain. Given for how long this
session has run, worth a checkpoint with the user before continuing further into either.
