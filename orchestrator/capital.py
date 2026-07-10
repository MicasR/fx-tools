"""Capital / rebalance / circuit-breaker engine — the orchestrator brain.

Pure functions over account state (no I/O) so it is unit-testable offline. Implements the
SYSTEM_PLAN.md §2 rebalance rule for the KING single-budget model:
  - target_i = W_i * F_total * T   (ops accounts);  Main = T - sum(targets)
  - rebalance is EVENT-DRIVEN on FLAT accounts only; never touch an account with an open op
  - won (flat, balance > target)  -> sweep excess to Main
  - lost (flat, balance < target) -> Main tops up the account (capped by Main's funds)
  - swept profit parks in Main until target accounts are flat; targets recompute off live T
The EA always sizes off its ACTUAL balance, so a not-yet-topped-up account just opens smaller
(never oversized) -> transfer lag is safe.
"""
from dataclasses import dataclass, field


@dataclass
class Account:
    name: str
    balance: float = 0.0      # realized balance (what funds the next op's 1R)
    equity: float = 0.0       # balance + floating (for T / drawdown)
    is_open: bool = False     # True while an op is live (LOCKED -- no transfers)
    last_hb: float = 0.0      # epoch s of last TELEMETRY (fresh balance/equity data)
    last_ctrl: float = 0.0    # epoch s of last CONTROL poll (proof-of-life, no balance)
    dir: int = 0              # open-op direction: 1 long, -1 short, 0 flat (display only)
    stack: int = 0            # open position count (display only)
    open_r: float = 0.0       # floating P&L in R units (display only)

    def last_seen(self):
        """Most recent contact of any kind (telemetry or control) -- liveness for the dot."""
        return max(self.last_hb, self.last_ctrl)


@dataclass
class Transfer:
    src: str
    dst: str
    amount: float
    reason: str               # "sweep" (win->Main) | "topup" (Main->loss)


def total_equity(accounts):
    return sum(a.equity for a in accounts.values())


def targets(accounts, cfg, T=None):
    """Target balance per account. T defaults to live total equity."""
    if T is None:
        T = total_equity(accounts)
    tg = {}
    used = 0.0
    for a in cfg.legs:
        tg[a.account] = a.weight * cfg.f_total * T
        used += tg[a.account]
    tg[cfg.main] = T - used                  # reserve (the Main hub account, keyed by its login)
    return tg


def plan_transfers(accounts, cfg, T=None):
    """Event-driven rebalance: return the transfers to fire NOW given current state.
    Only FLAT ops-accounts are trued up; Main is the hub. Top-ups are capped by Main's
    available balance (transfer lag is safe -- EA sizes off actual balance)."""
    main = cfg.main
    if T is None:
        T = total_equity(accounts)
    tg = targets(accounts, cfg, T)
    main_bal = accounts[main].balance
    sweeps, topups = [], []
    # 1. sweep wins first (grows Main's funds available for top-ups)
    for a in cfg.legs:
        acc = accounts[a.account]
        if acc.is_open:
            continue                          # locked
        delta = acc.balance - tg[a.account]   # >0 = excess (won)
        if delta > cfg.min_transfer:
            sweeps.append(Transfer(a.account, main, round(delta, 2), "sweep"))
            main_bal += delta
    # 2. top up losers from Main (capped by available Main balance)
    for a in cfg.legs:
        acc = accounts[a.account]
        if acc.is_open:
            continue
        need = tg[a.account] - acc.balance    # >0 = short (lost)
        if need > cfg.min_transfer:
            give = min(need, max(0.0, main_bal - cfg.min_transfer))
            if give > cfg.min_transfer:
                topups.append(Transfer(main, a.account, round(give, 2), "topup"))
                main_bal -= give
    return sweeps + topups


@dataclass
class Breaker:
    peak_T: float = 0.0
    halted: bool = False      # True = command all EAs "no new ops"

    def update(self, T, cfg):
        """Track peak T; trip the halt if drawdown exceeds the threshold. Returns
        (halted, drawdown). Resume is manual (Telegram /resume -> clear())."""
        self.peak_T = max(self.peak_T, T)
        dd = 0.0 if self.peak_T <= 0 else (self.peak_T - T) / self.peak_T
        if dd > cfg.breaker_dd:
            self.halted = True
        return self.halted, dd

    def clear(self):
        self.halted = False
        self.peak_T = 0.0     # reset peak so a resumed system doesn't instantly re-trip
