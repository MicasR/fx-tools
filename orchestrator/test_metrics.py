"""Unit test for metrics.compute — backtest-grade stats over a hand-checked op fixture.
Run: python -m orchestrator.test_metrics  (from repo root)."""
from orchestrator.metrics import compute

P = []
def chk(n, c): P.append(c); print(f"  [{'PASS' if c else 'FAIL'}] {n}")

# fixture: 6 ops, two legs. R-stream A: +2,-1,+3,-1 ; B: +1,-2
ops = [dict(account="A", realized_r=2.0), dict(account="A", realized_r=-1.0),
       dict(account="B", realized_r=1.0), dict(account="A", realized_r=3.0),
       dict(account="B", realized_r=-2.0), dict(account="A", realized_r=-1.0)]
r = compute(ops)
c = r["combined"]

# combined: 6 trades, net = 2-1+1+3-2-1 = 2; wins=3 (2,1,3), losses=3 (-1,-2,-1)
chk("trades", c["trades"] == 6)
chk("net_r", abs(c["net_r"] - 2.0) < 1e-9)
chk("wins/losses", c["wins"] == 3 and c["losses"] == 3)
chk("win_rate", abs(c["win_rate"] - 0.5) < 1e-9)
# gross_win=6, gross_loss=-4 -> PF=1.5 ; expectancy=2/6
chk("gross_win/loss", abs(c["gross_win_r"] - 6.0) < 1e-9 and abs(c["gross_loss_r"] + 4.0) < 1e-9)
chk("profit_factor", abs(c["profit_factor"] - 1.5) < 1e-9)
chk("expectancy", abs(c["expectancy_r"] - 2/6) < 1e-3)
chk("largest win/loss", c["largest_win_r"] == 3.0 and c["largest_loss_r"] == -2.0)
# cumulative: 2,1,2,5,3,2 -> peak 5, valley after = 2 -> max_dd 3 ; recovery = net/dd = 2/3
chk("max_dd_r", abs(c["max_dd_r"] - 3.0) < 1e-9)
chk("recovery_factor", abs(c["recovery_factor"] - 2/3) < 1e-3)
# consecutive in 2,-1,1,3,-2,-1: wins 1 then 3 are adjacent -> win run = 2 ; loss run = 2 (-2,-1)
chk("max_consec_wins", c["max_consec_wins"] == 2)
chk("max_consec_losses", c["max_consec_losses"] == 2)

# per-leg A: +2,-1,+3,-1 -> net 3, wins 2 losses 2
a = r["per_leg"]["A"]
chk("per_leg A net", abs(a["net_r"] - 3.0) < 1e-9 and a["trades"] == 4)
chk("per_leg B present", abs(r["per_leg"]["B"]["net_r"] + 1.0) < 1e-9)

# empty -> safe zeros
e = compute([])["combined"]
chk("empty trades=0, profit_factor None", e["trades"] == 0 and e["profit_factor"] is None)

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
