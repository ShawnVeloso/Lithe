# =============================================================================
# Lithe - Master Build Script
# =============================================================================
# Builds the complete Lithe desktop application:
#   1. Compiles Python backend with PyInstaller
#   2. Builds Electron frontend with electron-vite
#   3. Packages everything into a Windows installer with electron-builder
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build-all.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$FrontendDir = Join-Path (Join-Path $ProjectRoot "src") "frontend"

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Lithe - Full Application Build" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

# -------------------------------------------------------
# Step 1: Build Python Backend
# -------------------------------------------------------
Write-Host "Step 1/4: Building Python backend..." -ForegroundColor Cyan
Write-Host "-------------------------------------------"
& powershell -ExecutionPolicy Bypass -File (Join-Path (Join-Path $ProjectRoot "scripts") "build-backend.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend build failed." -ForegroundColor Red
    exit 1
}

# -------------------------------------------------------
# Step 2: Copy .env to AppData (first-run convenience)
# -------------------------------------------------------
Write-Host "Step 2/4: Setting up AppData config..." -ForegroundColor Cyan
$appdataDir = Join-Path $env:APPDATA "Lithe"
if (-not (Test-Path $appdataDir)) {
    New-Item -ItemType Directory -Path $appdataDir -Force | Out-Null
}
$envSource = Join-Path $ProjectRoot ".env"
$envDest = Join-Path $appdataDir ".env"
if ((Test-Path $envSource) -and (-not (Test-Path $envDest))) {
    Copy-Item $envSource $envDest
    Write-Host "  Copied .env to $envDest" -ForegroundColor Green
} elseif (Test-Path $envDest) {
    Write-Host "  .env already exists at $envDest - skipping" -ForegroundColor Yellow
} else {
    Write-Host "  WARNING: No .env found at project root." -ForegroundColor Yellow
}
Write-Host ""

# -------------------------------------------------------
# Step 3: Build Electron frontend
# -------------------------------------------------------
Write-Host "Step 3/4: Building Electron frontend..." -ForegroundColor Cyan
Write-Host "-------------------------------------------"
Push-Location $FrontendDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: electron-vite build failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Electron build complete." -ForegroundColor Green
} finally {
    Pop-Location
}
Write-Host ""

# -------------------------------------------------------
# Step 4: Package with electron-builder
# -------------------------------------------------------
Write-Host "Step 4/4: Packaging installer..." -ForegroundColor Cyan
Write-Host "-------------------------------------------"
Push-Location $FrontendDir
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
try {
    npm run dist
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: electron-builder failed." -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host "  Installer: src/frontend/release/" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
