# Install kmdr companion native messaging host — dev mode (Windows)
# Builds from local source, then delegates manifest + registry to install.ps1
# Run: powershell -ExecutionPolicy Bypass -File install-dev.ps1

param(
  $InstallDir = "$env:APPDATA\kmdr-companion",
  $ExtId = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = "$InstallDir\native_host.exe"

# Check Go
$go = Get-Command go -ErrorAction SilentlyContinue
if (-not $go) {
  Write-Host "ERROR: Go is not installed. Install from https://go.dev/dl/" -ForegroundColor Red
  exit 1
}

# Build (output to local dir so go build doesn't need full install path)
$srcExe = Join-Path $ScriptDir "native_host.exe"
Write-Host "Building native host from source..." -ForegroundColor Cyan
Push-Location $ScriptDir
try {
  & go build -v -o native_host.exe
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    Pop-Location
    exit 1
  }
} finally {
  Pop-Location
}

# Copy to install dir
Copy-Item -Force $srcExe $exePath
Write-Host "  OK: $exePath" -ForegroundColor Green

# Delegate manifest + registry to install.ps1
$installScript = Join-Path $ScriptDir "install.ps1"
$params = @{}
if ($ExtId) { $params["ExtId"] = $ExtId }
& $installScript -InstallDir $InstallDir -SkipDownload @params
