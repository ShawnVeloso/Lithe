# =============================================================================
# Lithe - Build Backend (PyInstaller)
# =============================================================================
# Compiles the Python backend into a standalone executable.
# Output: dist/lithe-server/lithe-server.exe
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build-backend.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Lithe - Building Python Backend" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify PyInstaller is available
Write-Host "[1/3] Checking PyInstaller..." -ForegroundColor Yellow
try {
    python -m PyInstaller --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller not found" }
    Write-Host "  OK" -ForegroundColor Green
} catch {
    Write-Host "  PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to install PyInstaller." -ForegroundColor Red
        exit 1
    }
}

# Step 2: Clean previous builds
Write-Host "[2/3] Cleaning previous builds..." -ForegroundColor Yellow
$distDir = Join-Path $ProjectRoot "dist"
$buildDir = Join-Path $ProjectRoot "pyinstaller-build"
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }
Write-Host "  OK" -ForegroundColor Green

# Step 3: Run PyInstaller
Write-Host "[3/3] Running PyInstaller..." -ForegroundColor Yellow
Push-Location $ProjectRoot
try {
    python -m PyInstaller `
        --distpath "$distDir" `
        --workpath "$buildDir" `
        --noconfirm `
        "lithe-server.spec"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: PyInstaller failed." -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

# Step 4: Copy the built backend to the Electron resources directory
Write-Host ""
Write-Host "Copying to Electron resources..." -ForegroundColor Yellow
$electronResources = Join-Path (Join-Path (Join-Path $ProjectRoot "src") "frontend") "resources\python-backend"
if (Test-Path $electronResources) { Remove-Item -Recurse -Force $electronResources }
New-Item -ItemType Directory -Path (Join-Path (Join-Path $ProjectRoot "src") "frontend\resources") -Force | Out-Null
Copy-Item -Recurse -Force (Join-Path $distDir "lithe-server") $electronResources

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Backend build complete!" -ForegroundColor Green
Write-Host "  Output: $electronResources" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
