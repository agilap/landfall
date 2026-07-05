"""Sitrep RAG interrogator: chunk NDRRMC PDFs, embed locally (bge-m3), retrieve with
citations. PRD §5.2: "Retrieval must attach source-document citations."

Local embeddings only — no API calls for retrieval itself, per PRD §5.3's local-model
stack. The corpus is small (one sitrep per storm, Week 4 scope); a flat numpy cosine
search is simpler and just as correct as a real vector DB at this size, and adding one
would be premature.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "sitreps"
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "rag"
EMBEDDING_MODEL = "BAAI/bge-m3"
CHUNK_SIZE = 800  # characters, not tokens — good enough for this corpus size
CHUNK_OVERLAP = 100


@dataclass
class Chunk:
    text: str
    storm_key: str
    source_file: str
    page: int


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


def load_corpus() -> list[Chunk]:
    chunks = []
    for storm_dir in sorted(DATA_DIR.iterdir()):
        if not storm_dir.is_dir():
            continue
        for pdf_path in sorted(storm_dir.glob("*.pdf")):
            reader = PdfReader(str(pdf_path))
            for page_num, page in enumerate(reader.pages, start=1):
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
        json.dumps([{"text": c.text, "storm_key": c.storm_key, "source_file": c.source_file, "page": c.page} for c in chunks])
    )
    print(f"indexed {len(chunks)} chunks from {len(set(c.source_file for c in chunks))} documents")


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


if __name__ == "__main__":
    build_index()
