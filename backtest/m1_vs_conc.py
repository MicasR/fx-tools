"""Side-by-side: bar engine (conc_engine) vs M1-intrabar engine vs tester TRUTH,
all NBP-clamped. Isolates what the M1 stepping changed relative to the bar engine
(which the FINDINGS recorded against the tester)."""
import numpy as np
from conc_engine import run_tf_conc
from m1_engine import run_m1_conc
from tester_truth import nbp
from m1_validate import LEGS, TRUTH


def tot(res):
    return float(nbp([o[2] for o in res]).sum()), len(res)


print(f"{'leg':<12}{'bar':>9}{'M1':>9}{'truth':>8}   {'barΔ%':>7}{'M1Δ%':>7}   {'barOps':>7}{'M1Ops':>6}")
for name, sym, tf, cfg in LEGS:
    rb, *_ = run_tf_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
    rm, *_ = run_m1_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
    tb, nb = tot(rb); tm, nm = tot(rm); tr = TRUTH[name][0]
    print(f"{name:<12}{tb:>9.1f}{tm:>9.1f}{tr:>8.1f}   "
          f"{100*(tb-tr)/tr:>+6.1f}%{100*(tm-tr)/tr:>+6.1f}%   {nb:>7}{nm:>6}")
print("\n  bar = conc_engine (mgmt-TF bars), M1 = m1_engine (M1 intrabar), truth = NBP tester.")
