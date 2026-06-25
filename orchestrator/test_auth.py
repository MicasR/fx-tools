"""Auth/session gate test — exercises the login-cookie flow with the gate ACTIVE (no CK_TEST).
TestClient connects as a non-local host, i.e. the remote/phone case. Uses a throwaway DB.
Run: python -m orchestrator.test_auth  (from repo root)."""
import os
os.environ.pop("CK_TEST", None)                       # gate must be active
os.environ["DASH_USER"] = "alice"
os.environ["DASH_PASS"] = "s3cret"
DBP = os.environ.setdefault("CK_DB", "orchestrator/test_auth.db")
for p in (DBP, DBP + "-wal", DBP + "-shm"):
    if os.path.exists(p):
        os.remove(p)

import base64
from fastapi.testclient import TestClient
from orchestrator import app as A

c = TestClient(A.app)
HTML = {"accept": "text/html,application/xhtml+xml"}
P = []
def chk(n, cond): P.append(cond); print(f"  [{'PASS' if cond else 'FAIL'}] {n}")

# --- before login ---
chk("remote m2m /telemetry -> 404 (hidden)", c.get("/telemetry", params={"account": "Main"}).status_code == 404)
chk("no session, XHR /status -> 401", c.get("/status").status_code == 401)
chk("no WWW-Authenticate header (no Basic popup)", "WWW-Authenticate" not in c.get("/status").headers)
red = c.get("/", headers=HTML, follow_redirects=False)
chk("browser GET / -> 302", red.status_code == 302)
chk("  ...redirects to /login", red.headers.get("location") == "/login")
chk("/login page is public (200)", c.get("/login").status_code == 200)
chk("bad credentials -> 401", c.post("/login", json={"username": "alice", "password": "nope"}).status_code == 401)

# --- login sets the session cookie ---
r = c.post("/login", json={"username": "alice", "password": "s3cret"})
chk("good credentials -> 200", r.status_code == 200)
chk("sets ck_session cookie", "ck_session" in c.cookies)
chk("session -> /status 200", c.get("/status").status_code == 200)
chk("session -> / serves dashboard", (lambda x: x.status_code == 200 and "crossking" in x.text.lower())(c.get("/", headers=HTML)))

# --- logout invalidates ---
c.post("/logout")
chk("after logout /status -> 401", c.get("/status").status_code == 401)

# --- Basic auth still works for API/curl (fresh client, no cookie) ---
c2 = TestClient(A.app)
b = base64.b64encode(b"alice:s3cret").decode()
chk("Basic auth -> /status 200 (API path)", c2.get("/status", headers={"Authorization": "Basic " + b}).status_code == 200)

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
