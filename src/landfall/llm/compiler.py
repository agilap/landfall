"""Scenario compiler: natural-language counterfactual request -> validated ScenarioConfig.

PRD §5.1/§6: the LLM's only job is extraction — map the user's words onto the four
schema fields literally, or emit a refusal when the request is out of scope (anything
beyond wind-only track/intensity perturbation of a registered storm), unquantified, or
names an unknown storm. It must never clamp, normalize, or guess. The deterministic gate
is ScenarioConfig's pydantic validation, not the prompt: whatever JSON the model emits
still has to pass the same hard range checks as a hand-written config, and a validation
failure becomes a human-readable refusal, never a silently adjusted config.
"""

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from landfall.scenario import MAX_INTENSITY_DELTA_KN, MAX_TRACK_OFFSET_KM, ScenarioConfig

load_dotenv()

MODEL = "gpt-4o-mini"

# PH-local <-> international names for the three registered storms. The compiler should
# resolve either name to the registry key; anything else is an unregistered storm.
STORM_ALIASES = {
    "haiyan": "haiyan",
    "yolanda": "haiyan",
    "rolly": "rolly",
    "goni": "rolly",
    "odette": "odette",
    "rai": "odette",
}

SYSTEM_PROMPT = f"""You compile natural-language typhoon counterfactual requests into a \
strict JSON config for a wind-only damage simulation. Registered storms and their name \
aliases (either name maps to the same key): haiyan/Yolanda -> "haiyan", Rolly/Goni -> \
"rolly", Odette/Rai -> "odette". No other storm is available.

Config fields:
- storm_key: one of "haiyan", "rolly", "odette"
- track_offset_km: how far the whole track is shifted, in km (0 if unchanged)
- track_bearing_deg: compass bearing of the shift (0=north, 90=east, 180=south, \
270=west; northeast=45, southeast=135, southwest=225, northwest=315)
- intensity_delta_kn: knots added to max sustained wind at every track point \
(negative to weaken, 0 if unchanged)

Valid ranges (inclusive unless noted): track_offset_km in [0, {MAX_TRACK_OFFSET_KM:.0f}], \
track_bearing_deg in [0, 360) — so 0, 30, 200, 315 are all valid, 360 and above are not — \
and intensity_delta_kn in [{-MAX_INTENSITY_DELTA_KN:.0f}, {MAX_INTENSITY_DELTA_KN:.0f}], \
with both endpoints valid.

Fields the request does not mention default to 0 — an intensity-only request has \
track_offset_km 0, a track-only request has intensity_delta_kn 0, and an exact \
historical replay ("as it happened", "no changes") is valid with all three numeric \
fields 0. Never refuse because a field is simply unmentioned.

Extract the request LITERALLY. Never clamp an out-of-range value into range, never \
normalize a bearing, never guess a number the user did not state. Respond with exactly \
one JSON object:
- {{"config": {{...the four fields...}}}} if the request is a wind-only track/intensity \
perturbation (or exact historical replay) of a registered storm and every value the \
user DID state is in range.
- {{"refusal": "<one-sentence reason>"}} otherwise — unknown storm, no storm named, a \
requested value out of range, a requested change left unquantified (e.g. just \
"stronger" with no number), or anything the schema cannot express: storm surge, \
flooding, rainfall, sea level, stalling, forward speed, casualties, or any non-wind \
hazard."""


@dataclass(frozen=True)
class CompileResult:
    config: ScenarioConfig | None
    refusal: str | None

    @property
    def rejected(self) -> bool:
        return self.config is None


def compile_scenario(text: str) -> CompileResult:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    raw = json.loads(response.choices[0].message.content)

    if "refusal" in raw:
        return CompileResult(config=None, refusal=str(raw["refusal"]))
    if "config" not in raw:
        return CompileResult(config=None, refusal=f"Compiler emitted neither config nor refusal: {raw}")

    # Deterministic alias resolution: if the model emits a PH-local/international name
    # instead of the registry key (e.g. "goni" for rolly), map it here rather than
    # relying on the prompt. Unknown names fall through to pydantic's storm check.
    if isinstance(raw["config"], dict) and isinstance(raw["config"].get("storm_key"), str):
        key = raw["config"]["storm_key"].lower()
        raw["config"]["storm_key"] = STORM_ALIASES.get(key, key)

    # The deterministic gate: pydantic re-validates every field against the same hard
    # ranges as a hand-written config. A model that clamped or hallucinated fails here.
    try:
        config = ScenarioConfig(**raw["config"])
    except ValidationError as e:
        reasons = "; ".join(err["msg"] for err in e.errors())
        return CompileResult(config=None, refusal=f"Extracted config failed validation: {reasons}")
    return CompileResult(config=config, refusal=None)
