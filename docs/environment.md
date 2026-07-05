# Environment

Managed via conda (miniforge), not pip — CLIMADA's geospatial dependencies (GDAL, PROJ,
GEOS) don't resolve reliably from PyPI.

```bash
mamba create -n landfall -c conda-forge climada python=3.11
conda activate landfall   # NOT calling the env's python binary directly — see below
pip install -e .          # installs the landfall package itself
```

Pinned versions (this build): **CLIMADA 6.1.0**, **Python 3.11.15**, conda-forge channel.

## Activation matters

Always `source <miniforge>/etc/profile.d/conda.sh && conda activate landfall` before
running anything — do not invoke `.../envs/landfall/bin/python` directly. Without the
activate scripts, `PROJ_DATA` isn't set and GDAL/PROJ raise a
`PROJ: proj_create_from_database` warning on every CRS operation (harmless but noisy;
avoid it rather than debug around it repeatedly).

## Known external-data blockers and workarounds

- **Coastal-distance filter** (`TropCyclone.from_tracks`'s default
  `ignore_distance_to_coast=False`) needs a NASA raster from
  `oceancolor.gsfc.nasa.gov` that returned 403 from this network. Worked around with
  `ignore_distance_to_coast=True` — see `landfall/hazard/wind.py`.
- **GPW population data** (used internally by every `LitPop` exposure, regardless of
  exponent weighting) requires a free NASA Earthdata account and a manual SEDAC
  download; SEDAC's server was unresponsive from both a browser and a direct `curl`
  test. Substituted a WorldPop Philippines population raster instead — see
  `scripts/build_gpw_substitute.py` and `docs/phase1-result.md` for the full rationale
  and validation (total matches PHL's actual 2020 population, ~110.2M).
- IBTrACS (`TCTracks.from_ibtracs_netcdf`) and nightlights (CLIMADA's BlackMarble
  downloader) both auto-download fine — no issues there.
