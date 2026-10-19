# Called by Get Code Editor.bat: sets up Continue (offline AI in VSCodium) and points Archie Coach at Archie.
param([string]$ArchieFolder)
$ArchieFolder = [System.IO.Path]::GetFullPath($ArchieFolder).TrimEnd('\')

# 1. Continue: use Archie's own models through Ollama (nothing online)
$cdir = Join-Path $env:USERPROFILE ".continue"
New-Item -ItemType Directory -Force -Path $cdir | Out-Null
$cfg = Join-Path $cdir "config.yaml"
if (-not (Test-Path $cfg)) {
@"
name: Archie (offline)
version: 1.0.0
schema: v1
models:
  - name: Archie coder (qwen2.5-coder 7B)
    provider: ollama
    model: qwen2.5-coder:7b
    roles: [chat, edit, apply]
  - name: Archie autocomplete (qwen2.5-coder 1.5B)
    provider: ollama
    model: qwen2.5-coder:1.5b
    roles: [autocomplete]
"@ | Set-Content -Encoding UTF8 $cfg
  Write-Host "  Continue set up to use Archie's models."
} else {
  Write-Host "  Continue already has a config.yaml; left it as it is."
}

# 2. VSCodium settings: no telemetry from Continue, and where Archie lives
$sdir = Join-Path $env:APPDATA "VSCodium\User"
New-Item -ItemType Directory -Force -Path $sdir | Out-Null
$sfile = Join-Path $sdir "settings.json"
$s = @{}
if (Test-Path $sfile) {
  try { $s = Get-Content $sfile -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop } catch {
    try { $o = Get-Content $sfile -Raw | ConvertFrom-Json -ErrorAction Stop; $s = @{}; $o.PSObject.Properties | ForEach-Object { $s[$_.Name] = $_.Value } } catch {
      Write-Host "  Couldn't read VSCodium's settings.json (it has comments?). Add these by hand in VSCodium's settings:"
      Write-Host "    continue.telemetryEnabled: false"
      Write-Host "    archieCoach.archieFolder: $ArchieFolder"
      exit 0
    }
  }
}
if ($null -eq $s) { $s = @{} }
$s["continue.telemetryEnabled"] = $false
$s["telemetry.telemetryLevel"] = "off"
$s["archieCoach.archieFolder"] = $ArchieFolder
$s | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $sfile
Write-Host "  VSCodium settings saved (telemetry off, Archie Coach pointed at $ArchieFolder)."
