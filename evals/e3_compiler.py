"""E3 — Scenario compiler accuracy (PRD §6).

Runs the NL -> ScenarioConfig compiler over evals/e3_dataset.json: 40 valid scenarios
scored on exact-config accuracy (all four fields must match the hand-labeled ground
truth exactly), plus 10 deliberately invalid scenarios scored on rejection correctness
(the compiler must refuse, not clamp or guess). Every miss is printed in full — the
misses are the interesting part.

Requires OPENAI_API_KEY. Run from the `landfall` conda env: python evals/e3_compiler.py
"""

import json
from pathlib import Path

from landfall.llm.compiler import compile_scenario

DATASET = Path(__file__).parent / "e3_dataset.json"


def main():
    cases = json.loads(DATASET.read_text())

    exact = 0
    for case in cases["valid"]:
        result = compile_scenario(case["text"])
        if result.rejected:
            print(f"MISS (valid #{case['id']}, wrongly rejected): {case['text']}")
            print(f"  refusal: {result.refusal}")
            continue
        got = result.config.model_dump()
        if got == case["expected"]:
            exact += 1
        else:
            print(f"MISS (valid #{case['id']}, wrong config): {case['text']}")
            print(f"  expected: {case['expected']}")
            print(f"  got:      {got}")

    rejected = 0
    for case in cases["invalid"]:
        result = compile_scenario(case["text"])
        if result.rejected:
            rejected += 1
        else:
            print(f"MISS (invalid #{case['id']}, wrongly accepted): {case['text']}")
            print(f"  should reject because: {case['why_invalid']}")
            print(f"  got config: {result.config.model_dump()}")

    n_valid, n_invalid = len(cases["valid"]), len(cases["invalid"])
    print(f"\nExact-config accuracy:  {exact}/{n_valid} = {exact / n_valid:.1%}")
    print(f"Rejection correctness:  {rejected}/{n_invalid} = {rejected / n_invalid:.1%}")


if __name__ == "__main__":
    main()
