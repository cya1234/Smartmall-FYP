# tools/install_weekly_task.ps1
#
# Register the Windows scheduled task that produces the weekly report.
#
# Two triggers, deliberately:
#
#   1. Tuesday 20:00      the intended time
#   2. at logon           catch-up for a machine that was off on Tuesday, which is the
#                         realistic case for a laptop. It only generates when the last
#                         report is over six days old, so it will not spam.
#
# The task runs whether or not this chat is open, which is the whole point: the report
# used to depend on someone having the assistant window in front of them.
#
#   .\tools\install_weekly_task.ps1
#   .\tools\install_weekly_task.ps1 -At 21:30
#   .\tools\install_weekly_task.ps1 -Remove

param(
  [string]$At = "20:00",
  [string]$Name = "SmartMall Weekly Report",
  [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

if ($Remove) {
  try {
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    Write-Host "  removed task: $Name"
  } catch {
    Write-Host "  no task named '$Name'"
  }
  return
}

$script = Join-Path $root 'tools\weekly_task.ps1'
if (-not (Test-Path $script)) { throw "missing $script" }

$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" `
  -WorkingDirectory $root

# Weekly Tuesday at the requested time.
$weekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At $At
# Logon catch-up.
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$logon.Delay = "PT5M"   # let the machine settle after login

$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

# StartWhenAvailable covers sleep; the logon trigger covers being switched off entirely.

Register-ScheduledTask -TaskName $Name -Action $action -Trigger @($weekly, $logon) `
  -Settings $settings -Description "SmartMall weekly report: facts from git, document into the synced cloud folder, Telegram notification." `
  -Force | Out-Null

$t = Get-ScheduledTask -TaskName $Name
Write-Host ""
Write-Host "  registered: $($t.TaskName)"
Write-Host "  state     : $($t.State)"
Write-Host "  triggers  : Tuesday $At + at logon (catch-up, minimum 6 days apart)"
Write-Host "  script    : $script"
Write-Host "  log       : $(Join-Path $root 'reports\task.log')"
Write-Host ""
Write-Host "  test it now:  powershell -NoProfile -ExecutionPolicy Bypass -File `"$script`" -DryRun"
Write-Host "  remove it  :  .\tools\install_weekly_task.ps1 -Remove"
