"""Segment + MONEY report for the prom-date teams. EQUAL WEIGHTS (default, anti-curve-fit
per user). $1000 account, pooled-geometric: equity *= (1 + f*weekR), f scaled to a DD budget.
Shows additive R fingerprint (6 segments) and compounded $ at 24% and 12% DD budgets."""
import numpy as np
import promdate as P

CAP0 = 1000.0


def active_trim(v_list):
    combined = sum(v_list)
    nz = np.nonzero(combined)[0]
    a, b = nz[0], nz[-1] + 1
    return [v[a:b] for v in v_list], (a, b)


def seg6(r):
    q = len(r) // 6
    return [r[k*q:(len(r) if k == 5 else (k+1)*q)].sum() for k in range(6)]


def money(r, budget):
    mult, f = P.growth_at_dd(r, budget)
    eq = CAP0 * np.cumprod(1.0 + f * r)
    dd = (1 - eq / np.maximum.accumulate(eq)).max()
    return f, eq, dd


def report(label, cap):
    pool = P.load_pool(max_oneop=cap)
    sel, _, _ = P.promdate(pool, budget=0.24, maxn=6, max_corr=0.5, verbose=False)
    Wm = P.W(pool)
    mem = [Wm[i] for i in sel]
    mem, (a, b) = active_trim(mem)
    combined = sum(mem)                              # EQUAL weight
    weeks = len(combined)

    print(f"\n================= {label}  ({len(sel)} dancers, EQUAL weight, ${CAP0:.0f}) =================")
    for i, idx in enumerate(sel):
        row = pool.iloc[idx]
        tag = ("BtcGF-trail" if row['leg'] == 'BtcGF' else
               "GoldShield-"+("trail" if row['trailR'] > 0 else "TP") if row['leg'] == 'GoldShield' else
               row['leg'])
        print(f"  dancer {i+1}: {tag:<15} {str(row['sym'])[:3]}  sma{int(row['smaP'])} slow{int(row['slowP'])} "
              f"step{row['step']:.2f} tp{row['tpR']:.2f} tr{row['trailR']:.1f}  nbpR={row['nbpR']:.1f}")

    cum = np.cumsum(combined)
    ddR = (np.maximum.accumulate(cum) - cum).max()
    totR = combined.sum()
    segs = seg6(combined)
    segp = sum(1 for s in segs if s > 0)
    print(f"\n  --- R-space (additive, NBP) ---  totR={totR:.0f}  maxDD={ddR:.0f}R  RF={totR/ddR:.1f}  segs {segp}/6")
    print("  per-segment R: " + "  ".join(f"S{k+1}{s:+.0f}" for k, s in enumerate(segs)))

    print(f"\n  --- MONEY (${CAP0:.0f}, pooled-geometric, weekly compounding) ---")
    for budget in (0.24, 0.12):
        f, eq, dd = money(combined, budget)
        # equity at each segment boundary
        q = weeks // 6
        bnds = [(k == 5 and weeks or (k+1)*q) for k in range(6)]
        segeq = [eq[min(bn, weeks)-1] for bn in bnds]
        print(f"  @ {int(budget*100)}% DD  (f={f:.3f}/op):  ${CAP0:.0f} -> ${eq[-1]:,.0f}  "
              f"({eq[-1]/CAP0:.1f}x, {100*(eq[-1]/CAP0-1):+,.0f}%)  realizedDD={100*dd:.1f}%")
        print("     equity by segment: " + " ".join(f"${e:,.0f}" for e in segeq))


if __name__ == "__main__":
    report("2-DANCER (robust)", 40)
    report("3-DANCER (growth)", 50)
