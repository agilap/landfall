"""Registry of replay storms. PRD §2's original v1 non-goal ("no nationwide coverage —
only regions affected by Haiyan/Rolly/Odette") scoped the first three; a 4th
(Mangkhut/Ompong, 2018) was added by explicit author direction after v1.2, still one
storm at a time with the same verification discipline, not a drift toward nationwide
coverage — see docs/v1.3-phase1-result.md. IBTrACS SIDs and ROI bounds are verified
against fetched data, not guessed; see docs/phase2-result.md (original three) and
docs/v1.3-phase1-result.md (Mangkhut) for how each ROI was chosen.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StormConfig:
    key: str
    ibtracs_sid: str
    ibtracs_name: str  # international name IBTrACS uses; may differ from the PH-local name
    roi_bounds: tuple[float, float, float, float]  # (lon_min, lat_min, lon_max, lat_max)
    year: int  # verified against the actual fetched track's timestamps, not guessed —
    # adding a 4th storm surfaced this same year hardcoded separately (and left stale) in
    # cli.py and evals/e2_groundedness.py; living here once is the actual fix, not a
    # per-callsite patch of the same duplication


STORMS = {
    "haiyan": StormConfig(
        key="haiyan",
        ibtracs_sid="2013306N07162",
        ibtracs_name="HAIYAN",
        roi_bounds=(121.5, 8.0, 126.5, 13.0),  # Visayas: Samar, Leyte, Cebu, Bohol, Negros, Panay
        year=2013,
    ),
    "rolly": StormConfig(
        key="rolly",
        ibtracs_sid="2020299N11144",
        ibtracs_name="GONI",
        roi_bounds=(122.0, 12.0, 125.5, 15.0),  # Bicol Region + Catanduanes landfall corridor
        year=2020,
    ),
    "odette": StormConfig(
        key="odette",
        ibtracs_sid="2021346N05145",
        ibtracs_name="RAI",
        roi_bounds=(119.5, 7.5, 127.5, 11.5),  # Palawan-Visayas-Mindanao (Surigao) corridor
        year=2021,
    ),
    "mangkhut": StormConfig(
        key="mangkhut",
        ibtracs_sid="2018250N12170",
        ibtracs_name="MANGKHUT",
        # Northern Luzon corridor: Cagayan/Isabela (landfall near Baggao, ~18.06N 121.87E)
        # west through Ilocos/Cordillera (incl. Itogon, Benguet) to the exit into the West
        # Philippine Sea, per the actual track's PH-transit segment (2018-09-14/15), not
        # guessed — see docs/v1.3-phase1-result.md. Zero overlap with the other three ROIs.
        roi_bounds=(119.0, 15.5, 123.5, 19.5),
        year=2018,
    ),
}
