"""Phase 2 regression gate: confirm the §3.6-REDUX EA rebuild reproduces the locked
legs' NBP R-streams on the default path (ADD_SMA_BOUNCE / LINE_MARGIN / no buffer).
Expected (FIDELITY §3.4, NBP): BtcGF ~190, GoldS210 ~157."""
import opt_run

EXPECT = {"BtcGF": 190.0, "GoldS210": 157.0}
for leg, exp in EXPECT.items():
    r = opt_run.run_single(leg)
    nb = r.get("nbpR", float("nan"))
    delta = (nb - exp) / exp * 100 if exp else 0.0
    flag = "OK" if abs(delta) <= 5 else "DRIFT"
    print(f"{leg:10s} nbpR={nb:7.1f} (expect ~{exp:.0f}, {delta:+.1f}%) "
          f"ops={r.get('ops')} segpos={r.get('segpos')}/6 1op={r.get('oneop'):.0f}% [{flag}]")
