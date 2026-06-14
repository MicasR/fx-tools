import io, re, os, csv
LOG = r"C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06\Tester\logs\20260614.log"
OUT = "out/ealog"; os.makedirs(OUT, exist_ok=True)
re_init  = re.compile(r"\[CrossKing:(\w+)\] init  sym")
re_open  = re.compile(r"\[CrossKing:(\w+)\] OP OPEN dir=(-?\d+) e0=([\d.]+) R=([\d.]+) E0=([\d.]+)")
re_add   = re.compile(r"\[CrossKing:(\w+)\] ADD (?:#\d+ )?lot=([\d.]+) in (\d+) order.*?@~([\d.]+)  depth->(\d+)")
re_close = re.compile(r"\[CrossKing:(\w+)\] OP CLOSE  R=(-?[\d.]+)  bal=([\d.]+)")

segments = []   # list of (leg, ops)
cur_seg = None; cur_op = None
with io.open(LOG, "r", encoding="utf-16") as f:
    for line in f:
        if "CrossKing" not in line: continue
        mi = re_init.search(line)
        if mi:
            cur_seg = dict(leg=mi.group(1), ops=[]); segments.append(cur_seg); cur_op=None; continue
        mo = re_open.search(line)
        if mo:
            cur_op = dict(dir=int(mo.group(2)), e0=float(mo.group(3)), r0=float(mo.group(4)),
                          E0=float(mo.group(5)), adds=[], depth=1); continue
        ma = re_add.search(line)
        if ma and cur_op is not None:
            cur_op["adds"].append((float(ma.group(2)),int(ma.group(3)),float(ma.group(4))))
            cur_op["depth"]=int(ma.group(5)); continue
        mc = re_close.search(line)
        if mc and cur_op is not None and cur_seg is not None:
            cur_op["R"]=float(mc.group(2)); cur_seg["ops"].append(cur_op); cur_op=None

# last segment per leg
last = {}
for s in segments:
    if s["ops"]: last[s["leg"]] = s
print(f"total segments={len(segments)}  legs={list(last.keys())}")
for leg in ["GoldGeo17","GoldS210","GoldShield","BtcGF","BtcPG","BtcShield"]:
    s = last.get(leg)
    if not s: print(f"{leg}: no run"); continue
    ops=s["ops"]; R=[o["R"] for o in ops]
    with open(f"{OUT}/{leg}.csv","w",newline="") as fo:
        w=csv.writer(fo); w.writerow(["op","dir","e0","r0","E0","R","depth","add_lots"])
        for i,o in enumerate(ops):
            lots=";".join(f"{a[0]:.2f}@{a[2]:.2f}" for a in o["adds"])
            w.writerow([i,o["dir"],f'{o["e0"]:.5f}',f'{o["r0"]:.5f}',f'{o["E0"]:.2f}',f'{o["R"]:.3f}',o["depth"],lots])
    print(f"{leg:<11} ops={len(ops):>4} totR={sum(R):>7.1f} win%={100*sum(1 for r in R if r>0)/len(R):>5.1f} "
          f"avgDepth={sum(o['depth'] for o in ops)/len(ops):>4.2f} maxR={max(R):>6.2f} maxDepth={max(o['depth'] for o in ops)}")
