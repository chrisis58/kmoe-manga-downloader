# Install kmdr companion native messaging host (Windows)
# Run: powershell -ExecutionPolicy Bypass -File install.ps1
param(
  $InstallDir = "$env:APPDATA\kmdr-companion",
  $ExtId = "",
  [switch]$SkipDownload  # internal: skip download, binary already in place
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoOwner = "chrisis58"
$RepoName = "kmoe-manga-downloader"
$exePath = "$InstallDir\native_host.exe"

# Create install directory
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# ── Download / verify binary ─────────────────────────────────────

if (-not $SkipDownload) {
  Write-Host "Downloading native host..." -ForegroundColor Cyan
  $releaseUrl = "https://github.com/$RepoOwner/$RepoName/releases/latest/download/native_host-windows-amd64.exe"
  Write-Host "  $releaseUrl"
  try {
    Invoke-WebRequest -Uri $releaseUrl -OutFile $exePath -ErrorAction Stop
  } catch {
    Write-Host "  ERROR: Download failed: $_" -ForegroundColor Red
    Write-Host "  For local development, use: install-dev.ps1" -ForegroundColor Yellow
    exit 1
  }
} else {
  Write-Host "Using existing binary: $exePath" -ForegroundColor Cyan
}

if (-not (Test-Path $exePath)) {
  Write-Host "  ERROR: $exePath not found" -ForegroundColor Red
  exit 1
}
Write-Host "  OK: $exePath" -ForegroundColor Green

# ── Extension ID ─────────────────────────────────────────────────

if (-not $ExtId) {
  $extManifest = "$ScriptDir\extension\manifest.json"
  if (Test-Path $extManifest) {
    $extData = Get-Content $extManifest -Raw | ConvertFrom-Json
    if ($extData.key) {
      Write-Host ""
      Write-Host "Extension has a 'key' field but ID computation requires openssl." -ForegroundColor Yellow
      Write-Host "Please check edge://extensions for the extension ID." -ForegroundColor Yellow
    }
  }
}

while (-not $ExtId -or $ExtId.Length -ne 32) {
  $ExtId = Read-Host "Enter the 32-char extension ID from edge://extensions"
}

# ── Manifest ─────────────────────────────────────────────────────

$manifest = @{
  name            = "com.kmdr.host"
  description     = "Kmoe Manga Downloader Native Messaging Host"
  path            = $exePath
  type            = "stdio"
  allowed_origins = @("chrome-extension://$ExtId/")
}

$manifestPath = "$InstallDir\kmdr_native_host.json"
$manifest | ConvertTo-Json -Depth 3 | Out-File -FilePath $manifestPath -Encoding UTF8
Write-Host "  Manifest: $manifestPath" -ForegroundColor Green

# ── Register for Chrome and Edge ─────────────────────────────────

$browsers = @{
  Chrome = "HKCU:\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.kmdr.host"
  Edge   = "HKCU:\SOFTWARE\Microsoft\Edge\NativeMessagingHosts\com.kmdr.host"
}

Write-Host ""
Write-Host "Registering native messaging host..." -ForegroundColor Cyan
foreach ($browser in $browsers.GetEnumerator()) {
  New-Item -Path $browser.Value -Force | Out-Null
  Set-ItemProperty -Path $browser.Value -Name "(Default)" -Value $manifestPath
  Write-Host "  OK: $($browser.Key)" -ForegroundColor Green
}

# ── Done ─────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Close browser completely (check Task Manager for msedge.exe)"
Write-Host "  2. edge://settings/system → disable 'Startup Boost' if on"
Write-Host "  3. Load extension: edge://extensions → Load unpacked → $ScriptDir\extension"
Write-Host "  4. Verify ID matches: $ExtId"
