"""Compare the GROWTH-objective team vs the RECOVERY-FACTOR-objective team (user: 'look at
recovery factor first' to cut drawdown). Same R1-R4 pool, max_corr=0.7. Reports each team's
RF (raw + ex-top3), growth@24%DD, and $1000 outcome at a fixed f=1% (DD comparable) and at
the DD-matched f. RF-first should surface a lower-DD, more drawdown-efficient combination."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import promdate as p

pool = p.load_pool()


def stats_at_f(c, f):
    eq = np.cumprod(np.maximum(1 + f * c, 1e-9))
    peak = np.maximum.accumulate(eq)
    return 1000 * eq[-1], 100 * ((peak - eq) / peak).max()


for obj in ("growth", "rf"):
    sel, combined, _ = p.promdate(pool, budget=0.24, maxn=6, max_corr=0.7, objective=obj, verbose=False)
    team = pool.iloc[sel].reset_index(drop=True)
    rawRF = p.team_rf(combined, 0)[0]
    robRF = p.team_rf(combined, 3)[0]
    g24, f24 = p.growth_at_dd(combined, 0.24)
    fin1, dd1 = stats_at_f(combined, 0.01)
    fin24, dd24 = stats_at_f(combined, f24)
    print(f"\n===== objective = {obj.upper()} =====  ({len(team)} legs)")
    for _, r in team.iterrows():
        print(f"   {str(r['sym'])[:3]} {p.arch_tag(r):<10} sma{int(r['smaP'])} slow{int(r['slowP'])} "
              f"step{r['step']:.2f} tp{r['tpR']:.2f} tr{r['trailR']:.2f} | nbpR={r['nbpR']:6.1f} seg{int(r['segpos'])}/6")
    print(f"  RF raw={rawRF:.2f}  robust(ex-top3)={robRF:.2f}   growth@24%DD={g24:.1f}x (f={f24:.3f})")
    print(f"  $1000 @ f=1%:   ${fin1:>10,.0f}   maxDD {dd1:.1f}%")
    print(f"  $1000 @ 24%DD:  ${fin24:>10,.0f}   (f={f24*100:.1f}%)")
    p.print_robustness(combined, budget=0.24, drop=5)
