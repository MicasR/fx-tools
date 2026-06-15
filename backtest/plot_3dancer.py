"""Equity-in-time chart (segments marked) + profit factor for the NEW 3-dancer team
(equal weight, $1000, pooled-geometric @24%DD). PF needs op-level streams -> single-pass."""
import datetime as dt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import opt_run as o
import promdate as P

CAP0 = 1000.0
EPOCH = dt.datetime(2024, 2, 26)

DANCERS = [
    ("BtcGF",      dict(smaP=18, slowP=270, step=1.1, trailR=2.5, tpR=0.0)),
    ("GoldShield", dict(smaP=7, tpR=2.0, trailR=0.0, half=0.3)),
    ("BtcPG",      dict(smaP=12, step=1.5, tpR=2.0, half=0.3)),
]

# --- combined weekly vector (equal weight) from the pool ---
pool = P.load_pool(max_oneop=50)
sel, _, _ = P.promdate(pool, 0.24, 6, max_corr=0.5, verbose=False)
mem = [P.W(pool)[i] for i in sel]
combined = sum(mem)
nz = np.nonzero(combined)[0]
a, b = nz[0], nz[-1] + 1
combined = combined[a:b]
weeks = len(combined)
dates = [EPOCH + dt.timedelta(weeks=int(a + k)) for k in range(weeks)]

g24, f = P.growth_at_dd(combined, 0.24)
eq = CAP0 * np.cumprod(1.0 + f * combined)
ddcurve = 1 - eq / np.maximum.accumulate(eq)
maxdd = ddcurve.max()
rf = combined.sum() / (np.maximum.accumulate(np.cumsum(combined)) - np.cumsum(combined)).max()

# --- profit factor from op-level streams (single-pass each dancer) ---
allR = []
print("fetching op streams for profit factor...")
for leg, fx in DANCERS:
    r = o.run_single(leg, fixed=fx)
    allR += [max(x, -1.0) for x in r["R"]]            # NBP clamp
    print(f"  {leg:<11} ops={len(r['R'])} nbpR={r.get('nbpR',0):.1f}", flush=True)
allR = np.array(allR)
gw, gl = allR[allR > 0].sum(), -allR[allR < 0].sum()
pf = gw / gl
win = 100 * (allR > 0).mean()
avgw = allR[allR > 0].mean(); avgl = allR[allR < 0].mean()

# --- plot ---
fig, ax = plt.subplots(figsize=(13, 6.5))
ax.plot(dates, eq, lw=1.8, color="#1f6feb")
ax.set_yscale("log")
ax.set_ylabel("equity  (log, $)")
ax.set_title(f"NEW 3-dancer (equal wt)  $1000 -> ${eq[-1]:,.0f}  ({g24:.1f}x @24%DD)   "
             f"PF={pf:.2f}  RF={rf:.1f}  win={win:.0f}%  maxDD={100*maxdd:.0f}%")
q = weeks // 6
_, segs = P.seg_robust(combined)
for k in range(1, 6):                                  # 5 internal segment dividers
    ax.axvline(dates[min(k*q, weeks-1)], color="grey", ls="--", lw=0.8, alpha=0.7)
for k in range(6):                                     # label each segment's R
    lo = k*q; hi = weeks if k == 5 else (k+1)*q
    xmid = dates[min((lo+hi)//2, weeks-1)]
    ax.text(xmid, eq.max()*0.6, f"S{k+1}\n{segs[k]:+.0f}R", ha="center", va="top",
            fontsize=9, color="#555")
ax.grid(True, which="both", alpha=0.25)
fig.autofmt_xdate()
fig.tight_layout()
out = "out/new_3dancer_equity.png"
fig.savefig(out, dpi=110)
print(f"\nsaved {out}")
print(f"PROFIT FACTOR = {pf:.2f}   (grossWin {gw:.0f}R / grossLoss {gl:.0f}R)")
print(f"win% {win:.1f}   avgWin {avgw:+.2f}R   avgLoss {avgl:+.2f}R   payoff {abs(avgw/avgl):.2f}")
print(f"$1000 -> ${eq[-1]:,.0f} @24%DD (f={f:.3f})  realizedDD {100*maxdd:.0f}%  RF {rf:.1f}")
