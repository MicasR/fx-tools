"""
king_segments.py — per-segment R: new king vs old king (2026-06-12).

R-stream view (1%-units, stressed@$0.40), same time window for all rows.
NOTE: in raw totR the new king is EXPECTED to be <= the old king -- the shield
sleeve trades a little totR for lower DD / more evenness; the win shows up in
geometric growth-at-DD (king_harden), not raw totR.  This table is for the
segment/DD/concentration picture.
  old king COMBO1 = geo .5 / s210 .5
  new king        = geo .45 / s210 .45 / TP2.0-shield .10
"""
from concurrent_ops import stream, stats, row, HDR
from shield import run_shield

if __name__ == "__main__":
    G, ag, bg = stream("geo1.7", 0.005)
    S, asx, bsx = stream("f5/s210 1.5%", 0.005)
    sh_ops, ash, bsh = run_shield(tp_R=2.0)
    SH = [(t0, t1, R, None) for t0, t1, R in sh_ops]

    t0 = min(ag, asx, ash); t1 = max(bg, bsx, bsh)     # common window for all rows

    print(HDR)
    print("--- standalone benchmarks (1%-units, stressed) ---")
    for thr in (0.40,):
        row("geo1.7 @1R", thr, stats([(stream('geo1.7', 0.01)[0], 1.0)], thr, t0, t1))
        row("f5/s210 1.5% @1R", thr, stats([(stream('f5/s210 1.5%', 0.01)[0], 1.0)], thr, t0, t1))
        row("TP2.0 shield @1R", thr, stats([(SH, 1.0)], thr, t0, t1))
    print("--- the kings (total 1R exposure each) ---")
    for thr in (0.0, 0.40):
        row("OLD king geo.5/s210.5", thr, stats([(G, 0.5), (S, 0.5)], thr, t0, t1))
    for thr in (0.0, 0.40):
        row("NEW king .45/.45/sh.10", thr,
            stats([(G, 0.45), (S, 0.45), (SH, 0.10)], thr, t0, t1))
