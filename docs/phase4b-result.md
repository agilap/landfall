# Phase 4b result — sitrep RAG interrogator

## Corpus acquisition (the actual work here)

PRD §5.2 calls for "NDRRMC situation reports and PAGASA bulletins... public PDFs." Getting
them was the hard part, not the RAG mechanics:

1. **`ndrrmc.gov.ph` blocks automated requests** — not a login gate like GPW, but a
   Cloudflare JS challenge ("Just a moment...") that `curl` structurally cannot pass
   regardless of User-Agent spoofing. No amount of retrying fixes this; it needs a real
   browser.
2. **ReliefWeb (reliefweb.int, run by UN OCHA) mirrors NDRRMC sitreps** as its own hosted
   PDFs, without that gating. Found the right report pages via `WebSearch`, then scraped
   each page's HTML for the direct PDF attachment link (curl with a browser User-Agent
   was enough for ReliefWeb itself, unlike ndrrmc.gov.ph).
3. **The first Haiyan document downloaded (Sitrep 104) had zero extractable text** —
   `pdftotext` returned nothing, meaning it's a scanned image with no text layer (common
   for 2013-era scanned government documents). No OCR tooling was available without a
   system package install, so rather than reach for that, found a different Haiyan
   report (Sitrep 108, April 2014) that has a real text layer and used that instead.

Final corpus: one sitrep per storm — Haiyan (Sitrep 108), Rolly (Sitrep 12, the
highest-numbered/most cumulative found), Odette (Sitrep 36). Small by design for Phase 4;
expanding to more sitreps per storm is a mechanical repeat of the same pipeline, not a new
capability.

## Pipeline

- **`landfall/llm/rag.py`** — `pypdf` extracts per-page text, chunked at 800 characters
  with 100-character overlap (whitespace-collapsed first, since PDF extraction leaves
  ragged line breaks). Embedded locally with `BAAI/bge-m3` via `sentence-transformers` —
  no API calls for retrieval, per PRD §5.3's local-model stack.
- **CPU-only, not GPU** — this dev environment has no GPU (PRD's RTX 3050 4GB target is
  the user's actual machine, not this sandbox). Caught and fixed a wasted install
  partway through: `pip install sentence-transformers` pulls torch's full CUDA build by
  default (~1.9GB of `nvidia-*` packages), which is useless without a GPU. Killed that
  install and did `pip install torch --index-url https://download.pytorch.org/whl/cpu`
  first instead.
- Embedding 2,067 chunks from 3 documents took ~18 minutes on CPU — slow, but a one-time
  cost; cached to `data/cache/rag/{embeddings.npy,chunks.json}`.
- Retrieval: cosine similarity (embeddings are pre-normalized, so a dot product is
  cosine similarity) over the full chunk set, optionally filtered to one storm. Every
  result carries `(source_file, page)` — the citation PRD §5.2 requires.

## Retrieval example

Query: *"What is the total cost of damage to infrastructure and agriculture from Typhoon
Rolly?"* (storm-filtered to Rolly)

Top result: `sitrep_12.pdf p.37` — a DA (Department of Agriculture) regional damage table
with per-region PHP figures, correctly surfaced from a 2,067-chunk corpus. Other results
in the top 5 pulled DSWD DROMIC family-assistance tables and a general hazard-exposure
note. This is retrieval working as intended: real, citable NDRRMC figures, not invented
ones — directly reusable as ground truth for the E1 comparison table (Phase 2) if a tighter
per-region figure is ever needed there.

## Known limitation, stated honestly

One sitrep per storm is a thin corpus — a single document's assessment stage (e.g.
Rolly's Sitrep 12 is from 11 Nov 2020, days after landfall; later revisions likely
adjusted figures upward, same pattern as Odette's figures that were still growing months
after the storm per Phase 2's E1 write-up). Retrieval quality and citation correctness are
solid; corpus *completeness* is not — a query asking about a region not covered in the one
ingested sitrep will retrieve the closest available match rather than admit absence. No
"I don't know" / insufficient-evidence path is implemented yet. Worth flagging in any
write-up rather than implying full coverage.

## Not built (deliberately, scope)

- **Answer synthesis** — this delivers retrieval + citations, not a synthesized
  natural-language answer. PRD §5.2's "supports 'what actually happened' queries" reads
  as retrieval-level support; adding an LLM synthesis pass on top (with its own
  groundedness verification, reusing the Phase 4 narrator/verifier pattern) is a natural
  next step, not attempted here to avoid extending an already-long session.
- **PAGASA bulletins** — only NDRRMC sitreps ingested so far. Same pipeline, different
  source.
