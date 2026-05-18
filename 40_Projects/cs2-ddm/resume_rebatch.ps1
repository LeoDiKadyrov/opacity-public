# Resume the full corpus rebatch + watcher after a pause.
# Driver has skip-existing logic -- already-completed demos auto-skip.
# Safe to run after any pause point (clean or mid-demo).
#
# Idempotent: if either process already running, the new one starts alongside.
# Typically you should pause first via .\pause_rebatch.ps1 before resuming.

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Write-Host "=== Checking for existing processes ==="
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {
        $_.CommandLine -match "full_corpus_rebatch\.py" -or
        $_.CommandLine -match "full_corpus_watcher\.py"
    } |
    Select-Object ProcessId, CommandLine

if ($existing) {
    Write-Host "WARNING: existing processes found:"
    $existing | Format-Table -Wrap
    Write-Host "Run .\pause_rebatch.ps1 first if you want to restart from clean state."
    Write-Host "Continuing anyway (will spawn parallel -- usually NOT what you want)..."
    Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "=== Launching driver ==="
$driver = Start-Process -WindowStyle Hidden -FilePath python `
    -ArgumentList "full_corpus_rebatch.py" `
    -RedirectStandardOutput "full_corpus_rebatch.stdout.log" `
    -RedirectStandardError "full_corpus_rebatch.stderr.log" `
    -PassThru
Write-Host "Driver PID: $($driver.Id)"

Start-Sleep -Seconds 2

Write-Host "=== Launching watcher ==="
$watcher = Start-Process -WindowStyle Hidden -FilePath python `
    -ArgumentList "full_corpus_watcher.py" `
    -RedirectStandardOutput "full_corpus_watcher.stdout.log" `
    -RedirectStandardError "full_corpus_watcher.stderr.log" `
    -PassThru
Write-Host "Watcher PID: $($watcher.Id)"

Write-Host ""
Write-Host "Both processes detached. Monitor:"
Write-Host "  Get-Content rebatch_full.log -Tail 5 -Wait"
Write-Host ""
Write-Host "Pause via: .\pause_rebatch.ps1"
