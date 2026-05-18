# Stops the full corpus rebatch + watcher gracefully.
# Identifies them by command-line match -- survives PID changes between sessions.
#
# Worker (`multi_player_analyze.py` child) is NOT killed here -- it finishes the
# current demo's player loop and exits when the parent driver is gone. This is
# the safer pause (no partial-demo work loss), at the cost of ~5-10 minutes
# waiting for the current player to finish.
#
# For an IMMEDIATE hard pause (loses current-demo partial work):
#   Stop-Process -Name python -Force   # WARNING: kills ALL python procs
#
# Use this script for the soft pause.

$ErrorActionPreference = "Stop"

Write-Host "=== Identifying processes ==="
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {
        $_.CommandLine -match "full_corpus_rebatch\.py" -or
        $_.CommandLine -match "full_corpus_watcher\.py"
    } |
    Select-Object ProcessId, CommandLine

if (-not $procs) {
    Write-Host "No driver or watcher running."
    exit 0
}

$procs | Format-Table -Wrap

Write-Host "=== Stopping ==="
foreach ($p in $procs) {
    Write-Host "Stopping PID $($p.ProcessId)..."
    Stop-Process -Id $p.ProcessId -Force
}

Start-Sleep -Seconds 2

# Note: the multi_player_analyze.py worker child may still be running.
# Let it finish naturally -- it writes the current demo's player rows
# into analytics.db and exits.
$worker = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "multi_player_analyze\.py" }

if ($worker) {
    Write-Host ""
    Write-Host "NOTE: multi_player_analyze.py worker (PID $($worker.ProcessId)) is still running."
    Write-Host "It will finish the current player's analysis (~2-5 min) then exit cleanly."
    Write-Host "Resume safely via .\resume_rebatch.ps1 after it exits (or anytime -- skip-existing handles it)."
} else {
    Write-Host ""
    Write-Host "Driver + watcher stopped. No worker running."
    Write-Host "Resume via: .\resume_rebatch.ps1"
}
