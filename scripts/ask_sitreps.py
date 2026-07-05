"""Ask a synthesized, cited question against the sitrep RAG corpus.

Usage: python scripts/ask_sitreps.py "<question>" [storm_key]
"""

import sys

from landfall.llm.rag_answer import answer_verified

if __name__ == "__main__":
    question = sys.argv[1]
    storm_key = sys.argv[2] if len(sys.argv) > 2 else None

    text, results, raw_report, final_report = answer_verified(question, storm_key=storm_key)

    print("ANSWER:")
    print(text)
    print()
    print("SOURCES:")
    for i, r in enumerate(results, start=1):
        print(f"[{i}] {r['source_file']} p.{r['page']} (score={r['score']:.3f})")
    print()
    print(f"raw groundedness: {raw_report.grounded_claims}/{raw_report.total_claims}")
    print(f"final groundedness: {final_report.grounded_claims}/{final_report.total_claims}")
