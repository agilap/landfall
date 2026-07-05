"""Registry of the three PRD-scoped replay storms — the only three in v1 (PRD §2 non-goals:
no nationwide coverage). IBTrACS SIDs and ROI bounds are verified against fetched data, not
guessed; see docs/week2-result.md for how each ROI was chosen.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StormConfig:
    key: str
    ibtracs_sid: str
    ibtracs_name: str  # international name IBTrACS uses; may differ from the PH-local name
    roi_bounds: tuple[float, float, float, float]  # (lon_min, lat_min, lon_max, lat_max)


STORMS = {
    "haiyan": StormConfig(
        key="haiyan",
        ibtracs_sid="2013306N07162",
        ibtracs_name="HAIYAN",
        roi_bounds=(121.5, 8.0, 126.5, 13.0),  # Visayas: Samar, Leyte, Cebu, Bohol, Negros, Panay
    ),
    "rolly": StormConfig(
        key="rolly",
        ibtracs_sid="2020299N11144",
        ibtracs_name="GONI",
        roi_bounds=(122.0, 12.0, 125.5, 15.0),  # Bicol Region + Catanduanes landfall corridor
    ),
    "odette": StormConfig(
        key="odette",
        ibtracs_sid="2021346N05145",
        ibtracs_name="RAI",
        roi_bounds=(119.5, 7.5, 127.5, 11.5),  # Palawan-Visayas-Mindanao (Surigao) corridor
    ),
}
