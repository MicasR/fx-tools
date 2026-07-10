"""Orchestrator config — the live roster is a DASHBOARD-MANAGED REGISTRY (SQLite `legs` table),
not hardcoded here. Legs are keyed by MT5 account LOGIN (immutable); the strategy running on an
account is just a swappable label. Register / remove / reweight happen at runtime — no restart.

Capital model (unchanged):
  T          = total equity across all accounts (ops + reserve)
  F_total    = share of T distributed to ops accounts ("aggression dial")
  per-leg 1R = target balance = W_i * F_total * T     (W_i sum to 1)
  reserve    = T * (1 - F_total)   (the Main hub account)

SEED_LEGS is the FIRST-RUN seed: it populates an empty registry, and is the default roster for
unit tests that build Config() without a DB. Once the registry has rows it is the sole source of
truth — edit it from the war room, not here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Leg:
    account: str        # MT5 account login — the immutable leg identity
    strategy: str       # descriptive label (current preset/EA); swappable, NOT an identity
    symbol: str
    weight: float       # capital-allocation weight (renormalized to sum 1 at load)
    cents: bool = True  # account denominated in US cents (USC); 100 USC = 1 USD
    tn: str = ""        # terminal slot label (T1..T7) for display + process control
    server: str = ""    # broker server (the collector's mt5.login target)
    terminal_path: str = ""   # terminal64.exe install path (open/close from the dashboard)


# First-run seed / test default. login == leg identity; ops weights renormalized in _set_legs.
# The 6 ops accounts are USC (cent) accounts; the reserve (role='main') is a USD account.
SEED_LEGS = [
    dict(login="161611609", tn="T1", server="Exness-MT5Real21", role="ops",  weight=0.33, strategy="XAU_H4_align",   symbol="XAUUSDc", cents=True,  terminal_path=r"C:\Program Files\MetaTrader 5 - T1\terminal64.exe"),
    dict(login="161611606", tn="T2", server="Exness-MT5Real21", role="ops",  weight=0.31, strategy="XAU_H4_engulf",  symbol="XAUUSDc", cents=True,  terminal_path=r"C:\Program Files\MetaTrader 5 - T2\terminal64.exe"),
    dict(login="161611603", tn="T3", server="Exness-MT5Real21", role="ops",  weight=0.16, strategy="BTC_wh_shield",  symbol="BTCUSDc", cents=True,  terminal_path=r"C:\Program Files\MetaTrader 5 - T3\terminal64.exe"),
    dict(login="161611597", tn="T4", server="Exness-MT5Real21", role="ops",  weight=0.10, strategy="XAU_H4_keltner", symbol="XAUUSDc", cents=True,  terminal_path=r"C:\Program Files\MetaTrader 5 - T4\terminal64.exe"),
    dict(login="161611593", tn="T5", server="Exness-MT5Real21", role="ops",  weight=0.06, strategy="XAU_H1_don55",   symbol="XAUUSDc", cents=True,  terminal_path=r"C:\Program Files\MetaTrader 5 - T5\terminal64.exe"),
    dict(login="161557528", tn="T6", server="Exness-MT5Real21", role="ops",  weight=0.04, strategy="XAU_H1_keltner", symbol="XAUUSDc", cents=True,  terminal_path=r"C:\Program Files\MetaTrader 5 - T6\terminal64.exe"),
    dict(login="408962391", tn="T7", server="Exness-MT5Real10", role="main", weight=0.0,  strategy="",               symbol="",        cents=False, terminal_path=r"C:\Program Files\MetaTrader 5 - T7\terminal64.exe"),
]


class Config:
    def __init__(self, f_total=1.0, breaker_dd=0.30, min_transfer=0.50,
                 heartbeat_timeout_s=300, start_capital=0.0):
        self._set_legs(SEED_LEGS)           # default roster (overridden by load_registry(db))
        self.f_total = f_total              # ops share of T (1.0 = spec cent topology)
        self.breaker_dd = breaker_dd        # halt-new-ops DD threshold
        self.min_transfer = min_transfer    # don't emit a transfer smaller than this ($)
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.start_capital = start_capital  # total deposited; baseline for $ profit (0 = unset)

    # ---- roster (registry-driven) ----------------------------------------------------------
    def _set_legs(self, rows):
        """(Re)build the in-memory roster from registry rows (list of dicts). Splits ops vs the
        reserve (role='main'), renormalizes enabled-ops weights to sum 1, indexes metadata by login."""
        enabled = [r for r in rows if int(r.get("enabled", 1))]
        ops = [r for r in enabled if r.get("role", "ops") != "main"]
        mains = [r for r in enabled if r.get("role") == "main"]
        s = sum(float(r.get("weight", 0.0)) for r in ops) or 1.0
        self.legs = [Leg(account=str(r["login"]), strategy=r.get("strategy") or "",
                         symbol=r.get("symbol") or "", weight=float(r.get("weight", 0.0)) / s,
                         cents=bool(int(r.get("cents", 1))), tn=r.get("tn") or "",
                         server=r.get("server") or "", terminal_path=r.get("terminal_path") or "")
                     for r in ops]
        self.main = str(mains[0]["login"]) if mains else "Main"
        self._registry = {str(r["login"]): dict(r) for r in rows}
        self.accounts = [l.account for l in self.legs] + [self.main]
        self.cent_accounts = {l.account for l in self.legs if l.cents}
        if int(self._registry.get(self.main, {}).get("cents", 0)):
            self.cent_accounts.add(self.main)

    def load_registry(self, db):
        """Load the authoritative roster from the DB registry, seeding it on first run."""
        db.seed_legs(SEED_LEGS)
        self._set_legs(db.legs_all())

    def weight(self, account):
        for l in self.legs:
            if l.account == account:
                return l.weight
        return None                          # reserve has no weight

    def terminal(self, account):
        """Registry metadata for `account` (login): tn, server, strategy, terminal path — or None."""
        r = self._registry.get(str(account))
        if not r:
            return None
        return dict(tn=r.get("tn") or "", login=str(account), server=r.get("server") or "",
                    strategy=r.get("strategy") or "", role=r.get("role") or "ops",
                    chart=r.get("symbol") or "", terminal_path=r.get("terminal_path") or "",
                    currency="USC" if int(r.get("cents", 0)) else "USD")

    def apply_overrides(self, d):
        """Overlay persisted/owner scalar dials (and legacy weight_<login> overrides) onto the live
        config. Weights primarily live in the registry now; a weight_<login> override still adjusts a
        current leg if present. Mutates in place so the running brain picks the change up immediately."""
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
                self.legs = [Leg(l.account, l.strategy, l.symbol, raw[l.account] / s, l.cents,
                                 l.tn, l.server, l.terminal_path) for l in self.legs]

    def to_usd(self, account, value):
        """Normalize a leg's native-currency amount to USD. Cent (USC) accounts report in cents,
        so divide by 100; USD accounts (reserve) pass through. Single point of truth."""
        return value / 100.0 if account in self.cent_accounts else value


DEFAULT = Config()
