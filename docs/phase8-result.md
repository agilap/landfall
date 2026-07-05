# Phase 8 result — RAG table-aware extraction and query rewriting

## Why this phase exists

docs/phase6-result.md flagged two live limitations and deliberately left both unfixed:
retrieval missing a passage a plain keyword query finds easily, and — the more serious
one — a fully "grounded" (5/5) answer that misattributed a province-level subtotal
(293,000,000) to a specific municipality (Baras), because pypdf's linear text extraction
flattens multi-column NDRRMC tables into an ambiguous character stream. This phase
attempts both fixes.

## Fix 1: table-aware extraction (`landfall/llm/rag.py`)

`load_corpus()` now uses `pdfplumber` instead of `pypdf` for pages where a table is
detected: `page.extract_tables()` returns each row as a list of cells, which are chunked
in small row-aligned windows (`TABLE_ROWS_PER_CHUNK = 4`, 1-row overlap) — a chunk never
splits a row's cells, so a number stays grouped with only its own row's label, not a
neighboring row's. Pages with no detected table (narrative text) keep the original
linear per-page chunking unchanged. Reindexed corpus: 6,255 chunks (6,022 table-row, 233
text) across the three sitreps — up from the prior page-level chunking because table
rows are now indexed individually rather than folded into fixed-size character blocks.

Re-running Phase 6's exact documented case confirms the fix directly. The top-retrieved
chunk for a Catanduanes water-infrastructure query is now:

```
Cabusao | Office building and equipment and pumping station | Damaged; low water pressure | 1,000,000.00
Calabanga | Office building, motor controls... | Flooded office building... | 5,000,000.00
Catanduanes | 0 | 0 | 293,000,000.00
Baras | Water sources, treatment facilities, transmission and distribution network and office building | Major and extensive damages; no water supply | 12,500,000.00
```

293,000,000 and 12,500,000 now sit as two distinct, clearly-labeled rows in the same
chunk, instead of an ambiguous flattened stream. The synthesized answer correctly states
"the cost of damage to water infrastructure in Catanduanes... was 293,000,000.00" (1/1
grounded) without attaching it to Baras. Asking the inverse, municipality-specific
question ("How much did Baras, Catanduanes specifically suffer?") correctly returns
Baras's own 12,500,000 figure, separately noting Catanduanes' 293,000,000 province total
as a distinct, unexplained-detail figure rather than conflating the two (2/2 grounded).

This is a real fix for the documented failure mode, not a general proof of correct
attribution — see "what this doesn't fix" below.

## Fix 2: query rewriting (`landfall/llm/rag.expand_query` / `query_with_expansion`)

Phase 6's other finding: a full natural-language question ("What did the sitreps
actually record about Catanduanes during Typhoon Rolly?") returned zero Catanduanes
passages at top_k=5, while a terse keyword query ("Catanduanes damage") found the same
content immediately. `expand_query()` asks `gpt-4o-mini` (temperature 0) to rewrite a
question into 2 short keyword-style alternates, and `query_with_expansion()` runs
retrieval over the original question plus both rewrites, merging by taking each chunk's
best score across variants.

First prompt draft included the storm name in the rewritten queries (e.g. "Catanduanes
Typhoon Rolly water infrastructure damage cost") — this made retrieval *worse*: bge-m3
weighted the narrative phrase "Typhoon Rolly" so heavily that a passage merely mentioning
the storm's name outranked the correct tabular passage, even though the query is already
storm-filtered separately (`storm_key="rolly"`) so the storm name adds nothing but noise.
Revised prompt explicitly forbids the storm name and prefers 2-4 word place+subject
queries; the correct table-row chunk moved from absent (top 10) to rank 1 (score 0.646).
This dependency on prompt phrasing for a retrieval-quality aid is why `expand_query`'s
docstring is explicit that it can only help or hurt recall, never introduce a
groundedness failure — it never states a figure itself.

`rag_answer.answer_verified()` now calls `query_with_expansion()` instead of `query()`.

## What this doesn't fix

- **Attribution is still not a proven property in general.** Table-row chunking fixes
  the *specific* documented failure (subtotal/detail-row conflation from flattened text);
  it doesn't guarantee every retrieved row is about the entity a question asks about — if
  retrieval itself surfaces the wrong row, the answer can still be wrong while every
  number in it is individually "grounded" (present in a retrieved passage). Groundedness
  remains necessary, not sufficient — restated in `rag_answer.py`'s module docstring.
- **No eval analogous to E2/E3 for retrieval or attribution quality** — same constraint
  E3 already surfaced: judging "is this the right row" needs human-checked ground truth
  per query, not something to generate by the agent that built the retriever.
- Query rewriting is a small, fixed 2-variant expansion, not iterative or
  relevance-feedback-based; it compensates for the one documented phrasing failure mode,
  not a general retrieval-robustness guarantee.
- Table detection depends on pdfplumber finding a grid in the PDF's underlying vector
  lines; a table rendered without detectable cell borders would silently fall back to
  linear chunking with the original attribution risk.
