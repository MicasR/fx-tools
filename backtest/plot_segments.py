"""
plot_segments.py — segment profiles: King components vs the poscandle ramps
(2026-06-12).  Pick which poscandle ramp to swap/add into the king by eyeballing
where it earns vs where geo1.7/s210/shield earn.  Stressed@$0.40, common window.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_ops import stats

A = lambda g: dict(trig="poscandle", smaP=7, slowP=0, sizing="proggeo", unit="base",
                   mult=0.01, prog_step=g, tp_R=3.0, stack=True)
KING = {
    "geo1.7":  dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210":    dict(smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield":  dict(stack=False, tp_R=2.0),
}
CAND = {"poscandle g1.1": A(1.1), "poscandle g1.2": A(1.2), "poscandle g1.3": A(1.3)}


def stream(cfg):
    res, tm, H, L, n = run_tf_conc(**cfg, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res], tm[0], tm[-1]


if __name__ == "__main__":
    allc = {**KING, **CAND}
    S = {}; t0 = t1 = None
    for nm, c in allc.items():
        s, a, b = stream(c); S[nm] = s
        t0 = a if t0 is None else min(t0, a); t1 = b if t1 is None else max(t1, b)
    St = {nm: stats([(S[nm], 1.0)], 0.40, t0, t1) for nm in allc}

    x = np.arange(6)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, sharey=True)
    kc = ["#1f77b4", "#d62728", "#2ca02c"]
    cc = ["#ff7f0e", "#9467bd", "#8c564b"]

    def panel(ax, names, cols, title):
        w = 0.8 / len(names)
        for i, nm in enumerate(names):
            s = St[nm]
            lbl = f"{nm}  ({s['tot']:.0f}R, RF {s['rf']:.1f}, 1op {s['oneop']:.0f}%)"
            ax.bar(x + (i - (len(names)-1)/2) * w, s["seg"], w, label=lbl, color=cols[i])
        ax.axhline(0, color="k", lw=0.6)
        ax.set_title(title); ax.legend(fontsize=8, ncol=1, loc="upper left")
        ax.set_ylabel("R per segment"); ax.grid(True, axis="y", alpha=0.25)

    panel(ax1, list(KING), kc, "KING components (stressed @ $0.40)")
    panel(ax2, list(CAND), cc, "Candidate: add-on-every-positive-candle (geo ramp)")
    ax2.set_xticks(x); ax2.set_xticklabels([f"seg{i+1}" for i in range(6)])
    fig.suptitle("Segment profiles — pick the poscandle ramp to swap/add on the King", y=0.995)
    fig.tight_layout()
    fig.savefig("out/segments.png", dpi=110)
    print("saved out/segments.png")
    # also print the table
    print(f"\n{'strategy':<16}{'totR':>7}{'RF':>6}{'1op':>5}   per-segment R")
    for nm in allc:
        s = St[nm]
        print(f"{nm:<16}{s['tot']:>7.0f}{s['rf']:>6.1f}{s['oneop']:>4.0f}%   " +
              " ".join(f"{v:+6.1f}" for v in s["seg"]))
