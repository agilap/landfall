"""Narrator: cached impact-engine output -> plain-language briefing.

PRD §5.2 (originally specified as a Haiku-class Anthropic model; the user directed a
switch to an OpenAI small model instead — see docs/phase4-result.md for that decision).
No load-bearing number may originate here: the prompt hands the model exactly the cached
figures it's allowed to state and instructs it not to introduce others. The groundedness
verifier (landfall/verify/groundedness.py) is what actually enforces that, not the prompt
alone — prompts are not a security/correctness boundary.

v1.2 Phase 2: damage is stated as a low-high range, not a point estimate, per
docs/v1.2-phase1-result.md — no single number in that calibration's output is more
"correct" than the range's endpoints, so narrating a false-precision point estimate
would misrepresent the model's own output. The prompt explicitly forbids averaging the
two bounds into a new figure, since that would be an invented statistic the verifier
would (correctly) flag as ungrounded.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You write short, plain-language disaster-briefing paragraphs for a \
typhoon damage simulation tool. You are given exactly three numbers: a low-end and a \
high-end estimate of total economic damage in USD, and an estimated affected \
population. State the damage as a range using both numbers exactly as given (for \
example, "an estimated $X to $Y in damage") — do not average, split the difference, or \
state any single damage figure of your own. The range may be wide; that reflects \
genuine calibration uncertainty in the underlying model, not imprecision to smooth \
over, so do not editorialize about the range being too wide or unhelpful. State the \
affected population plainly. Describe the scenario in one or two sentences. Do not \
state any other number — no percentages, no wind speeds, no storm categories, no dates \
beyond the storm's name and year if given, no per-household or per-capita figures. Do \
not invent statistics. This is a research/preparedness demonstration, not a real \
forecast; if the scenario is a counterfactual (not what actually happened), say so \
explicitly."""


def narrate(scenario_description: str, damage_low_usd: float, damage_high_usd: float, affected_population: float) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    user_prompt = (
        f"Scenario: {scenario_description}\n"
        f"Estimated damage (USD), low end: {damage_low_usd:,.2f}\n"
        f"Estimated damage (USD), high end: {damage_high_usd:,.2f}\n"
        f"Estimated affected population: {affected_population:,.0f}\n\n"
        "Write the briefing paragraph now."
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
