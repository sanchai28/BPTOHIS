[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Add gh CLI to PATH
$env:PATH = "C:\Program Files\GitHub CLI;$env:PATH"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  BPTOHIS Release Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Validate tools
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] gh CLI not found. Restart PowerShell and try again." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] python not found." -ForegroundColor Red
    exit 1
}

# Read current version
$currentVersion = (Get-Content "version.txt" -Encoding UTF8 -Raw).Trim()
Write-Host "Current version: v$currentVersion" -ForegroundColor Yellow
Write-Host ""

# Prompt for new version (must be X.Y.Z)
$newVersion = ""
while ($true) {
    $newVersion = Read-Host "New version (e.g. 1.1.0)"
    if ($newVersion -notmatch '^\d+\.\d+\.\d+$') {
        Write-Host "[!] Must be X.Y.Z format" -ForegroundColor Red
        continue
    }
    if ($newVersion -eq $currentVersion) {
        Write-Host "[!] Same as current version" -ForegroundColor Red
        continue
    }
    break
}

$releaseNotes = Read-Host "Release notes"
if (-not $releaseNotes) { $releaseNotes = "Release v$newVersion" }

Write-Host ""
Write-Host "Release: v$newVersion  |  Notes: $releaseNotes" -ForegroundColor Green
$confirm = Read-Host "Confirm? (Y/N)"
if ($confirm -notin @("Y","y")) { Write-Host "Cancelled."; exit 0 }

# [1/5] version.txt
Write-Host ""
Write-Host "[1/5] Update version.txt..." -ForegroundColor Cyan
Set-Content "version.txt" $newVersion -Encoding UTF8
Write-Host "      OK v$newVersion" -ForegroundColor Green

# [2/5] Git commit & push
Write-Host ""
Write-Host "[2/5] Git commit & push..." -ForegroundColor Cyan
git add .
git commit -m "Release v${newVersion}: $releaseNotes"
git tag "v$newVersion"
git push origin master
git push origin "v$newVersion"
Write-Host "      OK" -ForegroundColor Green

# [3/5] PyInstaller build
Write-Host ""
Write-Host "[3/5] PyInstaller build..." -ForegroundColor Cyan
if (Test-Path "dist\BPTOHIS_v2") { Remove-Item "dist\BPTOHIS_v2" -Recurse -Force }
python -m PyInstaller BPTOHIS_v2_onedir.spec --noconfirm
if (-not (Test-Path "dist\BPTOHIS_v2\BPTOHIS_v2.exe")) {
    Write-Host "[ERROR] Build failed." -ForegroundColor Red
    exit 1
}
Set-Content "dist\BPTOHIS_v2\version.txt" $newVersion -Encoding UTF8
Write-Host "      OK" -ForegroundColor Green

# [4/5] ZIP
Write-Host ""
Write-Host "[4/5] Creating ZIP..." -ForegroundColor Cyan
$zipPath = "$PSScriptRoot\BPTOHIS_v2.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "dist\BPTOHIS_v2" -DestinationPath $zipPath -CompressionLevel Optimal
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "      OK BPTOHIS_v2.zip ($sizeMB MB)" -ForegroundColor Green

# [5/5] GitHub Release
Write-Host ""
Write-Host "[5/5] Creating GitHub Release v$newVersion..." -ForegroundColor Cyan
gh release create "v$newVersion" $zipPath --title "BPTOHIS v$newVersion" --notes $releaseNotes --latest
Remove-Item $zipPath -Force
Write-Host "      OK" -ForegroundColor Green

# Done
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  DONE! v$newVersion released" -ForegroundColor Green
Write-Host "  https://github.com/sanchai28/BPTOHIS/releases" -ForegroundColor Green
Write-Host "  Kiosks will auto-update within 1 hour." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
