"""Generate PD2_*.set presets for the crowned robust team (FIDELITY §3.6-REDUX).
Pulls the 6 selected legs' exact params from the pool and writes one .set per leg."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import promdate as p

PRE = "ExpertAdvisors/CrossKing_EA/presets"
ADDT = {0: "Bounce", 1: "Poscandle"}
LINE = {0: "ml", 1: "nb", 2: "pin"}

pool = p.load_pool()
sel, _, _ = p.promdate(pool, budget=0.24, maxn=6, max_corr=1.0, drop_top=3, verbose=False)
team = pool.iloc[sel].reset_index(drop=True)

print(f"{'preset':22s} sym  trig      line nback buf  sizing smaP slowP step  tpR  trailR half nbpR")
for i, r in team.iterrows():
    xau = str(r["sym"]).startswith("XAU")
    mtf = 15 if xau else 16385
    style = ("Trail" if r["trailR"] > 0 else ("Pin" if int(r["lineplace"]) == 2 else
             ("Nb" if int(r["lineplace"]) == 1 else ("Pc" if int(r["addtrig"]) == 1 else "Geo"))))
    name = f"PD2_{'Gold' if xau else 'Btc'}{style}_{i}"
    magic = 30260611 + i
    lines = [
        f"; CrossKing PROM-DATE2 robust team (FIDELITY 3.6-REDUX) -- {name}",
        f"; {'XAUUSDc' if xau else 'BTCUSDc'} chart H1, mgmt {'M15' if xau else 'H1'}. Equal weight (1/{len(team)}).",
        f"; tester-true nbpR~{r['nbpR']:.0f} segpos {int(r['segpos'])}/6 extop1R {r['extop1R']:.0f}."
        f" {'AGGRESSIVE STACKER -- path-sensitive +-10-36% run-to-run.' if r['trailR']==0 else 'trail leg.'}",
        f"InpLegName={name}", f"InpMagicNumber={magic}", "InpEntryTF=16385",
        f"InpMgmtTF={mtf}", "InpMAPeriod=20", "InpMultiplier=2.0", "InpRisePct=0.02",
        "InpBreakBars=4", "InpStack=true", f"InpSizing={int(r['sizing'])}",
        f"InpSmaP={int(r['smaP'])}", f"InpSlowP={int(r['slowP'])}", f"InpMult={r['mult']}",
        f"InpProgStep={r['step']}", f"InpHalf={r['half']}", f"InpTpR={r['tpR']}",
        f"InpTrailR={r['trailR']}", f"InpAddTrigger={int(r['addtrig'])}",
        f"InpLinePlace={int(r['lineplace'])}", f"InpNBack={int(r['nback'])}",
        f"InpLineBuffer={r['buffer']}", "InpTROverride=0.0", "InpMPLOverride=0.0",
        "InpDeviation=50", "InpTelemetryURL=", "InpHeartbeatSec=30",
    ]
    with open(f"{PRE}/{name}.set", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{name:22s} {str(r['sym'])[:3]}  {ADDT[int(r['addtrig'])]:9s} "
          f"{LINE[int(r['lineplace'])]:4s} {int(r['nback']):4d} {r['buffer']:.2f} "
          f"{int(r['sizing']):5d} {int(r['smaP']):4d} {int(r['slowP']):5d} {r['step']:.2f} "
          f"{r['tpR']:.2f} {r['trailR']:.2f}  {r['half']:.1f} {r['nbpR']:.0f}")
print(f"\nwrote {len(team)} presets to {PRE}/PD2_*.set")
