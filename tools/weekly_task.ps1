# tools/weekly_task.ps1
#
# Entry point for the Windows scheduled task. Two triggers call it:
#
#   Tuesday 20:00      -> generate this week's report
#   at logon           -> "catch up": only generates if the last report is over 6 days
#                         old, which covers the case where the machine was off on
#                         Tuesday (the normal case for a student laptop)
#
# Everything else (facts, document, cloud copy, Telegram) is done by
# tools/build_weekly_report.py. This wrapper only exists because the Task Scheduler
# needs a stable, argument-free command with a log file.
#
#   .\tools\weekly_task.ps1              # normal weekly run
#   .\tools\weekly_task.ps1 -CatchUp     # logon catch-up run
#   .\tools\weekly_task.ps1 -DryRun      # local only, no cloud, no Telegram

param(
  [switch]$CatchUp,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'reports'
$log = Join-Path $logDir 'task.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log($msg) {
  $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
  Add-Content -Path $log -Value $line -Encoding utf8
  Write-Host $line
}

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
  Write-Log "ERROR: python not found at $py"
  exit 1
}

$builder = Join-Path $root 'tools\build_weekly_report.py'
$argList = @($builder)
if ($CatchUp) { $argList += '--catch-up' }
if ($DryRun) { $argList += '--dry-run' }

Write-Log "run start (catchup=$CatchUp dryrun=$DryRun)"
try {
  $out = & $py @argList 2>&1
  foreach ($line in $out) { Write-Log ("  " + $line) }
  Write-Log "run finished ok"
  exit 0
} catch {
  Write-Log ("ERROR: " + $_.Exception.Message)
  exit 1
}
