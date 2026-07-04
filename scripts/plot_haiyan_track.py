"""Week 1 Session 2: plot Haiyan's raw IBTrACS track. Run from the `landfall` conda env."""

import matplotlib.pyplot as plt

from landfall.hazard.tracks import get_haiyan_track

if __name__ == "__main__":
    tracks = get_haiyan_track()
    ax = tracks.plot()
    plt.savefig("outputs/maps/haiyan_track.png", dpi=150, bbox_inches="tight")
    print("saved outputs/maps/haiyan_track.png")
