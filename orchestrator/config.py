"""Orchestrator config — single source of truth for the TESTER-TRUE deployment.

Book: fx_gym docs/TESTERTRUE_TEAM_SPEC.md (supersedes the PD3 king — old
numbers must never be quoted). GymTeam_EA legs, whole-account ops, cent
ops-accounts for the $100 shakedown.

Capital model (unchanged):
  T          = total equity across all accounts (6 ops + Main)
  F_total    = share of T distributed to ops accounts ("aggression dial")
  per-leg 1R = target balance = W_i * F_total * T     (W_i sum to 1)
  Main       = reserve = T * (1 - F_total)

F_total for THIS book: the spec's cent topology funds the ENTIRE $100 into
the six ops accounts ($33/$31/$16/$10/$6/$4) -> F_total = 1.0 for the
shakedown AND the $10k migration (same shape). De-risking (contract
trigger #3: -50%) is done by lowering F_total, which parks half in Main.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Leg:
    account: str       # ops-account id / MT5 login alias
    preset: str        # GymTeam_EA presets/<name>.set
    symbol: str
    weight: float      # capital-allocation weight (renormalized to sum 1 at load)


# TESTER-TRUE roster + thread-40 weights (TESTERTRUE_TEAM_SPEC.md). account
# id == the EA's InpLegName (the EA only knows that; telemetry/control key
# on it). Weights renormalized in CONFIG below.
_RAW_LEGS = [
    Leg("XAU_H4_align",   "XAU_H4_align",   "XAUUSDc", 0.33),
    Leg("XAU_H4_engulf",  "XAU_H4_engulf",  "XAUUSDc", 0.31),
    Leg("BTC_wh_shield",  "BTC_wh_shield",  "BTCUSDc", 0.16),
    Leg("XAU_H4_keltner", "XAU_H4_keltner", "XAUUSDc", 0.10),
    Leg("XAU_H1_don55",   "XAU_H1_don55",   "XAUUSDc", 0.06),
    Leg("XAU_H1_keltner", "XAU_H1_keltner", "XAUUSDc", 0.04),
]
MAIN = "Main"          # the Main reporter EA's InpLegName


class Config:
    def __init__(self, f_total=1.0, breaker_dd=0.30, min_transfer=0.50,
                 heartbeat_timeout_s=300):
        s = sum(l.weight for l in _RAW_LEGS)
        self.legs = [Leg(l.account, l.preset, l.symbol, l.weight / s) for l in _RAW_LEGS]
        self.accounts = [l.account for l in self.legs] + [MAIN]
        self.f_total = f_total              # ops share of T (1.0 = spec cent topology)
        self.breaker_dd = breaker_dd        # halt-new-ops DD threshold (contract trigger #2: 30%)
        self.min_transfer = min_transfer    # don't emit a transfer smaller than this ($)
        self.heartbeat_timeout_s = heartbeat_timeout_s

    def weight(self, account):
        for l in self.legs:
            if l.account == account:
                return l.weight
        return None                          # Main has no weight (it's the reserve)


DEFAULT = Config()
