"""SQLite persistence — account state, telemetry history, op audit, transfer audit, events.
Append-only audit tables (immutable reconciliation); a single accounts row per account kept
current. WAL mode for concurrent ingest+dashboard reads."""
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  name TEXT PRIMARY KEY, balance REAL, equity REAL, is_open INTEGER, last_hb REAL
);
CREATE TABLE IF NOT EXISTS telemetry (          -- every heartbeat/state push (history)
  id INTEGER PRIMARY KEY, ts REAL, account TEXT, symbol TEXT, balance REAL, equity REAL,
  is_open INTEGER, dir INTEGER, stack INTEGER, open_r REAL, ml_sl REAL, ver TEXT
);
CREATE TABLE IF NOT EXISTS ops (                -- immutable: one row per CLOSED op (live R-stream)
  id INTEGER PRIMARY KEY, ts REAL, account TEXT, symbol TEXT, realized_r REAL,
  positions INTEGER, reason TEXT, open_time REAL, close_time REAL
);
CREATE TABLE IF NOT EXISTS transfers (          -- immutable: every rebalance instruction + confirm
  id INTEGER PRIMARY KEY, ts REAL, src TEXT, dst TEXT, amount REAL, reason TEXT,
  status TEXT, confirmed_ts REAL
);
CREATE TABLE IF NOT EXISTS events (             -- ops/transfers/alerts/breaker log
  id INTEGER PRIMARY KEY, ts REAL, kind TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS settings (           -- live, owner-tunable config overrides (war room)
  key TEXT PRIMARY KEY, value REAL, updated_ts REAL
);
CREATE TABLE IF NOT EXISTS legs (               -- roster registry (login-keyed); dashboard-managed
  login TEXT PRIMARY KEY, tn TEXT, server TEXT, role TEXT, weight REAL,
  strategy TEXT, symbol TEXT, cents INTEGER, enabled INTEGER,
  terminal_path TEXT, added_ts REAL
);
"""


class DB:
    def __init__(self, path="orchestrator/state.db"):
        self.cx = sqlite3.connect(path, check_same_thread=False)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.executescript(SCHEMA)
        self.cx.commit()

    def upsert_account(self, name, balance, equity, is_open, last_hb):
        self.cx.execute(
            "INSERT INTO accounts(name,balance,equity,is_open,last_hb) VALUES(?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET balance=?,equity=?,is_open=?,last_hb=?",
            (name, balance, equity, int(is_open), last_hb, balance, equity, int(is_open), last_hb))
        self.cx.commit()

    def add_telemetry(self, **k):
        cols = "ts account symbol balance equity is_open dir stack open_r ml_sl ver".split()
        self.cx.execute(f"INSERT INTO telemetry({','.join(cols)}) VALUES({','.join('?'*len(cols))})",
                        [k.get(c) for c in cols]); self.cx.commit()

    def add_op(self, **k):
        cols = "ts account symbol realized_r positions reason open_time close_time".split()
        self.cx.execute(f"INSERT INTO ops({','.join(cols)}) VALUES({','.join('?'*len(cols))})",
                        [k.get(c) for c in cols]); self.cx.commit()

    def add_transfer(self, src, dst, amount, reason, status="pending"):
        cur = self.cx.execute(
            "INSERT INTO transfers(ts,src,dst,amount,reason,status) VALUES(?,?,?,?,?,?)",
            (time.time(), src, dst, amount, reason, status)); self.cx.commit()
        return cur.lastrowid

    def confirm_transfer(self, tid):
        self.cx.execute("UPDATE transfers SET status='confirmed',confirmed_ts=? WHERE id=?",
                        (time.time(), tid)); self.cx.commit()

    def log(self, kind, detail):
        self.cx.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",
                        (time.time(), kind, detail)); self.cx.commit()

    def accounts(self):
        return {r["name"]: dict(r) for r in self.cx.execute("SELECT * FROM accounts")}

    def pending_transfers(self):
        return [dict(r) for r in self.cx.execute("SELECT * FROM transfers WHERE status='pending'")]

    def op_rstream(self):
        return [dict(r) for r in self.cx.execute(
            "SELECT account,realized_r,close_time FROM ops ORDER BY close_time")]

    def ops_all(self):
        """Full op rows ordered by close_time — for the backtest-grade metrics report."""
        return [dict(r) for r in self.cx.execute("SELECT * FROM ops ORDER BY close_time, id")]

    def events_since(self, since=0.0, limit=200):
        """Recent event-log rows after `since` (epoch s), newest first — for the in-page feed."""
        return [dict(r) for r in self.cx.execute(
            "SELECT id,ts,kind,detail FROM events WHERE ts > ? ORDER BY ts DESC, id DESC LIMIT ?",
            (since, limit))]

    def get_settings(self):
        """All persisted config overrides as {key: value}."""
        return {r["key"]: r["value"] for r in self.cx.execute("SELECT key,value FROM settings")}

    def set_setting(self, key, value):
        self.cx.execute(
            "INSERT INTO settings(key,value,updated_ts) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=?,updated_ts=?",
            (key, value, time.time(), value, time.time())); self.cx.commit()

    # ---- roster registry (login-keyed; the dashboard-managed source of truth) -----------------
    def legs_all(self):
        """All registry rows (ops + reserve, enabled + disabled), reserve last, biggest weight first."""
        return [dict(r) for r in self.cx.execute(
            "SELECT * FROM legs ORDER BY (role='main'), weight DESC, tn")]

    def leg_upsert(self, login, tn="", server="", role="ops", weight=0.0, strategy="",
                   symbol="", cents=1, enabled=1, terminal_path=""):
        """Insert or update one registry row. added_ts is set once (kept on update)."""
        self.cx.execute(
            "INSERT INTO legs(login,tn,server,role,weight,strategy,symbol,cents,enabled,"
            "terminal_path,added_ts) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(login) DO UPDATE SET tn=excluded.tn,server=excluded.server,"
            "role=excluded.role,weight=excluded.weight,strategy=excluded.strategy,"
            "symbol=excluded.symbol,cents=excluded.cents,enabled=excluded.enabled,"
            "terminal_path=excluded.terminal_path",
            (str(login), tn, server, role, float(weight), strategy, symbol,
             int(bool(cents)), int(bool(enabled)), terminal_path, time.time())); self.cx.commit()

    def leg_remove(self, login):
        self.cx.execute("DELETE FROM legs WHERE login=?", (str(login),)); self.cx.commit()

    def leg_set_weight(self, login, weight):
        self.cx.execute("UPDATE legs SET weight=? WHERE login=?", (float(weight), str(login)))
        self.cx.commit()

    def leg_set_enabled(self, login, enabled):
        self.cx.execute("UPDATE legs SET enabled=? WHERE login=?", (int(bool(enabled)), str(login)))
        self.cx.commit()

    def seed_legs(self, rows):
        """Populate the registry ONLY if empty — idempotent first-run seed."""
        if self.cx.execute("SELECT COUNT(*) FROM legs").fetchone()[0]:
            return
        for r in rows:
            self.leg_upsert(r["login"], tn=r.get("tn", ""), server=r.get("server", ""),
                            role=r.get("role", "ops"), weight=r.get("weight", 0.0),
                            strategy=r.get("strategy", ""), symbol=r.get("symbol", ""),
                            cents=r.get("cents", True), enabled=r.get("enabled", True),
                            terminal_path=r.get("terminal_path", ""))
