# Install kmdr companion native messaging host (Windows)
# Run: powershell -ExecutionPolicy Bypass -File install.ps1
param(
  $InstallDir = "$env:APPDATA\kmdr-companion",
  $ExtId = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Create install directory
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Build Go native host
Write-Host "Building native host..." -ForegroundColor Cyan
Push-Location $ScriptDir
$goResult = & go build -o "$InstallDir\native_host.exe" native_host.go 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Go build failed:" -ForegroundColor Red
    Write-Host $goResult
    exit 1
}
Pop-Location
Write-Host "  OK: $InstallDir\native_host.exe" -ForegroundColor Green

# Determine extension ID — use parameter, or check manifest, or prompt
if (-not $ExtId) {
    # Try to read from extension manifest
    $extManifest = "$ScriptDir\extension\manifest.json"
    if (Test-Path $extManifest) {
        $extData = Get-Content $extManifest -Raw | ConvertFrom-Json
        if ($extData.key) {
            # Compute ID from key (simplified: ask user to provide it)
            Write-Host ""
            Write-Host "Extension has a 'key' field but ID computation requires openssl." -ForegroundColor Yellow
            Write-Host "Please check edge://extensions for the extension ID." -ForegroundColor Yellow
        }
    }
}

while (-not $ExtId -or $ExtId.Length -ne 32) {
    $ExtId = Read-Host "Enter the 32-char extension ID from edge://extensions"
}

# Build manifest
$manifest = @{
    name = "com.kmdr.host"
    description = "Kmoe Manga Downloader Native Messaging Host"
    path = "$InstallDir\native_host.exe"
    type = "stdio"
    allowed_origins = @("chrome-extension://$ExtId")
}

$manifestPath = "$InstallDir\kmdr_native_host.json"
$manifest | ConvertTo-Json -Depth 3 | Out-File -FilePath $manifestPath -Encoding UTF8
Write-Host "  Manifest: $manifestPath" -ForegroundColor Green

# Register for Chrome and Edge
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

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Close Edge completely (check Task Manager for msedge.exe)"
Write-Host "  2. edge://settings/system → disable 'Startup Boost'"
Write-Host "  3. Load extension: edge://extensions → Load unpacked → $ScriptDir\extension"
Write-Host "  4. Verify ID matches: $ExtId"
