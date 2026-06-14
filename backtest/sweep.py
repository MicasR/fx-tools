"""Ad-hoc §3.6 sweep driver. Edit the call, run: python sweep.py <which>."""
import sys
import opt_run as o

which = sys.argv[1] if len(sys.argv) > 1 else "s210_struct"

if which == "s210_struct":
    df = o.run_opt("s210_struct", "GoldS210",
                   opt={"step": (1.4, 0.1, 2.0), "slowP": (150, 30, 300),
                        "smaP": (3, 2, 11), "half": (0.3, 0.2, 0.7)},
                   mode=1, timeout=2400)
    print(f"passes: {len(df)}")
    print("current king (step1.7/slow210/sma5/half0.5): nbpR 157.4, 3/6 segs, 1op 57%")
    o.show(df, 20)
