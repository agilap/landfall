"""One-time data-prep: substitute a WorldPop raster for CLIMADA's GPW population dependency.

CLIMADA's LitPop exposure always loads a GPW population raster internally (even when the
LitPop 'pop' exponent is 0 — verified empirically), and CLIMADA has no automated fetch for
it: the file must be downloaded manually from SEDAC, which requires a free NASA Earthdata
account. That download was attempted and SEDAC's server was unresponsive from this network
(confirmed both from the user's browser and via a direct curl from this machine — a broadly
flaky host, not a login problem).

WorldPop (https://www.worldpop.org, CC BY 4.0) publishes an equivalent Philippines
population-count GeoTIFF with no login required. CLIMADA's own grid-alignment code
(`grid_aligned_with_gpw`) only reads the *origin* of whatever file sits at the expected GPW
path and phases a global grid to it at the caller's requested resolution (150 arcsec here,
not GPW's native 30 arcsec) — so a country-cropped substitute at a different native
resolution works correctly with no further re-projection needed. WorldPop's native 3
arc-second grid is in fact finer than GPW's 30 arc-second grid.

The only real fix needed: WorldPop's nodata sentinel (-99999) must not be read as a literal
population count by downstream disaggregation math, so it's zeroed out here.

Total population after the fix sanity-checks at ~110M, matching the Philippines' actual
2020 population — this is a legitimate substitute, not an approximation of last resort.

Revisit if/when a real GPW download succeeds; this script would then be unnecessary.
"""

from pathlib import Path

import numpy as np
import rasterio

SRC = Path("/home/alex/landfall/data/cache/worldpop/phl_ppp_2020.tif")
DST_DIR = Path(
    "/home/alex/climada/data/gpw-v4-population-count-rev11_2020_30_sec_tif"
)
DST = DST_DIR / "gpw_v4_population_count_rev11_2020_30_sec.tif"

PAD_DEG = 0.25  # generous margin so the raster fully encloses PHL's national boundary
# polygon (which extends slightly past WorldPop's own raster edge on the north/east —
# outlying islets like Y'Ami/Itbayat in Batanes), avoiding a zero-overlap window crash
# in CLIMADA's per-polygon masking.

if __name__ == "__main__":
    DST_DIR.mkdir(parents=True, exist_ok=True)

    with rasterio.open(SRC) as src:
        arr = src.read(1)
        transform = src.transform
        meta = src.meta.copy()

    arr = np.where(arr < 0, 0.0, arr).astype("float32")

    res = transform.a
    pad_px = int(round(PAD_DEG / res))
    padded = np.zeros(
        (arr.shape[0] + 2 * pad_px, arr.shape[1] + 2 * pad_px), dtype="float32"
    )
    padded[pad_px : pad_px + arr.shape[0], pad_px : pad_px + arr.shape[1]] = arr

    new_transform = rasterio.Affine(
        transform.a, 0, transform.c - pad_px * res, 0, transform.e, transform.f - pad_px * transform.e
    )
    meta.update(
        dtype="float32",
        nodata=None,
        width=padded.shape[1],
        height=padded.shape[0],
        transform=new_transform,
    )

    with rasterio.open(DST, "w", **meta) as dst:
        dst.write(padded, 1)

    print(f"wrote {DST}")
    print("total population:", float(padded.sum()))
