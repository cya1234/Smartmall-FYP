# Capture screenshots of the running site.
#
# Run this from a normal PowerShell window (not through the agent's sandbox): Chrome
# needs to create IPC channels for its own child processes, and a restricted token
# blocks that with "platform_channel.cc Check failed". Your own terminal has no such
# restriction, so this works there.
#
#   .\tools\shots.ps1                      # all key pages
#   .\tools\shots.ps1 -Pages closet,survey # just some
#
# Output goes to .cache\shots\ as PNGs, which the agent can then open and inspect.

param(
  [string]$Base = "http://127.0.0.1:3000",
  [string]$Out = ".cache\shots",
  [string[]]$Pages = @(),
  [int]$Width = 1440,
  [int]$Height = 1000,
  [int]$WaitMs = 8000
)

$chromeCandidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { Write-Error "No Chrome or Edge found. Install one, or pass a browser path."; exit 1 }

$all = [ordered]@{
  home       = "#/"
  shop       = "#/shop"
  product    = "#/product/p004"
  shoe       = "#/product/p013"
  earbuds    = "#/product/p042"
  closet     = "#/closet"
  survey     = "#/survey"
  surveyDemo = "#/survey/demo"
  aesthetic  = "#/aesthetic"
  tryon      = "#/tryon"
  dashboard  = "#/dashboard"
  stores     = "#/stores"
}

$names = if ($Pages.Count) { $Pages } else { $all.Keys }
$root = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $root $Out
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "Browser : $chrome"
Write-Host "Base    : $Base"
Write-Host "Output  : $outDir"
Write-Host ""

foreach ($name in $names) {
  if (-not $all.Contains($name)) { Write-Warning "unknown page '$name'"; continue }
  $url = $Base + "/" + $all[$name]
  $file = Join-Path $outDir "$name.png"
  if (Test-Path $file) { Remove-Item $file -Force }

  $args = @(
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--disable-extensions",
    "--user-data-dir=$outDir\profile",
    "--window-size=$Width,$Height",
    "--virtual-time-budget=$WaitMs",
    "--screenshot=$file",
    $url
  )
  & $chrome @args 2>$null | Out-Null
  Start-Sleep -Milliseconds 600

  if (Test-Path $file) {
    $kb = [math]::Round((Get-Item $file).Length / 1KB)
    Write-Host ("  OK    {0,-10} {1,5} KB  {2}" -f $name, $kb, $url)
  } else {
    Write-Host ("  FAIL  {0,-10} {1}" -f $name, $url)
  }
}

Write-Host ""
Write-Host "Done. Ask the agent to look at .cache\shots\*.png"
