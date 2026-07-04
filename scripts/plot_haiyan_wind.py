"""Week 1 Session 3: synthesize and plot Haiyan's Holland (1980) wind field over the Visayas."""

import matplotlib.pyplot as plt

from landfall.hazard.tracks import get_haiyan_track
from landfall.hazard.wind import haiyan_wind_field

if __name__ == "__main__":
    tracks = get_haiyan_track()
    tc = haiyan_wind_field(tracks)
    print("centroids:", tc.centroids.size)
    print("max intensity (m/s):", tc.intensity.max())

    ax = tc.plot_intensity(event=0)
    plt.savefig("outputs/maps/haiyan_wind.png", dpi=150, bbox_inches="tight")
    print("saved outputs/maps/haiyan_wind.png")
