"""RAG interrogator storm/date phrasing robustness check.

Not a numbered E-eval (no PRD §6 slot for this) -- a regression check born out of
directly testing how `landfall/llm/rag_answer.py` handles storm identity and date
references in free-text questions, both with and without the `storm_key` filter
(landfall/cli.py's `--storm`). Two failure modes matter here, checked differently:

1. Retrieval correctness when no filter is given: does the query text alone (a PH-local
   name, an international name, a bare date) correctly surface the right storm's
   passages? Checked by asserting the top retrieved passage's `storm_key`.
2. Synthesis safety when the filter and the query's own storm/date reference disagree
   (a user error, or a storm/date genuinely absent from the filtered corpus): does the
   model correctly decline rather than fabricate a cross-storm answer? Checked by
   asserting the *raw* (pre-verifier) draft has zero ungrounded claims -- not that zero
   claims are stated at all. A correct decline often restates a truthfully-grounded
   date while explaining the mismatch (e.g. "they only reference events in November
   2020"), which is legitimate context, not fabrication; the first version of this
   check asserted zero claims and wrongly flagged two such correct, safe declines as
   failures before this was caught and fixed.

Requires OPENAI_API_KEY. Run from the `landfall` conda env: python evals/rag_storm_date_cases.py
"""

from landfall.llm.rag import query_with_expansion
from landfall.llm.rag_answer import answer_verified

# (label, question, storm_filter, expected_top_storm_key)
RETRIEVAL_CASES = [
    ("PH-local name, no filter", "What happened in Catanduanes during Typhoon Rolly?", None, "rolly"),
    ("International name, no filter", "What happened in Catanduanes during Typhoon Goni?", None, "rolly"),
    ("Date only, no filter", "What happened in Catanduanes in early November 2020?", None, "rolly"),
]

# (label, question, storm_filter) -- all expected to produce zero grounded claims,
# i.e. a correct decline rather than a fabricated cross-storm/cross-date answer.
REFUSAL_CASES = [
    ("filter=rolly, query names Haiyan", "What happened during Typhoon Haiyan in Catanduanes?", "rolly"),
    ("filter=rolly, wrong year in query", "What happened in Catanduanes in November 2013?", "rolly"),
    ("filter=haiyan, query names Rolly", "What was the water damage in Catanduanes from Typhoon Rolly?", "haiyan"),
    (
        "compound two-storm query, no filter",
        "Compare what happened during Typhoon Haiyan and Typhoon Rolly in terms of water damage.",
        None,
    ),
    ("plausible-but-wrong date, filter=rolly", "What happened in Catanduanes on November 15, 2020?", "rolly"),
    ("vague relative date, no filter", "What happened last week during the typhoon?", None),
]


def main():
    failures = []

    print("--- retrieval correctness (no filter, storm identified by query text alone) ---")
    for label, question, storm_filter, expected_storm in RETRIEVAL_CASES:
        results = query_with_expansion(question, top_k=5, storm_key=storm_filter)
        actual_storm = results[0]["storm_key"] if results else None
        ok = actual_storm == expected_storm
        print(f"[{'OK' if ok else 'FAIL'}] {label}: top result storm={actual_storm} (expected {expected_storm})")
        if not ok:
            failures.append(label)

    print("\n--- synthesis safety (filter/query mismatch must decline, not fabricate) ---")
    for label, question, storm_filter in REFUSAL_CASES:
        text, _results, raw, _final = answer_verified(question, storm_key=storm_filter)
        ok = not raw.ungrounded
        print(f"[{'OK' if ok else 'FAIL'}] {label}: raw ungrounded={raw.ungrounded}")
        if not ok:
            print(f"    text: {text}")
            failures.append(label)

    print(f"\n{len(RETRIEVAL_CASES) + len(REFUSAL_CASES) - len(failures)}/{len(RETRIEVAL_CASES) + len(REFUSAL_CASES)} passed")
    if failures:
        print(f"failures: {failures}")


if __name__ == "__main__":
    main()
