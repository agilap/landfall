"""Compare the WP2 (Philippines) TC impact function under TDR (CLIMADA default,
Landfall's original choice) vs RMSF (v1.1 Phase 1) — damage fraction vs wind speed.

Eberenz et al. 2021, NHESS 21:393-415, https://doi.org/10.5194/nhess-21-393-2021.
v_half values are read live from CLIMADA's bundled calibration files, not hardcoded,
so this plot can't drift out of sync with engine.py's actual parameter.

Usage: python scripts/plot_impact_curves.py
"""

import matplotlib.pyplot as plt
import numpy as np
from climada.entity.impact_funcs.trop_cyclone import ImpfSetTropCyclone

from landfall.impact.engine import IMPF_CALIBRATION_APPROACH, PHILIPPINES_IMPF_ID

if __name__ == "__main__":
    wind_speeds = np.arange(0, 121, 1)

    fig, ax = plt.subplots(figsize=(7, 5))
    for approach, style in [("TDR", "--"), (IMPF_CALIBRATION_APPROACH, "-")]:
        impf_set = ImpfSetTropCyclone.from_calibrated_regional_ImpfSet(calibration_approach=approach)
        impf = impf_set.get_func(fun_id=PHILIPPINES_IMPF_ID)[0]
        v_half = ImpfSetTropCyclone.calibrated_regional_vhalf(calibration_approach=approach)["WP2"]
        mdd = np.interp(wind_speeds, impf.intensity, impf.mdd)
        label = f"{approach} (v_half={v_half:.1f} m/s)"
        if approach == "TDR":
            label += " — original"
        else:
            label += " — v1.1 Phase 1"
        ax.plot(wind_speeds, mdd, style, label=label)

    for name, speed in [("Haiyan peak (~87 m/s)", 87), ("Cat 5 threshold (70 m/s)", 70)]:
        ax.axvline(speed, color="gray", linestyle=":", linewidth=0.8)
        ax.text(speed + 1, 0.02, name, rotation=90, fontsize=8, color="gray", va="bottom")

    ax.set_xlabel("Wind speed (m/s)")
    ax.set_ylabel("Mean damage degree (fraction of exposed value)")
    ax.set_title("WP2 (Philippines) TC impact function: TDR vs RMSF calibration")
    ax.legend()
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig("docs/impact_curves_tdr_vs_rmsf.png", dpi=150)
    print("saved docs/impact_curves_tdr_vs_rmsf.png")
