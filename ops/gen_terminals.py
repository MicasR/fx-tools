"""Generate orchestrator/terminals.json (gitignored) from terminals.xlsx.

The dashboard war-room labels each account/transfer as `Tn · <leg> · #<login> (Broker)` so a
rebalance instruction is executable in Exness without a lookup. This script extracts ONLY the
identity fields needed for that — terminal, role, Exness login, broker, server, chart. The
Password column is intentionally never read/written. Re-run after terminals.xlsx changes:

    .venv/Scripts/python.exe ops/gen_terminals.py
"""
import json
import os

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "terminals.xlsx")
OUT = os.path.join(ROOT, "orchestrator", "terminals.json")


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    idx = {h: i for i, h in enumerate(rows[0])}

    def cell(row, name):
        i = idx.get(name)
        return row[i] if i is not None else None

    out = {}
    for r in rows[1:]:
        if not any(r):
            continue
        preset = (cell(r, "preset") or "").strip()
        role_raw = str(cell(r, "account role") or "")
        if preset.endswith(".set"):
            acct = preset[:-4]                         # leg account == preset name
            role = "ops"
        elif role_raw.lower().startswith("main"):
            acct = "Main"                              # the reporter (never trades)
            role = "Main reporter"
        else:
            continue                                   # unknown row (e.g. dev/build box)
        login = cell(r, "login")
        out[acct] = dict(
            tn=str(cell(r, "terminal") or "").strip(),
            role=role,
            login=str(int(login)) if isinstance(login, float) else (str(login) if login else ""),
            broker=str(cell(r, "Broker") or "").strip(),
            server=str(cell(r, "Server") or "").strip(),
            chart=str(cell(r, "symbol/chart") or "").strip(),
            currency=str(cell(r, "currency") or "").strip(),
        )

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    summary = ", ".join(f"{v['tn']}={k}" for k, v in out.items())
    print(f"wrote {OUT}: {len(out)} terminals -> {summary}")


if __name__ == "__main__":
    main()
