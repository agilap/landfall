"""RAG answer synthesis: turn retrieved sitrep passages into a cited, narrated answer.

Different groundedness problem than the narrator's (landfall/llm/narrator.py): there
isn't a fixed pair of numbers to check against. Instead, every number the model states
must trace back to *some* number that actually appears in the retrieved passages — the
reference set is built from the passages themselves, not from cached impact-engine
output. Same verification pattern (extract numbers, check, regenerate, redact), applied
to a different source of truth.

IMPORTANT LIMITATION, partially addressed (see docs/phase6-result.md and
docs/phase7-result.md): groundedness proves a stated number appears *somewhere* in a
retrieved passage, not that it's correctly attributed to what the answer claims it's
about. The original finding was pypdf's linear text extraction flattening multi-column
NDRRMC tables so a chunk interleaved numbers and labels from unrelated rows — a confirmed
real example attributed a province-level subtotal (293,000,000) to one municipality's
row. Phase 7 replaced that with table-aware extraction (landfall/llm/rag.py) so a chunk
built from one table row never contains another row's numbers, which fixes that specific
failure mode. It does not make attribution a *proven* property in general — a retrieved
row can still be about the wrong entity if retrieval itself returns the wrong row, which
is a retrieval-quality question, not a groundedness one. Groundedness here is necessary,
not sufficient.
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

from landfall.llm.rag import query_with_expansion
from landfall.verify.groundedness import GroundednessReport, check, extract_numbers, redact_ungrounded

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
MAX_REGENERATE_ATTEMPTS = 2

SYSTEM_PROMPT = """You answer questions about what actually happened during a Philippine \
typhoon, using ONLY the numbered source passages you're given below. Every factual claim \
must be attributable to one of the passages — cite it inline like [1], [2] using the \
passage numbers given. Do not state any number that does not appear in the passages \
themselves; do not compute, estimate, sum, or extrapolate new numbers from them. If the \
passages don't answer the question, say so plainly rather than guessing."""


def _format_passages(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"[{i}] ({r['source_file']}, p.{r['page']}): {r['text']}")
    return "\n\n".join(lines)


def _draft(question: str, passages_text: str) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Passages:\n\n{passages_text}\n\nQuestion: {question}"},
        ],
    )
    return response.choices[0].message.content


def answer_verified(
    question: str, storm_key: str | None = None, top_k: int = 5
) -> tuple[str, list[dict], GroundednessReport, GroundednessReport]:
    """Returns (answer_text, cited_passages, raw_report, final_report)."""
    results = query_with_expansion(question, top_k=top_k, storm_key=storm_key)
    passages_text = _format_passages(results)

    reference_values = [v for r in results for v in extract_numbers(r["text"])]

    text = _draft(question, passages_text)
    raw_report = check(text, reference_values)

    report = raw_report
    for attempt in range(MAX_REGENERATE_ATTEMPTS):
        if not report.ungrounded:
            return text, results, raw_report, report
        logger.info("regenerating (attempt %d): ungrounded=%s", attempt + 1, report.ungrounded)
        text = _draft(question, passages_text)
        report = check(text, reference_values)

    if report.ungrounded:
        logger.warning("redacting after %d failed regenerations: %s", MAX_REGENERATE_ATTEMPTS, report.ungrounded)
        text, report = redact_ungrounded(text, reference_values)

    return text, results, raw_report, report
