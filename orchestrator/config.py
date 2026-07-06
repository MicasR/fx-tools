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
import json
import os
from dataclasses import dataclass

_TERMINALS_PATH = os.path.join(os.path.dirname(__file__), "terminals.json")


def _load_terminals():
    """Optional gitignored map: leg account -> {tn, role, login, broker, server, symbol}.
    Generated from terminals.xlsx by ops/gen_terminals.py (passwords excluded). Absent in dev."""
    try:
        with open(_TERMINALS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@dataclass(frozen=True)
class Leg:
    account: str       # ops-account id / MT5 login alias
    preset: str        # GymTeam_EA presets/<name>.set
    symbol: str
    weight: float      # capital-allocation weight (renormalized to sum 1 at load)
    cents: bool = True # account is denominated in US cents (USC); 100 USC = 1 USD


# TESTER-TRUE roster + thread-40 weights (TESTERTRUE_TEAM_SPEC.md). account
# id == the EA's InpLegName (the EA only knows that; telemetry/control key on
# it). Weights renormalized in CONFIG below. The 6 ops accounts are USC (cent)
# accounts; Main is a USD account. The EA reports each account's native
# balance/equity, so cent legs are normalized to USD at ingest (see Config.to_usd).
_RAW_LEGS = [
    Leg("XAU_H4_align",   "XAU_H4_align",   "XAUUSDc", 0.33),
    Leg("XAU_H4_engulf",  "XAU_H4_engulf",  "XAUUSDc", 0.31),
    Leg("BTC_wh_shield",  "BTC_wh_shield",  "BTCUSDc", 0.16),
    Leg("XAU_H4_keltner", "XAU_H4_keltner", "XAUUSDc", 0.10),
    Leg("XAU_H1_don55",   "XAU_H1_don55",   "XAUUSDc", 0.06),
    Leg("XAU_H1_keltner", "XAU_H1_keltner", "XAUUSDc", 0.04),
]
MAIN = "Main"          # the Main reporter EA's InpLegName (USD account)


class Config:
    def __init__(self, f_total=1.0, breaker_dd=0.30, min_transfer=0.50,
                 heartbeat_timeout_s=300, start_capital=0.0):
        s = sum(l.weight for l in _RAW_LEGS)
        self.legs = [Leg(l.account, l.preset, l.symbol, l.weight / s, l.cents) for l in _RAW_LEGS]
        self.accounts = [l.account for l in self.legs] + [MAIN]
        self.cent_accounts = {l.account for l in self.legs if l.cents}   # USC accounts (÷100 -> USD)
        self.f_total = f_total              # ops share of T (1.0 = spec cent topology)
        self.breaker_dd = breaker_dd        # halt-new-ops DD threshold (contract trigger #2: 30%)
        self.min_transfer = min_transfer    # don't emit a transfer smaller than this ($)
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.start_capital = start_capital  # total deposited; baseline for $ profit (0 = unset)
        self.terminals = _load_terminals()  # leg -> terminal/account metadata (for the UI)

    def weight(self, account):
        for l in self.legs:
            if l.account == account:
                return l.weight
        return None                          # Main has no weight (it's the reserve)

    def terminal(self, account):
        """Terminal/account metadata for `account` (Tn, Exness login, broker, ...) or None."""
        return self.terminals.get(account)

    def apply_overrides(self, d):
        """Overlay persisted/owner settings onto the live config. Accepts the scalar dials and
        per-leg weights as `weight_<account>`; weights are renormalized to sum 1 (preset/symbol/
        cents preserved). Mutates in place so the running brain picks the change up immediately."""
        if not d:
            return
        if "f_total" in d:             self.f_total = float(d["f_total"])
        if "breaker_dd" in d:          self.breaker_dd = float(d["breaker_dd"])
        if "min_transfer" in d:        self.min_transfer = float(d["min_transfer"])
        if "heartbeat_timeout_s" in d: self.heartbeat_timeout_s = float(d["heartbeat_timeout_s"])
        if "start_capital" in d:       self.start_capital = float(d["start_capital"])
        wkeys = {k[len("weight_"):]: float(v) for k, v in d.items() if k.startswith("weight_")}
        if wkeys:
            raw = {l.account: wkeys.get(l.account, l.weight) for l in self.legs}
            s = sum(raw.values())
            if s > 0:
                self.legs = [Leg(l.account, l.preset, l.symbol, raw[l.account] / s, l.cents)
                             for l in self.legs]

    def to_usd(self, account, value):
        """Normalize a leg's native-currency amount to USD. Cent (USC) accounts report in
        cents, so divide by 100; USD accounts (Main) pass through. Single point of truth so
        all downstream math + display is in USD (no mixed-unit summation)."""
        return value / 100.0 if account in self.cent_accounts else value


DEFAULT = Config()
