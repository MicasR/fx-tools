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
