"""IBTrACS track ingestion for the three replay storms.

Week 1 scope: fetch-and-cache only. Track perturbation (counterfactuals) is Week 3.
"""

from pathlib import Path

from climada.hazard import TCTracks

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "tracks"

# IBTrACS storm IDs (SID field), one per replay storm. Verified against the IBTrACS
# best-track archive at fetch time — do not trust this table blindly if CLIMADA's
# IBTrACS.ALL file version changes.
STORM_IDS = {
    "haiyan": "2013306N07162",
    "rolly": "2020296N10133",  # Goni (international name Rolly is PH-local)
    "odette": "2021332N05144",  # Rai (international name Odette is PH-local)
}


def get_track(storm_key: str, expected_name: str, data_dir: Path = DATA_DIR) -> TCTracks:
    """Fetch a single storm's IBTrACS track, caching to `data_dir` after first fetch.

    Raises AssertionError if the fetched track's name doesn't match `expected_name` —
    a wrong storm ID is a silent-corruption risk we refuse to guess past.
    """
    # TCTracks.{write,from}_netcdf take a folder, writing/reading one .nc file per
    # track inside it — so each storm gets its own cache subfolder.
    storm_dir = data_dir / storm_key
    storm_id = STORM_IDS[storm_key]

    if storm_dir.exists() and any(storm_dir.glob("*.nc")):
        tracks = TCTracks.from_netcdf(str(storm_dir))
    else:
        storm_dir.mkdir(parents=True, exist_ok=True)
        tracks = TCTracks.from_ibtracs_netcdf(storm_id=storm_id)
        tracks.write_netcdf(str(storm_dir))

    assert len(tracks.data) == 1, f"expected exactly one track for {storm_key}, got {len(tracks.data)}"
    name = tracks.data[0].attrs["name"]
    assert name.upper() == expected_name.upper(), (
        f"storm_id {storm_id} resolved to '{name}', expected '{expected_name}' — "
        "check STORM_IDS against the current IBTrACS archive"
    )
    return tracks


def get_haiyan_track(data_dir: Path = DATA_DIR) -> TCTracks:
    return get_track("haiyan", "HAIYAN", data_dir)
