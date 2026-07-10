# Orchestrator / Dashboard — start · stop · restart

The **orchestrator** is one process: `uvicorn` serving the **dashboard + API on port 8800**
(`http://<vps>:8800/`). It is kept alive by a Windows **Scheduled Task** that relaunches it if it
ever stops or fails `/health`. So the golden rule:

> To **restart**, just kill the process — the supervisor brings it back in ~15 s on the latest code.
> To **stop it and keep it down**, you must **disable the task first**, otherwise it relaunches.

## What runs

| Component | Scheduled Task | Wrapper script | Notes |
|---|---|---|---|
| Orchestrator + dashboard | `CrossKing-Orchestrator` (task) | `ops/run_orchestrator.ps1` | uvicorn on **:8800**; polls `/health` every 10 s, relaunches on failure |
| Telegram bot | `CrossKing-Bot` (task) | `ops/run_bot.ps1` | alerts; idle until `.env` tokens set |
| Pull collector | **interactive process** (NOT a task) | `python -m orchestrator.collector` | MT5 telemetry; reader = T7. Must run in the interactive desktop — see below |

The two tasks auto-start at logon. **The collector cannot be a Scheduled Task** — MT5 needs the
interactive desktop, and a task (or hidden-window supervisor) runs session-isolated and fails with
`IPC initialize failed, Process create failed`. Run it in the interactive session (below).

---

## Status — is it up?

```powershell
Get-ScheduledTask -TaskName "CrossKing-*" | Select-Object TaskName, State
Get-NetTCPConnection -LocalPort 8800 -State Listen | Select-Object OwningProcess
(Invoke-WebRequest http://127.0.0.1:8800/health -UseBasicParsing).Content
```
`/health` returns JSON (`ok`, `legs_alive`, …) when the orchestrator is serving.

---

## Restart (the common case — after a code or config change)

The supervisor task must be **enabled** (it is by default). Kill the orchestrator process; the
supervisor relaunches it fresh — this also cleans up any duplicate uvicorn:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*orchestrator.app*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 16
(Invoke-WebRequest http://127.0.0.1:8800/health -UseBasicParsing).Content   # confirm it's back
```

(Only the orchestrator is touched — the filter matches `orchestrator.app`, not `orchestrator.bot`.)

---

## Stop (take it down and KEEP it down)

Disable the task **first** (or it just relaunches), then stop it and kill the process:

```powershell
Disable-ScheduledTask -TaskName CrossKing-Orchestrator
Stop-ScheduledTask    -TaskName CrossKing-Orchestrator
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*orchestrator.app*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```
Verify it's gone: `Get-NetTCPConnection -LocalPort 8800 -State Listen` returns nothing.

---

## Start (bring it back)

```powershell
Enable-ScheduledTask -TaskName CrossKing-Orchestrator
Start-ScheduledTask  -TaskName CrossKing-Orchestrator
Start-Sleep -Seconds 16
(Invoke-WebRequest http://127.0.0.1:8800/health -UseBasicParsing).Content
```

---

## Dashboard access

- **On the VPS:** `http://127.0.0.1:8800/`
- **Remote (phone/laptop):** `http://<vps-public-ip>:8800/` — requires signing in at `/login`
  (only when `DASH_USER`/`DASH_PASS` are set in `.env`; otherwise remote access is blocked and it's
  localhost-only).

---

## Bot

```powershell
# restart the bot → Stop-ScheduledTask CrossKing-Bot ; Start-ScheduledTask CrossKing-Bot
```

## Collector (interactive — MT5 needs the desktop)

Start it **in the interactive desktop session** (a plain `Start-Process` of python works; a hidden
PowerShell wrapper or a Scheduled Task does NOT — it gets a non-interactive window station):

```powershell
cd "C:\Users\Administrator\Desktop\projects\fx-tools"
$env:ORCH_URL="http://127.0.0.1:8800"
$env:MT5_READER_PATH="C:\Program Files\MetaTrader 5 - T7\terminal64.exe"   # T7/Main = reader (no EA)
$env:COLLECTOR_POLL_S="30"; $env:CK_DB="orchestrator/state.db"
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "-m","orchestrator.collector" `
  -WorkingDirectory (Get-Location) -RedirectStandardOutput "ops\collector.out" `
  -RedirectStandardError "ops\collector.err" -WindowStyle Hidden

# check it's feeding:
(Invoke-WebRequest http://127.0.0.1:8800/health -UseBasicParsing).Content   # legs_alive should climb to 7/7
# stop it:
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*orchestrator.collector*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**It does not auto-start after a reboot** — relaunch it with the block above once the desktop is up
(same as the MT5 terminals, which are also interactive). Logs: `ops/collector.out` / `.err`.

Other logs: `ops/orchestrator.out` / `.err`, `ops/bot.log`.

---

## First-time install / re-register the tasks

```powershell
powershell -ExecutionPolicy Bypass -File ops\install_services.ps1   # registers all three tasks
Start-ScheduledTask -TaskName CrossKing-Orchestrator
```

## Gotchas

- **Killing uvicorn without disabling the task = instant relaunch.** That's *by design* (a restart);
  it's only a problem if you meant to stop it — then disable the task first.
- If `/health` shows the **old roster** (strategy-name legs like `PD3_*`) after a code update, the
  process didn't restart — run the **Restart** block above so it re-imports `config.py`.
- A full restart re-reads `orchestrator/state.db` settings + the `legs` registry; nothing is lost.
