"""IBTrACS track ingestion for the three replay storms.

Week 1-2 scope: fetch-and-cache only. Track perturbation (counterfactuals) is Week 3.
"""

from pathlib import Path

from climada.hazard import TCTracks

from landfall.storms import STORMS

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "tracks"


def get_track(storm_key: str, data_dir: Path = DATA_DIR) -> TCTracks:
    """Fetch a single storm's IBTrACS track, caching to `data_dir` after first fetch.

    Raises AssertionError if the fetched track's name doesn't match the registry's
    ibtracs_name — a wrong storm ID is a silent-corruption risk we refuse to guess past.
    """
    config = STORMS[storm_key]

    # TCTracks.{write,from}_netcdf take a folder, writing/reading one .nc file per
    # track inside it — so each storm gets its own cache subfolder.
    storm_dir = data_dir / storm_key

    if storm_dir.exists() and any(storm_dir.glob("*.nc")):
        tracks = TCTracks.from_netcdf(str(storm_dir))
    else:
        storm_dir.mkdir(parents=True, exist_ok=True)
        tracks = TCTracks.from_ibtracs_netcdf(storm_id=config.ibtracs_sid)
        tracks.write_netcdf(str(storm_dir))

    assert len(tracks.data) == 1, f"expected exactly one track for {storm_key}, got {len(tracks.data)}"
    name = tracks.data[0].attrs["name"]
    assert name.upper() == config.ibtracs_name.upper(), (
        f"storm_id {config.ibtracs_sid} resolved to '{name}', expected "
        f"'{config.ibtracs_name}' — check STORMS registry against the current IBTrACS archive"
    )
    return tracks
