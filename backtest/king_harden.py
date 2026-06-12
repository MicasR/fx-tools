"""
king_harden.py — harden the new king (2026-06-12).

(1) FULL 2D weight grid over the three ops-accounts (only the weight RATIOS
    matter -- geo_sim sizes total f to the DD budget, so a common scale on the
    weights cancels).  Tests the user's hypothesis: does MORE shield weight let
    the SWORDS run hotter (higher f) enough to beat the 45/45/10 king?  Reports
    growth @ matched DD AND the sized f (the 'aggression' level) at the optimum.
(2) SHIELD TP robustness: is the +26% a knife-edge in the shield's TP?  Sweep
    TP 1.75 / 2.0 / 2.25 / 2.5 at the best weights.
Geometric scale-to-DD, stressed @ $0.40.
"""
from concurrent_geo import geo_sim, at_dd, FGRID
from concurrent_ops import stream
from shield import run_shield


def sh_stream(tp):
    return [(t0, t1, R, None) for t0, t1, R in run_shield(tp_R=tp)[0]]


def at(legs, budget):
    cur = [(f, *geo_sim(legs, f)) for f in FGRID]
    return at_dd(cur, budget)        # (growth, f) or None


if __name__ == "__main__":
    G = stream("geo1.7", 0.005)[0]
    S = stream("f5/s210 1.5%", 0.005)[0]
    SH = sh_stream(2.0)

    geo_shares = [0.30, 0.40, 0.50, 0.60, 0.70]   # geo's share of the sword budget
    shield_ws  = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    best = None
    print("=== (1) 2D weight grid: growth x @ 24% DD  (rows=shield%, cols=geo-share-of-swords) ===")
    print(f"{'shield%':>8}" + "".join(f"{f'geo {int(gs*100)}%':>10}" for gs in geo_shares))
    for sw in shield_ws:
        sb = 1 - sw
        cells = ""
        for gs in geo_shares:
            legs = [(G, gs*sb), (S, (1-gs)*sb), (SH, sw)]
            r = at(legs, 24.0)
            g = r[0] if r else 0
            cells += f"{g:>10.1f}"
            if best is None or g > best[0]:
                best = (g, sw, gs, r[1] if r else 0)
        print(f"{int(sw*100):>7}%{cells}")

    bg, bsw, bgs, bf = best
    print(f"\n--> BEST @24%DD = {bg:.1f}x at shield {int(bsw*100)}%, "
          f"geo {int(bgs*100)}%/s210 {int((1-bgs)*100)}% of swords  (sized f={bf*100:.2f}%)")
    print(f"    weights: geo {(1-bsw)*bgs*100:.0f}% / s210 {(1-bsw)*(1-bgs)*100:.0f}% / shield {bsw*100:.0f}%")
    print(f"    vs old king COMBO1 21.9x  and  45/45/10 king 27.6x")

    print("\n    aggression check (f sized to 24% DD) vs shield weight, geo=s210:")
    for sw in (0.0, 0.10, 0.20, 0.30):
        half = (1-sw)/2
        r = at([(G, half), (S, half), (SH, sw)], 24.0)
        print(f"      shield {int(sw*100):>2}% -> f={r[1]*100:.2f}%  growth {r[0]:.1f}x")

    print("\n=== (2) shield TP robustness at the best weights (growth x @ DD budgets) ===")
    print(f"{'shield TP':>10}{'@13%':>9}{'@18%':>9}{'@24%':>9}{'@30%':>9}")
    sb = 1 - bsw
    for tp in (1.75, 2.0, 2.25, 2.5):
        legs = [(G, bgs*sb), (S, (1-bgs)*sb), (sh_stream(tp), bsw)]
        row = "".join(f"{at(legs, b)[0]:>9.1f}" if at(legs, b) else f"{'--':>9}"
                      for b in (13.0, 18.0, 24.0, 30.0))
        print(f"{f'TP{tp}':>10}{row}")
