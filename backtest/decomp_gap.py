import csv, json, numpy as np
def ea(leg):
    out=[]
    with open(f"out/ealog/{leg}.csv") as f:
        for r in csv.DictReader(f):
            out.append(dict(e0=float(r["e0"]),dir=int(r["dir"]),R=max(float(r["R"]),-1.0)))  # NBP
    return out
def py(leg):
    out=[]
    with open(f"out/shadow/{leg}.csv") as f:
        for r in csv.DictReader(f):
            out.append(dict(e0=float(r["e0"]),dir=int(r["dir"]),R=max(float(r["R_raw"]),-1.0)))  # oracle already floors at -1
    return out
print(f"{'leg':<11}{'PYtot':>7}{'EAtot':>7}{'gap':>7} | {'matchN':>7}{'mGapR':>7}{'pyOnlyN':>8}{'pyOnlyR':>8}{'eaOnlyN':>8}{'eaOnlyR':>8}")
for leg in ["GoldGeo17","GoldS210","GoldShield","BtcGF","BtcPG","BtcShield"]:
    E=ea(leg); P=py(leg); tol=0.001
    i=j=0; mN=0; mgap=0.0; pyonly=[]; eaonly=[]
    used_e=set()
    # greedy sequential align with small lookahead
    while i<len(E) and j<len(P):
        a,p=E[i],P[j]
        if abs(a["e0"]-p["e0"])/p["e0"]<tol and a["dir"]==p["dir"]:
            mN+=1; mgap+=p["R"]-a["R"]; i+=1; j+=1
        else:
            adv=None
            for dj in range(1,5):
                if j+dj<len(P) and abs(a["e0"]-P[j+dj]["e0"])/a["e0"]<tol and a["dir"]==P[j+dj]["dir"]: adv=("py",dj);break
            for di in range(1,5):
                if i+di<len(E) and abs(E[i+di]["e0"]-p["e0"])/p["e0"]<tol and E[i+di]["dir"]==p["dir"]:
                    if adv is None or di<adv[1]: adv=("ea",di)
                    break
            if adv is None: eaonly.append(a["R"]); pyonly.append(p["R"]); i+=1; j+=1
            elif adv[0]=="py":
                for d in range(adv[1]): pyonly.append(P[j+d]["R"])
                j+=adv[1]
            else:
                for d in range(adv[1]): eaonly.append(E[i+d]["R"])
                i+=adv[1]
    while j<len(P): pyonly.append(P[j]["R"]); j+=1
    while i<len(E): eaonly.append(E[i]["R"]); i+=1
    PYtot=sum(o["R"] for o in P); EAtot=sum(o["R"] for o in E)
    print(f"{leg:<11}{PYtot:>7.1f}{EAtot:>7.1f}{PYtot-EAtot:>7.1f} | {mN:>7}{mgap:>7.1f}{len(pyonly):>8}{sum(pyonly):>8.1f}{len(eaonly):>8}{sum(eaonly):>8.1f}")
print("\n gap = mGapR + pyOnlyR - eaOnlyR.  mGapR=matched-op R diff (PY-EA); pyOnly=ops PY took & EA didn't; eaOnly=ops EA took & PY didn't.")
