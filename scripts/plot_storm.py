"""Plot a storm's raw IBTrACS track and its Holland (1980) wind field over its ROI.

Usage: python scripts/plot_storm.py <storm_key>
"""

import sys

import matplotlib.pyplot as plt

from landfall.hazard.tracks import get_track
from landfall.hazard.wind import wind_field
from landfall.storms import STORMS

if __name__ == "__main__":
    storm_key = sys.argv[1]
    config = STORMS[storm_key]
    tracks = get_track(storm_key)

    ax = tracks.plot()
    plt.savefig(f"outputs/maps/{storm_key}_track.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved outputs/maps/{storm_key}_track.png")

    tc = wind_field(tracks, config.roi_bounds)
    print("centroids:", tc.centroids.size)
    print("max intensity (m/s):", tc.intensity.max())
    ax = tc.plot_intensity(event=0)
    plt.savefig(f"outputs/maps/{storm_key}_wind.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved outputs/maps/{storm_key}_wind.png")
