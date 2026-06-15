"""Generate PD3_*.set presets for the crowned KING (GROWTH-6 weight-opt) + a weight manifest.
Each leg = one ops-account; the KING weight = that account's capital allocation share
(realized by funding; InpFixedE0=0 live = whole-account balance). Strategy params from pool."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import promdate as p

PRE = "ExpertAdvisors/CrossKing_EA/presets"
pool = p.load_pool()
sel, _, _ = p.promdate(pool, 0.24, 6, max_corr=1.0, drop_top=3, verbose=False)
team = pool.iloc[sel].reset_index(drop=True)
w, _, _ = p.weight_optimize(team, list(range(len(sel))), budget=0.24)
w = w / w.sum()

man = ["# KING = GROWTH-6 weight-opt (FIDELITY 3.6-REDUX). $1000 @24%DD -> $40,919, PF 2.69, RF 5.39,",
       "# 6/6 segs, max concurrent 5.4%. Each leg = 1 ops-account; weight = capital allocation share.",
       "", "| preset | sym | mgmt | role | weight | magic |", "|---|---|---|---|---|---|"]
for i, r in team.iterrows():
    xau = str(r["sym"]).startswith("XAU")
    mtf = 15 if xau else 16385
    style = ("Trail" if r["trailR"] > 0 else ("Pin" if int(r["lineplace"]) == 2 else
             ("Nb" if int(r["lineplace"]) == 1 else "Geo")))
    name = f"PD3_{'Gold' if xau else 'Btc'}{style}_{i}"
    magic = 30260621 + i
    wt = w[i] * 100
    lines = [
        f"; KING (GROWTH-6 weight-opt) -- {name} -- weight {wt:.1f}% of capital",
        f"; {'XAUUSDc' if xau else 'BTCUSDc'} chart H1, mgmt {'M15' if xau else 'H1'}. tester-true nbpR~{r['nbpR']:.0f}, seg{int(r['segpos'])}/6.",
        f"; ORCHESTRATOR: fund this ops-account with {wt:.1f}% of pooled risk capital (InpFixedE0=0 live).",
        f"InpLegName={name}", f"InpMagicNumber={magic}", "InpEntryTF=16385", f"InpMgmtTF={mtf}",
        "InpMAPeriod=20", "InpMultiplier=2.0", "InpRisePct=0.02", "InpBreakBars=4",
        "InpStack=true", f"InpSizing={int(r['sizing'])}", f"InpSmaP={int(r['smaP'])}",
        f"InpSlowP={int(r['slowP'])}", f"InpMult={r['mult']}", f"InpProgStep={r['step']}",
        f"InpHalf={r['half']}", f"InpTpR={r['tpR']}", f"InpTrailR={r['trailR']}",
        f"InpAddTrigger={int(r['addtrig'])}", f"InpLinePlace={int(r['lineplace'])}",
        f"InpNBack={int(r['nback'])}", f"InpLineBuffer={r['buffer']}",
        "InpTROverride=0.0", "InpMPLOverride=0.0", "InpDeviation=50",
        "InpTelemetryURL=", "InpHeartbeatSec=30",
    ]
    with open(f"{PRE}/{name}.set", "w") as f:
        f.write("\n".join(lines) + "\n")
    man.append(f"| {name} | {str(r['sym'])[:3]} | {'M15' if xau else 'H1'} | {style} | **{wt:.1f}%** | {magic} |")
    print(f"wrote {name}.set  weight={wt:.1f}%")

with open(f"{PRE}/PD3_KING_manifest.md", "w") as f:
    f.write("\n".join(man) + "\n")
print(f"\nwrote {PRE}/PD3_KING_manifest.md")
