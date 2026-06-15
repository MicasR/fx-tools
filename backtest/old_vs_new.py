"""Head-to-head: the OLD oracle-crowned kings vs the NEW prom-date teams, BOTH on the
trustworthy tester (NBP weekly vectors), $1000, growth-at-matched-DD. Fair because the
f-scaling pins every contender to the same DD budget (scale-invariant)."""
import numpy as np
import opt_run as o
import promdate as P

CAP0, WCOLS = 1000.0, P.WCOLS
KINGS = ["GoldGeo17", "GoldS210", "GoldShield", "BtcGF", "BtcPG", "BtcShield"]


def king_weekly(leg, half=0.5):
    # 2-value sweep (MT5 needs >=2 combos to run optimization/frames); pick the king's half
    df = o.run_opt(f"king_{leg}", leg, opt={"half": (0.5, 0.2, 0.7)}, fixed={}, mode=1, timeout=600)
    r = df.iloc[(df["half"] - half).abs().idxmin()]
    return r[WCOLS].to_numpy(float), r["nbpR"], int(r["segpos"]), r["oneop"]


def trim(v_list):
    nz = np.nonzero(sum(v_list))[0]
    return [v[nz[0]:nz[-1] + 1] for v in v_list]


def seg6(r):
    q = len(r) // 6
    return [r[k*q:(len(r) if k == 5 else (k+1)*q)].sum() for k in range(6)]


def line(label, combined):
    cum = np.cumsum(combined)
    ddR = (np.maximum.accumulate(cum) - cum).max()
    tot = combined.sum()
    segs = seg6(combined); segp = sum(1 for s in segs if s > 0)
    g24, f24 = P.growth_at_dd(combined, 0.24)
    g12, _ = P.growth_at_dd(combined, 0.12)
    print(f"{label:<26}{tot:>7.0f}{ddR:>7.0f}{tot/ddR:>6.1f}{segp:>4}/6  "
          f"{g24:>7.1f}x ${CAP0*g24:>9,.0f}   {g12:>6.1f}x ${CAP0*g12:>8,.0f}   "
          + " ".join(f"{s:+.0f}" for s in segs))


if __name__ == "__main__":
    print("fetching old-king weekly vectors from the tester...")
    wk = {}
    for lg in KINGS:
        wk[lg], nbp, sp, op = king_weekly(lg)
        print(f"  {lg:<11} nbpR={nbp:6.1f} segs={sp}/6 1op={op:.0f}%", flush=True)

    goldking = 0.500*wk["GoldGeo17"] + 0.375*wk["GoldS210"] + 0.125*wk["GoldShield"]
    btcking = 0.552*wk["BtcGF"] + 0.248*wk["BtcPG"] + 0.200*wk["BtcShield"]
    old_cross = 0.5*goldking + 0.5*btcking

    # new teams (equal weight) from the pool
    pool40 = P.load_pool(max_oneop=40); s2, _, _ = P.promdate(pool40, 0.24, 6, max_corr=0.5, verbose=False)
    pool50 = P.load_pool(max_oneop=50); s3, _, _ = P.promdate(pool50, 0.24, 6, max_corr=0.5, verbose=False)
    new2 = sum(P.W(pool40)[i] for i in s2)
    new3 = sum(P.W(pool50)[i] for i in s3)

    print(f"\n{'contender (tester-true)':<26}{'totR':>7}{'ddR':>7}{'RF':>6}{'segs':>6}  "
          f"{'g@24%DD  $1000->':>18}  {'g@12%DD  $1000->':>16}   per-seg R")
    g, = trim([goldking]); line("OLD Gold King (trio)", g)
    b, = trim([btcking]); line("OLD BTC King (trio)", b)
    oc, = trim([old_cross]); line("OLD cross (50/50, 6 legs)", oc)
    n2, = trim([new2]); line("NEW 2-dancer (equal)", n2)
    n3, = trim([new3]); line("NEW 3-dancer (equal)", n3)
    print("\n  oracle claimed: Gold 38.9x / BTC 37.7x / cross 128.8x @24%DD  (INFLATED -- compare to the tester rows above)")
