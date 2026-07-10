"""Account passwords for the collector — gitignored secrets.json, keyed by MT5 login.

Kept OUT of the DB and out of git. Never logged, never returned by any API (only a `has_password`
boolean is ever exposed). Shared by app.py (write, when an account is registered) and collector.py
(read, to log in). Path is env-overridable (CK_SECRETS) so tests never touch the real file.
"""
import json
import os


def _path():
    return os.environ.get("CK_SECRETS", os.path.join(os.path.dirname(__file__), "secrets.json"))


def load():
    """{login: password}. Ignores any non-login bookkeeping keys (e.g. a leading "_comment")."""
    try:
        with open(_path(), encoding="utf-8") as f:
            return {str(k): v for k, v in json.load(f).items() if not str(k).startswith("_")}
    except Exception:
        return {}


def has_password(login):
    return str(login) in load()


def set_password(login, password):
    """Upsert one login's password (preserving the rest). No-op on empty password."""
    if not password:
        return
    d = {}
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d[str(login)] = password
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
