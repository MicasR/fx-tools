# Registers the orchestrator + bot as auto-start Scheduled Tasks (run at user logon, since the
# VPS auto-logs-in the interactive desktop that the MT5 terminals also need). The wrapper scripts
# (run_orchestrator.ps1 / run_bot.ps1) supervise + restart-on-crash; the task-level RestartCount
# handles the rare case the wrapper itself dies. Re-run safe (unregisters first).
# RunLevel Limited => NO elevation needed (uvicorn binds an unprivileged port, needs no admin).
# NOTE: the bot task idles until TELEGRAM_TOKEN/CHAT are set in .env.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$User = "$env:USERDOMAIN\$env:USERNAME"

function Register-CKTask($Name, $Script) {
    $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    $principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal | Out-Null
    Write-Host "registered $Name"
}

Register-CKTask "CrossKing-Orchestrator" (Join-Path $Root "ops\run_orchestrator.ps1")
Register-CKTask "CrossKing-Bot"          (Join-Path $Root "ops\run_bot.ps1")
Write-Host "done. Start now with: Start-ScheduledTask -TaskName CrossKing-Orchestrator"
