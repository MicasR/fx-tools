"""Orchestrator config — single source of truth for the KING deployment.

Capital model (KING = GROWTH-6 weight-opt, single cross-instrument split):
  T          = total equity across all accounts (6 ops + Main)
  F_total    = total risk budget = sum of per-leg risk fractions = "max concurrent" dial
  per-leg 1R = target balance = W_i * F_total * T     (W_i sum to 1, the PD3 weights)
  Main       = reserve = T - sum(targets) = T * (1 - F_total)

F_total is the deployment dial:
  ~0.054 (5.4%)  -> the 24%-DD design point (research operating point)
  hot shakedown  -> set higher deliberately (mechanics test, not P&L); see SYSTEM_PLAN D.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Leg:
    account: str       # ops-account id / MT5 login alias
    preset: str        # PD3_*.set
    symbol: str
    weight: float      # KING capital-allocation weight (renormalized to sum 1 at load)
    cents: bool = True # account is denominated in US cents (USC); 100 USC = 1 USD


# KING roster + weights (PD3_KING_manifest.md). account id == the EA's InpLegName (the EA
# only knows that; telemetry/control key on it). Weights renormalized in CONFIG below.
# The 6 ops accounts are USC (cent) accounts; Main is a USD account. The EA reports each
# account's native balance/equity, so cent legs are normalized to USD at ingest (see Config.to_usd).
_RAW_LEGS = [
    Leg("PD3_BtcTrail_1", "PD3_BtcTrail_1", "BTCUSDc", 0.338),
    Leg("PD3_GoldGeo_0",  "PD3_GoldGeo_0",  "XAUUSDc", 0.241),
    Leg("PD3_BtcTrail_4", "PD3_BtcTrail_4", "BTCUSDc", 0.161),
    Leg("PD3_BtcNb_2",    "PD3_BtcNb_2",    "BTCUSDc", 0.105),
    Leg("PD3_BtcPin_5",   "PD3_BtcPin_5",   "BTCUSDc", 0.084),
    Leg("PD3_GoldGeo_3",  "PD3_GoldGeo_3",  "XAUUSDc", 0.070),
]
MAIN = "Main"          # the Main reporter EA's InpLegName (USD account)


class Config:
    def __init__(self, f_total=0.054, breaker_dd=0.35, min_transfer=0.50,
                 heartbeat_timeout_s=300):
        s = sum(l.weight for l in _RAW_LEGS)
        self.legs = [Leg(l.account, l.preset, l.symbol, l.weight / s, l.cents) for l in _RAW_LEGS]
        self.accounts = [l.account for l in self.legs] + [MAIN]
        self.cent_accounts = {l.account for l in self.legs if l.cents}   # USC accounts (÷100 -> USD)
        self.f_total = f_total              # total risk budget (the DD dial)
        self.breaker_dd = breaker_dd        # halt-new-ops drawdown threshold (35% shakedown / 80% live)
        self.min_transfer = min_transfer    # don't emit a transfer smaller than this ($)
        self.heartbeat_timeout_s = heartbeat_timeout_s

    def weight(self, account):
        for l in self.legs:
            if l.account == account:
                return l.weight
        return None                          # Main has no weight (it's the reserve)

    def to_usd(self, account, value):
        """Normalize a leg's native-currency amount to USD. Cent (USC) accounts report in
        cents, so divide by 100; USD accounts (Main) pass through. Single point of truth so
        all downstream math + display is in USD (no mixed-unit summation)."""
        return value / 100.0 if account in self.cent_accounts else value


# Shakedown deployment (Phase D, DEPLOYMENT_GUIDE §6/§10): hot f_total for a mechanics test,
# breaker armed at 35% DD. Switch to f_total≈0.054 / breaker_dd=0.80 for the $1000 live phase.
DEFAULT = Config(f_total=0.25, breaker_dd=0.35, min_transfer=0.50)
