# tools/make-portable.ps1
#
# Package this project for a machine that is wiped on reboot (school lab, GPU cluster).
#
# The rule that shapes it: nothing installed there survives, so the bundle carries
# everything that is expensive to re-fetch and nothing that is machine-specific.
#
#   kept      source, data, model weights, docs      -> slow to obtain, needed every time
#   dropped   .venv, .git, caches, accounts          -> machine-specific, or should not travel
#
#   .\tools\make-portable.ps1                      # bundle next to the project
#   .\tools\make-portable.ps1 -Out E:\SmartMall    # bundle straight onto a USB drive
#   .\tools\make-portable.ps1 -Wheels              # also cache pip wheels for offline install
#   .\tools\make-portable.ps1 -List                # dry run: show what would be copied
#
# Expected size: about 11 GB, dominated by the 10.8 GB of model weights.

param(
  [string]$Out = "",
  [switch]$Wheels,
  [switch]$List,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $Out) { $Out = Join-Path (Split-Path -Parent $root) 'SmartMall-portable' }

function Say($m) { Write-Host "  $m" }
function Size($p) {
  if (-not (Test-Path $p)) { return 0 }
  (Get-ChildItem $p -Recurse -File -Force -ErrorAction SilentlyContinue |
    Measure-Object Length -Sum).Sum
}

Say "source : $root"
Say "target : $Out"
Say ""

if ($List) {
  Say "would copy (dry run):"
  $inc = Size $root
  foreach ($x in @('.venv', '.git', 'node_modules', '.cache\mpl')) {
    $s = Size (Join-Path $root $x)
    Say ("  skip {0,-16} {1,8:N2} GB" -f $x, ($s / 1GB))
    $inc -= $s
  }
  foreach ($f in @('data\users.json', 'data\sessions.json', 'data\analytics.db')) {
    $p = Join-Path $root $f
    if (Test-Path $p) { Say ("  skip {0,-16} {1,8:N2} MB  (account data must not travel)" -f $f, ((Get-Item $p).Length / 1MB)) }
  }
  Say ("  ---- approx bundle: {0:N2} GB" -f ($inc / 1GB))
  return
}

if ((Test-Path $Out) -and -not $Force) {
  $existing = Get-ChildItem $Out -Force -ErrorAction SilentlyContinue
  if ($existing) {
    throw "target '$Out' already has files; pass -Force to overwrite"
  }
}
New-Item -ItemType Directory -Force -Path $Out | Out-Null

# robocopy exit codes: 0-7 are success, 8+ are failures.
$xd = @('.venv', '.git', 'node_modules', '.cache\mpl', '.cache\logs')
$xf = @('users.json', 'sessions.json', 'analytics.db', 'analytics.db-shm', 'analytics.db-wal')

Say "copying (this takes a few minutes for ~11 GB) ..."
$args = @($root, $Out, '/E', '/XJ', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
$args += '/XD'
$args += $xd | ForEach-Object { Join-Path $root $_ }
$args += '/XF'
$args += $xf
& robocopy @args | Out-Null
$code = $LASTEXITCODE
if ($code -ge 8) { throw "robocopy failed with code $code" }

# Account data is excluded above; make that visible in the bundle so nobody wonders
# why the login page has no accounts.
$note = @"
Accounts, sessions and the analytics database were deliberately not copied.

They hold login records for this machine only, and a lab PC is not the place for them.
The site starts with no accounts: register one on the spot, and the analytics database
re-seeds its demo history on first boot.
"@
Set-Content -Path (Join-Path $Out 'PORTABLE-NOTE.txt') -Value $note -Encoding utf8

if ($Wheels) {
  Say "caching pip wheels for an offline install ..."
  $wheelDir = Join-Path $Out 'wheels'
  New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
  $py = Join-Path $root '.venv\Scripts\python.exe'
  if (-not (Test-Path $py)) { $py = 'python' }
  & $py -m pip download -r (Join-Path $root 'requirements.txt') -d $wheelDir
  & $py -m pip download torch torchvision -d $wheelDir
  Say ("  wheels: {0:N2} GB" -f ((Size $wheelDir) / 1GB))
}

$total = Size $Out
Say ""
Say ("bundle ready : {0}" -f $Out)
Say ("size         : {0:N2} GB" -f ($total / 1GB))
Say ""
Say "on the target machine:"
Say "  1. copy the folder somewhere writable (or run it from the USB stick)"
Say "  2. python -m venv .venv"
Say "  3. .venv\Scripts\pip install -r requirements.txt"
Say "     (offline: add --no-index --find-links wheels)"
Say "  4. .\start-with-ai.bat"
Say ""
Say "read PORTABLE.md for the session plan and what to bring back."
