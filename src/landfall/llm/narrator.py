"""Narrator: cached impact-engine output -> plain-language briefing.

PRD §5.2 (originally specified as a Haiku-class Anthropic model; the user directed a
switch to an OpenAI small model instead — see docs/phase4-result.md for that decision).
No load-bearing number may originate here: the prompt hands the model exactly the cached
figures it's allowed to state and instructs it not to introduce others. The groundedness
verifier (landfall/verify/groundedness.py) is what actually enforces that, not the prompt
alone — prompts are not a security/correctness boundary.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You write short, plain-language disaster-briefing paragraphs for a \
typhoon damage simulation tool. You are given exactly two numbers: total estimated \
economic damage in USD, and estimated affected population. State both numbers plainly \
and describe the scenario in one or two sentences. Do not state any other number — no \
percentages, no wind speeds, no storm categories, no dates beyond the storm's name and \
year if given, no per-household or per-capita figures. Do not invent statistics. This is \
a research/preparedness demonstration, not a real forecast; if the scenario is a \
counterfactual (not what actually happened), say so explicitly."""


def narrate(scenario_description: str, total_damage_usd: float, affected_population: float) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    user_prompt = (
        f"Scenario: {scenario_description}\n"
        f"Total estimated damage (USD): {total_damage_usd:,.2f}\n"
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
