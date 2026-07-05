"""Sitrep RAG interrogator: chunk NDRRMC PDFs, embed locally (bge-m3), retrieve with
citations. PRD §5.2: "Retrieval must attach source-document citations."

Local embeddings only — no API calls for retrieval itself, per PRD §5.3's local-model
stack. The corpus is small (one sitrep per storm, Phase 4 scope); a flat numpy cosine
search is simpler and just as correct as a real vector DB at this size, and adding one
would be premature.

Table-aware extraction (Phase 7, see docs/phase6-result.md): NDRRMC sitreps are
table-heavy. pypdf's linear per-page text extraction flattens multi-column tables into
one stream, so a chunk can interleave a number with a label from an unrelated row — a
confirmed real case put a province-level subtotal in the same chunk as, and readable as
belonging to, an unrelated municipality's row. pdfplumber's grid-aware table extraction
keeps each row's cells together, so a chunk built from one row never contains another
row's numbers. Pages with a detected table are chunked by table row instead of by raw
character count; pages without one (narrative text) keep the old linear chunking.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pdfplumber
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

load_dotenv()

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "sitreps"
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "rag"
EMBEDDING_MODEL = "BAAI/bge-m3"
CHUNK_SIZE = 800  # characters, not tokens — good enough for this corpus size
CHUNK_OVERLAP = 100
TABLE_ROWS_PER_CHUNK = 4  # small window: enough row-to-row context, never splits a row
TABLE_ROW_OVERLAP = 1

QUERY_EXPANSION_MODEL = "gpt-4o-mini"


@dataclass
class Chunk:
    text: str
    storm_key: str
    source_file: str
    page: int
    is_table: bool = False


def _chunk_page_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = " ".join(text.split())  # collapse whitespace/newlines from PDF extraction
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _format_table_row(row: list[str | None]) -> str:
    cells = [c.replace("\n", " ").strip() for c in row if c and c.strip()]
    return " | ".join(cells)


def _chunk_table(
    table: list[list[str | None]], rows_per_chunk: int = TABLE_ROWS_PER_CHUNK, overlap: int = TABLE_ROW_OVERLAP
) -> list[str]:
    """Groups a table's rows into small row-aligned windows, never splitting a row's
    cells across two chunks — the property that keeps a number attached to the rest of
    its own row instead of a neighboring one."""
    formatted_rows = [_format_table_row(row) for row in table]
    formatted_rows = [r for r in formatted_rows if r]
    if not formatted_rows:
        return []
    chunks = []
    start = 0
    step = max(rows_per_chunk - overlap, 1)
    while start < len(formatted_rows):
        window = formatted_rows[start : start + rows_per_chunk]
        chunks.append("\n".join(window))
        start += step
    return chunks


def load_corpus() -> list[Chunk]:
    chunks = []
    for storm_dir in sorted(DATA_DIR.iterdir()):
        if not storm_dir.is_dir():
            continue
        for pdf_path in sorted(storm_dir.glob("*.pdf")):
            with pdfplumber.open(str(pdf_path)) as pdf:
                tables_by_page = {i: page.extract_tables() for i, page in enumerate(pdf.pages, start=1)}

            reader = PdfReader(str(pdf_path))
            for page_num, page in enumerate(reader.pages, start=1):
                tables = tables_by_page.get(page_num) or []
                if tables:
                    for table in tables:
                        for chunk_text in _chunk_table(table):
                            chunks.append(
                                Chunk(
                                    text=chunk_text,
                                    storm_key=storm_dir.name,
                                    source_file=pdf_path.name,
                                    page=page_num,
                                    is_table=True,
                                )
                            )
                else:
                    page_text = page.extract_text() or ""
                    for chunk_text in _chunk_page_text(page_text):
                        chunks.append(
                            Chunk(text=chunk_text, storm_key=storm_dir.name, source_file=pdf_path.name, page=page_num)
                        )
    return chunks


def build_index() -> None:
    chunks = load_corpus()
    model = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = model.encode([c.text for c in chunks], normalize_embeddings=True, show_progress_bar=True)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CACHE_DIR / "embeddings.npy", embeddings)
    (CACHE_DIR / "chunks.json").write_text(
        json.dumps(
            [
                {
                    "text": c.text,
                    "storm_key": c.storm_key,
                    "source_file": c.source_file,
                    "page": c.page,
                    "is_table": c.is_table,
                }
                for c in chunks
            ]
        )
    )
    n_table = sum(c.is_table for c in chunks)
    n_docs = len(set(c.source_file for c in chunks))
    print(f"indexed {len(chunks)} chunks ({n_table} table-row, {len(chunks) - n_table} text) from {n_docs} documents")


def query(text: str, top_k: int = 5, storm_key: str | None = None) -> list[dict]:
    """Returns top_k chunks (with citation metadata) most similar to `text`."""
    embeddings = np.load(CACHE_DIR / "embeddings.npy")
    chunks = json.loads((CACHE_DIR / "chunks.json").read_text())

    model = SentenceTransformer(EMBEDDING_MODEL)
    query_emb = model.encode([text], normalize_embeddings=True)[0]

    scores = embeddings @ query_emb
    if storm_key:
        mask = np.array([c["storm_key"] == storm_key for c in chunks])
        scores = np.where(mask, scores, -np.inf)

    top_indices = np.argsort(scores)[::-1][:top_k]
    return [{**chunks[i], "score": float(scores[i])} for i in top_indices]


QUERY_EXPANSION_PROMPT = """You turn a natural-language question about a Philippine \
typhoon's aftermath into short, keyword-style search queries for a semantic search index \
over NDRRMC situation reports. The index sometimes underweights a specific place name \
against the rest of a full question's phrasing, so your job is to produce terser \
variants that foreground the place name(s) and subject matter.

Rules for the alternates:
- Never include the storm/typhoon's name or "typhoon" itself — retrieval is already \
filtered to that storm's documents separately, and including it dilutes the embedding \
away from the place name that actually needs to stand out.
- Prefer 2-4 words: a place name plus the narrowest subject noun (e.g. "water \
infrastructure", "school damage", "evacuees"). Drop generic words like "cost", "report", \
or "damage" alone if a more specific noun is available.

Given the question, respond with exactly one JSON object: {"queries": [...]} containing \
2 short alternate search strings (not full sentences) — do not include the original \
question, just the alternates. Example: given "What did the sitreps record about damage \
to water infrastructure in Catanduanes?", respond with something like \
{"queries": ["Catanduanes water infrastructure", "Catanduanes water supply damage"]}."""


def expand_query(question: str) -> list[str]:
    """Query-rewriting aid for retrieval only (see module docstring / docs/phase6-result.md
    for the phrasing-sensitivity finding this addresses) — it never states a figure, so it
    carries none of the narrator/RAG-answer groundedness risk that verify/groundedness.py
    guards against. A failure here degrades retrieval recall, not numeric correctness."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=QUERY_EXPANSION_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": QUERY_EXPANSION_PROMPT},
            {"role": "user", "content": question},
        ],
    )
    raw = json.loads(response.choices[0].message.content)
    return [str(q) for q in raw.get("queries", [])]


def query_with_expansion(question: str, top_k: int = 5, storm_key: str | None = None) -> list[dict]:
    """Runs retrieval over the original question plus a couple of LLM-generated keyword
    rewrites, then merges by taking each chunk's best score across all variants. Chunks
    that only a rewrite (not the original phrasing) surfaces are exactly the retrieval
    gap documented in docs/phase6-result.md — a keyword query found the right passage at
    rank 1 while the natural-language question missed it at top_k=5."""
    variants = [question] + expand_query(question)

    best: dict[tuple[str, int, str], dict] = {}
    for variant in variants:
        for result in query(variant, top_k=top_k, storm_key=storm_key):
            key = (result["source_file"], result["page"], result["text"])
            if key not in best or result["score"] > best[key]["score"]:
                best[key] = result

    return sorted(best.values(), key=lambda r: r["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    build_index()
