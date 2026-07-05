"""Counterfactual scenario config: schema, deterministic validation, and track perturbation.

PRD §5.1: counterfactuals apply parametric perturbations (track translation, intensity
delta) to the historical track before wind-field synthesis. PRD §4.2: "fail loud, not
plausible" — invalid inputs are rejected outright, not clamped or guessed past.

Known simplification: intensity_delta_kn adjusts max_sustained_wind only. central_pressure
is left untouched, so the Holland model's implied pressure-wind relationship becomes
mildly inconsistent after a large intensity perturbation. Acceptable for Week 3's "however
wrong" scope; revisit if counterfactual results look physically implausible.
"""

import copy
import hashlib
import json

from geopy.distance import geodesic
from pydantic import BaseModel, field_validator

from landfall.storms import STORMS

MAX_TRACK_OFFSET_KM = 500.0  # beyond this, "shift the track" stops being a meaningful ask
MAX_INTENSITY_DELTA_KN = 60.0  # roughly one Saffir-Simpson category's worth of wind speed


class ScenarioConfig(BaseModel):
    storm_key: str
    track_offset_km: float = 0.0
    track_bearing_deg: float = 0.0  # compass bearing: 0=N, 90=E, 180=S, 270=W
    # IBTrACS (and CLIMADA's TCTracks) store max_sustained_wind in knots, not m/s —
    # this field matches that unit deliberately, to avoid a silent unit-conversion bug.
    intensity_delta_kn: float = 0.0  # added to max_sustained_wind at every track point

    @field_validator("storm_key")
    @classmethod
    def _storm_must_be_registered(cls, v):
        if v not in STORMS:
            raise ValueError(f"'{v}' is not a registered storm (must be one of {list(STORMS)})")
        return v

    @field_validator("track_offset_km")
    @classmethod
    def _offset_in_range(cls, v):
        if not (0.0 <= v <= MAX_TRACK_OFFSET_KM):
            raise ValueError(f"track_offset_km must be in [0, {MAX_TRACK_OFFSET_KM}], got {v}")
        return v

    @field_validator("track_bearing_deg")
    @classmethod
    def _bearing_in_range(cls, v):
        if not (0.0 <= v < 360.0):
            raise ValueError(f"track_bearing_deg must be in [0, 360), got {v}")
        return v

    @field_validator("intensity_delta_kn")
    @classmethod
    def _intensity_delta_in_range(cls, v):
        if not (-MAX_INTENSITY_DELTA_KN <= v <= MAX_INTENSITY_DELTA_KN):
            raise ValueError(
                f"intensity_delta_kn must be in [{-MAX_INTENSITY_DELTA_KN}, {MAX_INTENSITY_DELTA_KN}], got {v}"
            )
        return v

    def is_historical_baseline(self) -> bool:
        return self.track_offset_km == 0.0 and self.intensity_delta_kn == 0.0

    def scenario_hash(self) -> str:
        canonical = json.dumps(self.model_dump(), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def perturb_track(tracks, config: ScenarioConfig):
    """Apply `config`'s track offset and intensity delta to a copy of `tracks`."""
    perturbed = copy.deepcopy(tracks)
    track = perturbed.data[0]

    if config.track_offset_km > 0:
        new_lats = []
        new_lons = []
        for lat, lon in zip(track.lat.values, track.lon.values):
            dest = geodesic(kilometers=config.track_offset_km).destination(
                point=(float(lat), float(lon)), bearing=config.track_bearing_deg
            )
            new_lats.append(dest.latitude)
            new_lons.append(dest.longitude)
        track["lat"] = ("time", new_lats)
        track["lon"] = ("time", new_lons)

    if config.intensity_delta_kn != 0:
        track["max_sustained_wind"] = (track["max_sustained_wind"] + config.intensity_delta_kn).clip(min=0)

    return perturbed
