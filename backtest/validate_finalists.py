"""Finalist validation: re-run each chosen dancer single-pass on the tester and confirm
its fingerprint reproduces the prom-date pool (catches any pool-data error). Margin
feasibility at 1R is enforced by the EA's MarginCap (sizing uses E0=1R), so a reproduced
stream IS margin-feasible."""
import opt_run as o

# the 5 distinct dancers across BOTH teams
DANCERS = {
    "2D_BtcGF":      ("BtcGF",      dict(smaP=15, slowP=240, step=1.1, trailR=2.5, tpR=0.0)),
    "2D_GoldShield": ("GoldShield", dict(smaP=7, tpR=0.0, trailR=3.5, half=0.3)),
    "3D_BtcGF":      ("BtcGF",      dict(smaP=18, slowP=270, step=1.1, trailR=2.5, tpR=0.0)),
    "3D_GoldShield": ("GoldShield", dict(smaP=7, tpR=2.0, trailR=0.0, half=0.3)),
    "3D_BtcPG":      ("BtcPG",      dict(smaP=12, step=1.5, tpR=2.0, half=0.3)),
}

# expected from the pool (pool nbpR / segpos / 1op)
EXPECT = {
    "2D_BtcGF": (208.1, 6, 35), "2D_GoldShield": (64.5, 4, 31),
    "3D_BtcGF": (223.8, 5, 45), "3D_GoldShield": (37.7, 4, 5), "3D_BtcPG": (38.5, 5, 6),
}

if __name__ == "__main__":
    print(f"{'dancer':<14}{'ops':>5}{'nbpR':>8}{'seg':>5}{'1op':>6}{'RF':>6}   {'exp nbpR/seg/1op':>18}  match")
    for name, (leg, fixed) in DANCERS.items():
        r = o.run_single(leg, fixed=fixed)
        en, es, eo = EXPECT[name]
        ok = abs(r.get("nbpR", 0) - en) < max(2.0, 0.03 * en) and r.get("segpos", -1) == es
        print(f"{name:<14}{r.get('ops',0):>5}{r.get('nbpR',0):>8.1f}{r.get('segpos',0):>4}/6"
              f"{r.get('oneop',0):>5.0f}%{r.get('rf',0):>6.1f}   {en:>6.1f}/{es}/{eo:<3}        "
              f"{'OK' if ok else 'MISMATCH'}", flush=True)
