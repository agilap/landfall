"""Ad-hoc 'what actually happened' queries against the sitrep RAG corpus.

Usage: python scripts/query_sitreps.py "<question>" [storm_key]
"""

import sys

from landfall.llm.rag import query

if __name__ == "__main__":
    question = sys.argv[1]
    storm_key = sys.argv[2] if len(sys.argv) > 2 else None

    for r in query(question, top_k=5, storm_key=storm_key):
        print(f"[{r['source_file']} p.{r['page']}] score={r['score']:.3f}")
        print(r["text"][:400])
        print("---")
