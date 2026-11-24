# tools/weekly_task.ps1
#
# Entry point for the Windows scheduled task. Two triggers call it:
#
#   Tuesday 20:00      -> generate this week's report
#   at logon           -> "catch up": only generates if the last report is over 6 days
#                         old, which covers the case where the machine was off on
#                         Tuesday (the normal case for a student laptop)
#
# Why the cloud copy and the Telegram message live here rather than in Python:
#
#   Python is denied write access to the Google Drive virtual drive, even running as the
#   logged-in user. PowerShell on the same machine, in the same folder, writes fine —
#   verified with a probe scheduled task. Inheriting that restriction means a
#   Python-spawned PowerShell is denied too, so the copy has to happen in this process,
#   which was started directly by the Task Scheduler.
#
#   .\tools\weekly_task.ps1              # normal weekly run
#   .\tools\weekly_task.ps1 -CatchUp     # logon catch-up run
#   .\tools\weekly_task.ps1 -DryRun      # generate locally, no cloud copy, no Telegram

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
if (-not (Test-Path $py)) { Write-Log "ERROR: python not found at $py"; exit 1 }

# ---- config (may legitimately be absent) ---------------------------------
$configPath = Join-Path $root '.report\report.json'
$cfg = $null
if (Test-Path $configPath) {
  try { $cfg = Get-Content $configPath -Raw -Encoding utf8 | ConvertFrom-Json }
  catch { Write-Log "WARNING: report.json is not valid JSON — ignoring it" }
}
$token = if ($cfg -and $cfg.telegram) { $cfg.telegram.token } else { '' }
$chatId = if ($cfg -and $cfg.telegram) { $cfg.telegram.chat_id } else { '' }
$driveFolder = if ($cfg) { $cfg.drive_folder } else { '' }

# ---- 1. generate ---------------------------------------------------------
$resultPath = Join-Path $root '.cache\report-result.json'
$args = @((Join-Path $root 'tools\build_weekly_report.py'), '--generate', '--emit-result', $resultPath)
if ($CatchUp) { $args += '--catch-up' }
if ($DryRun)  { $args += '--dry-run' }

Write-Log "generate start (catchup=$CatchUp dryrun=$DryRun)"
try {
  & $py @args 2>&1 | ForEach-Object { Write-Log ("  " + $_) }
} catch {
  Write-Log ("ERROR: " + $_.Exception.Message)
  exit 1
}

if (-not (Test-Path $resultPath)) {
  Write-Log "not due or generation skipped; nothing to deliver"
  exit 0
}
$result = Get-Content $resultPath -Raw -Encoding utf8 | ConvertFrom-Json
$reportPath = $result.report_path
if (-not (Test-Path $reportPath)) { Write-Log "ERROR: report missing at $reportPath"; exit 1 }
Write-Log ("generated: " + (Split-Path $reportPath -Leaf))

# ---- 2. copy into the cloud folder ---------------------------------------
$where = '本機 reports/（未偵測到 Google Drive 資料夾）'
if (-not $DryRun -and $driveFolder -and (Test-Path $driveFolder)) {
  try {
    $dest = Join-Path $driveFolder (Split-Path $reportPath -Leaf)
    # If the name is taken (an earlier copy still open in Word), add a suffix.
    if (Test-Path $dest) {
      $stem = [System.IO.Path]::GetFileNameWithoutExtension($dest)
      $ext = [System.IO.Path]::GetExtension($dest)
      for ($i = 1; $i -lt 10; $i++) {
        $candidate = Join-Path $driveFolder ("{0} ({1}){2}" -f $stem, $i, $ext)
        if (-not (Test-Path $candidate)) { $dest = $candidate; break }
      }
    }
    Copy-Item -LiteralPath $reportPath -Destination $dest -Force -ErrorAction Stop
    $where = 'Google Drive'
    Write-Log "copied to Drive: $dest"
  } catch {
    $where = "本機 reports/（Drive 寫入失敗：$($_.Exception.Message.Split([Environment]::NewLine)[0])）"
    Write-Log ("WARNING: Drive copy failed: " + $_.Exception.Message.Split([Environment]::NewLine)[0])
  }
} elseif (-not $DryRun) {
  Write-Log "no drive folder configured; leaving the report local"
}

# ---- 3. notify ------------------------------------------------------------
$summary = @(
  "📊 SmartMall 週報已生成",
  "$($result.commits) 個提交 · $($result.products) 件商品",
  "位置：$where",
  "檔名：$(Split-Path $reportPath -Leaf)"
)
if ($result.uncommitted -gt 0) { $summary += "⚠️ 有 $($result.uncommitted) 個未提交檔案" }
$text = $summary -join "`n"

if ($DryRun -or -not $token -or -not $chatId) {
  Write-Log ("telegram skipped (dryrun=$DryRun, configured=" + [bool]($token -and $chatId) + ")")
} else {
  try {
    $body = @{ chat_id = $chatId; text = $text; disable_web_page_preview = 'true' }
    $resp = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/sendMessage" `
      -Method Post -Body $body -TimeoutSec 25
    if ($resp.ok) { Write-Log "telegram sent" } else { Write-Log "telegram rejected: $($resp | ConvertTo-Json -Compress)" }
  } catch {
    Write-Log ("ERROR sending telegram: " + $_.Exception.Message)
  }
}

Write-Log "run finished ok"
exit 0
