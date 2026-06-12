"""
concurrent_weight.py — WEIGHT sweep on the two-account blend (2026-06-12).

concurrent_geo found COMBO1 (geo1.7 + s210, 50/50) beats every standalone on
growth-at-matched-DD, and that geo1.7 out-grows s210 alone.  So the 50/50 split
may not be optimal: tilt the total risk budget f between the two accounts
(w to geo1.7, 1-w to the partner) and find the mix that maximises terminal
growth at a fixed DD budget.  w=0 => partner alone, w=1 => geo1.7 alone.

Reuses the geometric scale-to-DD machinery (stake = f * weight * current C per
op, sized so the blend hits the DD budget).  Stressed @ $0.40, same stable-edge
assumption (trustworthy in the DD<=24% / f~1-2% zone).
"""
from concurrent_geo import geo_sim, at_dd, FGRID
from concurrent_ops import stream, CFG

if __name__ == "__main__":
    S = {nm: stream(nm, 0.005)[0] for nm in CFG}     # one edge stream per config

    partners = {"s210": "f5/s210 1.5%", "s200": "f5/s200"}
    budgets = (13.0, 18.0, 24.0)
    wgrid = [0.0, 0.25, 0.40, 0.50, 0.60, 0.75, 1.0]

    for tag, partner in partners.items():
        print(f"\n=== weight sweep: w*geo1.7 + (1-w)*{tag}  (growth x @ matched DD, f%) ===")
        print(f"{'w(geo1.7)':>10}  " + "".join(f"{f'DD {int(b)}%':>20}" for b in budgets))
        for w in wgrid:
            legs = [(S["geo1.7"], w), (S[partner], 1.0 - w)]
            curve = [(f, *geo_sim(legs, f)) for f in FGRID]
            cells = ""
            for b in budgets:
                r = at_dd(curve, b)
                cells += (f"{r[0]:>11.1f}x @{r[1]*100:>4.2f}%" if r else f"{'--':>20}")
            lab = "(s%s alone)" % tag[1:] if w == 0 else ("(geo1.7 alone)" if w == 1 else "")
            print(f"{w:>10.2f}  {cells}  {lab}")
