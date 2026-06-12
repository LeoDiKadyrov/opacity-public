# Resume the OF-3 staged re-batch (N=81 stage) after a pause.
# of3_rebatch.py has skip-existing logic (t0_source IS NOT NULL per demo) --
# already-completed donk demos auto-skip. Safe to run after any pause point.
#
# Idempotent: if a driver process is already running, the new one starts
# alongside (usually not what you want -- check first).

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Write-Host "=== Checking for existing of3_rebatch.py processes ==="
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "of3_rebatch\.py" } |
    Select-Object ProcessId, CommandLine

if ($existing) {
    Write-Host "WARNING: existing of3_rebatch.py process(es) found:"
    $existing | Format-Table -Wrap
    Write-Host "Continuing anyway will spawn a parallel run -- usually NOT what you want."
    Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "=== Launching driver (stage 81, detached) ==="
$driver = Start-Process -WindowStyle Hidden -FilePath python `
    -ArgumentList "of3_rebatch.py", "--stage", "81", "--db", "analytics.db" `
    -RedirectStandardOutput "of3_rebatch.stdout.log" `
    -RedirectStandardError "of3_rebatch.stderr.log" `
    -PassThru
Write-Host "Driver PID: $($driver.Id)"

Write-Host ""
Write-Host "Detached. Monitor with:"
Write-Host "  Get-Content of3_rebatch.log -Tail 5 -Wait"
Write-Host ""
Write-Host "To pause: stop the python.exe process matching 'of3_rebatch.py' via"
Write-Host "  Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { `$_.CommandLine -match 'of3_rebatch' } | Stop-Process"
