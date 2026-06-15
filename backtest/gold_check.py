"""What does insisting on a GOLD-COMPOUND dancer cost? Seed the team with the best gold
stacker (GoldS210/GoldGeo17 = geofloor/proggeo) then greedy-add, vs the free 3-dancer."""
import numpy as np
import promdate as P

pool = P.load_pool(max_oneop=50)
Wm = P.W(pool)
B = 0.24


def grow(idxs):
    return P.growth_at_dd(sum(Wm[i] for i in idxs), B)[0]


def greedy_from(seed, maxn=3, max_corr=0.5):
    sel = list(seed)
    while len(sel) < maxn:
        best_i, best_g = -1, grow(sel) if sel else 1.0
        for i in range(len(pool)):
            if i in sel or any(P._corr(Wm[i], Wm[j]) > max_corr for j in sel):
                continue
            g = grow(sel + [i])
            if g > best_g + 1e-9:
                best_g, best_i = g, i
        if best_i < 0:
            break
        sel.append(best_i)
    return sel


# best gold compounder (stacker) standalone, by growth-at-DD
gold_stk = [i for i in range(len(pool)) if pool.iloc[i]["leg"] in ("GoldS210", "GoldGeo17")]
gbest = max(gold_stk, key=lambda i: P.growth_at_dd(Wm[i], B)[0])
gr = pool.iloc[gbest]
print(f"best gold compounder: {gr['leg']} sma{int(gr['smaP'])} slow{int(gr['slowP'])} "
      f"step{gr['step']:.2f} half{gr['half']:.1f}  nbpR={gr['nbpR']:.1f} segs={int(gr['segpos'])}/6 "
      f"1op={gr['oneop']:.0f}%  standalone growth@24%DD={P.growth_at_dd(Wm[gbest],B)[0]:.1f}x")

free = greedy_from([], 3)
seeded = greedy_from([gbest], 3)
print(f"\nFREE 3-dancer:   {[pool.iloc[i]['leg'] for i in free]}  -> {grow(free):.1f}x")
print(f"GOLD-SEEDED 3:   {[pool.iloc[i]['leg'] for i in seeded]}  -> {grow(seeded):.1f}x")
for i in seeded:
    r = pool.iloc[i]
    sp, _ = P.seg_robust(Wm[i])
    print(f"   {r['leg']:<11} sma{int(r['smaP'])} slow{int(r['slowP'])} step{r['step']:.2f} "
          f"tp{r['tpR']:.2f} tr{r['trailR']:.1f}  nbpR={r['nbpR']:.1f} seg={int(r['segpos'])}/6 1op={r['oneop']:.0f}%")
sp_s, segs_s = P.seg_robust(sum(Wm[i] for i in seeded))
print(f"   gold-seeded team segs {sp_s}/6  " + " ".join(f"{s:+.0f}" for s in segs_s))
print(f"\ncost of insisting on gold-compound: {100*(grow(seeded)/grow(free)-1):+.0f}% growth@24%DD")
