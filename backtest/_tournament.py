"""Phase 3 — the prom-date re-crown tournament. Pool candidates (union of incumbent
pool_*.csv + the 6 §3.6-REDUX archetype sweeps), greedy-build the team that maximizes
geometric growth@24%DD, and compare to the current 3-dancer CHAMPION (57.5x).
Usage: python _tournament.py [archonly]"""
import os
import sys
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (out/opt lives here)
import promdate as p

CHAMP = 57.5   # current crowned 3-dancer growth@24%DD (FIDELITY §3.6, same tooling)

mode = sys.argv[1] if len(sys.argv) > 1 else "union"
if mode == "archonly":
    patterns = ("out/opt/gold_*.csv", "out/opt/btc_*.csv")
    label = "NEW ARCHETYPES ONLY (preview)"
elif mode == "incumbent":
    patterns = ("out/opt/pool_*.csv",)
    label = "INCUMBENT POOL ONLY (control: same engine, no new archetypes)"
else:
    patterns = ("out/opt/pool_*.csv", "out/opt/gold_*.csv", "out/opt/btc_*.csv")
    label = "FULL UNION (incumbent + new archetypes)"

pool = p.load_pool(patterns=patterns)
sym3 = pool["sym"].astype(str).str[:3]
print(f"=== {label} ===")
print(f"pool: {len(pool)} candidates  syms={sym3.value_counts().to_dict()}")
# how many candidates per archetype survived the jackpot filter
pool = pool.assign(_a=pool.apply(p.arch_tag, axis=1).str.split("/").str[0],
                   _l=pool.apply(lambda r: {0:'ml',1:'nb',2:'pp'}[int(r['lineplace'])], axis=1))
print("survivors by trigger/line:",
      pool.groupby([sym3, "_a", "_l"]).size().to_dict())

for mc in (1.0, 0.7):
    print(f"\n----- greedy (max_corr={mc}) -----")
    sel, combined, g_rob = p.promdate(pool, budget=0.24, maxn=6, max_corr=mc, drop_top=3)
    g_raw = p.growth_at_dd(combined, 0.24)[0]
    p.report(pool, sel, combined, budget=0.24)
    p.print_robustness(combined, budget=0.24, drop=5)
    verdict = (f"NEW CROWN  +{100*(g_raw/CHAMP-1):.0f}% vs champion" if g_raw > CHAMP
               else f"champion holds ({g_raw:.1f}x < {CHAMP}x)")
    print(f"  >>> raw growth@24%DD = {g_raw:.1f}x  (robust/ex-top3 = {g_rob:.1f}x, the selection "
          f"objective)  vs CHAMPION {CHAMP}x  ->  {verdict}")
