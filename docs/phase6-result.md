# Phase 6 result — RAG answer synthesis, and a real limitation it surfaced

## What was built

`landfall/llm/rag_answer.py` — an LLM synthesis layer on top of Phase 4b's retrieval,
reusing the narrator's verify/regenerate/redact pattern (`landfall/verify/groundedness.py`,
now exposing `extract_numbers` publicly instead of privately) but against a different
notion of "grounded": there's no fixed pair of reference numbers here, so the reference
set is built by extracting every number that appears anywhere in the retrieved passages
themselves. The model is instructed to cite passages inline (`[1]`, `[2]`, ...) and told
explicitly not to compute, sum, or extrapolate new numbers — only state ones that appear
verbatim in a passage.

## Retrieval is sensitive to query phrasing — a real, documented finding

First test query: *"What did the sitreps actually record about Catanduanes during Typhoon
Rolly?"* (a natural phrasing, close to the PRD's own representative query). Top-5
retrieval returned zero passages mentioning Catanduanes at all, and the model correctly
answered "the passages don't mention Catanduanes" — the right behavior when it lacks
support, not a groundedness failure.

But Catanduanes content clearly exists in the corpus — a plain keyword query
("Catanduanes damage") surfaces it immediately at rank 2. The full natural-language
question's embedding apparently doesn't weight "Catanduanes" strongly enough against the
rest of the question's phrasing to retrieve the same passages a terser query does. Raising
`top_k` from 5 to 10 on the same question did surface *a* Catanduanes-relevant passage
(telecom outage figures), but still not the water-infrastructure damage passage a keyword
query finds at rank 1. No query rewriting/expansion is built to compensate — this is a
real, live limitation of the current retrieval, not fixed in this pass.

## A more serious finding: groundedness doesn't mean correct attribution

Retesting with a more targeted phrasing — *"What was the cost of damage to water
infrastructure in Catanduanes from Typhoon Rolly?"* — retrieved the right passage
(`sitrep_12.pdf p.35`) and produced a fully grounded answer on the first draft (5/5, no
regeneration needed):

> "The cost of damage to water infrastructure in Catanduanes from Typhoon Rolly was
> 293,000,000.00 for Baras, with additional significant costs... Bato (12,500,000.00),
> Pandan (13,000,000.00)..."

Every number in that answer does appear in the retrieved passage — the verifier is
working correctly by its own definition. **But checking the raw extracted PDF text shows
this is very likely a wrong attribution.** `pdftotext`/`pypdf`'s linear text extraction
flattens multi-column tables into a single stream, and the actual text around
"293,000,000.00" interleaves fragments that look like a *different* table (Buenavista,
Mogpog, Gubat, Bulan — Marinduque/Sorsogon municipalities, not Catanduanes) rather than a
clean Catanduanes-only damage table. The number is real and present in the source
document; whether it means what the synthesized answer claims it means is not verified by
anything built so far.

This is the load-bearing limitation of this phase, stated as plainly as possible:
**the groundedness verifier proves numeric fidelity (nothing was invented), not semantic
correctness of what a number is attached to.** For table-heavy government PDFs — which
describes most of this corpus — that gap matters a lot. A structural fix would mean
table-aware PDF extraction (e.g. `pdfplumber`'s table-detection mode, or `camelot`)
instead of per-page linear text chunking, preserving row/column structure so a retrieved
chunk carries "this number belongs to this row" rather than an ambiguous stream of
numbers and labels. Not attempted here — flagged honestly instead of either quietly
shipping a plausible-looking wrong answer or overstating what verification actually
covers.

## Where this leaves E2's "100% groundedness" framing

Worth being precise: Phase 4's E2 metric (100% final groundedness) is about the
*narrator*, whose only allowed numbers are two fixed, unambiguous cached figures (total
damage, affected population) — there's no attribution question there, a number either
matches one of two known values or it doesn't. This phase's RAG synthesis is a
structurally harder problem (open-ended source text, tabular data, many candidate
numbers) and "100% groundedness" would mean something narrower than it sounds if reported
the same way. Not folding this into an E2-style aggregate metric for that reason — the
two are different guarantees and shouldn't be presented as the same number.

## Not built

- Query rewriting/expansion to close the retrieval-phrasing gap.
- Table-aware PDF extraction to fix the attribution problem described above.
- An eval analogous to E2 for this layer — would need a way to check attribution
  correctness, not just numeric presence, which is a harder labeling problem (likely
  needs human-checked ground truth per passage, similar in spirit to E3's constraint).
