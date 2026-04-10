# ============================================================
# release.ps1 - BPTOHIS Release Script
# ============================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  BPTOHIS Release Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# อ่านเวอร์ชันปัจจุบัน
$currentVersion = (Get-Content "version.txt" -Encoding UTF8 -Raw).Trim()
Write-Host "เวอร์ชันปัจจุบัน: v$currentVersion" -ForegroundColor Yellow
Write-Host ""

# กรอกเวอร์ชันใหม่ พร้อม validate รูปแบบ X.Y.Z
do {
    $newVersion = Read-Host "กรอกเวอร์ชันใหม่ (รูปแบบ X.Y.Z เช่น 1.1.0)"
    if ($newVersion -notmatch '^\d+\.\d+\.\d+$') {
        Write-Host "รูปแบบไม่ถูกต้อง ต้องเป็น X.Y.Z เช่น 1.1.0" -ForegroundColor Red
        $newVersion = ""
    } elseif ($newVersion -eq $currentVersion) {
        Write-Host "เวอร์ชันเหมือนเดิม กรุณาใส่เวอร์ชันที่สูงกว่า" -ForegroundColor Red
        $newVersion = ""
    }
} while (-not $newVersion)

$releaseNotes = Read-Host "Release notes"
if (-not $releaseNotes) { $releaseNotes = "Release v$newVersion" }

Write-Host ""
Write-Host "จะ Release: v$newVersion" -ForegroundColor Green
Write-Host "Notes: $releaseNotes"
Write-Host ""
$confirm = Read-Host "ยืนยัน? (Y/N)"
if ($confirm -notin @("Y","y")) { Write-Host "ยกเลิก"; exit 0 }

# ── [1/5] อัปเดต version.txt ─────────────────────────────
Write-Host ""
Write-Host "[1/5] อัปเดต version.txt..." -ForegroundColor Cyan
Set-Content "version.txt" $newVersion -Encoding UTF8
Write-Host "      OK: version.txt = $newVersion" -ForegroundColor Green

# ── [2/5] Git commit & push ───────────────────────────────
Write-Host ""
Write-Host "[2/5] Git commit & push..." -ForegroundColor Cyan
git add .
git commit -m "Release v${newVersion}: $releaseNotes"
git tag "v$newVersion"
git push origin master
git push origin "v$newVersion"
Write-Host "      OK: Push สำเร็จ" -ForegroundColor Green

# ── [3/5] PyInstaller Build ───────────────────────────────
Write-Host ""
Write-Host "[3/5] PyInstaller build (one-dir)..." -ForegroundColor Cyan

if (Test-Path "dist\BPTOHIS_v2") {
    Remove-Item -Recurse -Force "dist\BPTOHIS_v2"
}

python -m PyInstaller BPTOHIS_v2_onedir.spec --noconfirm

if (-not (Test-Path "dist\BPTOHIS_v2\BPTOHIS_v2.exe")) {
    Write-Host "Build ล้มเหลว! ไม่พบ BPTOHIS_v2.exe" -ForegroundColor Red
    exit 1
}

# คัดลอก version.txt เข้าไปใน dist ด้วย
Set-Content "dist\BPTOHIS_v2\version.txt" $newVersion -Encoding UTF8
Write-Host "      OK: Build สำเร็จ" -ForegroundColor Green

# ── [4/5] ZIP ─────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] กำลัง ZIP..." -ForegroundColor Cyan
$zipPath = "$PSScriptRoot\BPTOHIS_v2.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "dist\BPTOHIS_v2" -DestinationPath $zipPath -CompressionLevel Optimal
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "      OK: BPTOHIS_v2.zip ($sizeMB MB)" -ForegroundColor Green

# ── [5/5] GitHub Release ──────────────────────────────────
Write-Host ""
Write-Host "[5/5] สร้าง GitHub Release v$newVersion..." -ForegroundColor Cyan
gh release create "v$newVersion" $zipPath `
    --title "BPTOHIS v$newVersion" `
    --notes $releaseNotes `
    --latest
Remove-Item $zipPath -Force
Write-Host "      OK: Release สำเร็จ" -ForegroundColor Green

# ── Done ──────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Release v$newVersion เสร็จสมบูรณ์!" -ForegroundColor Green
Write-Host "  https://github.com/sanchai28/BPTOHIS/releases" -ForegroundColor Green
Write-Host "  เครื่อง kiosk จะอัปเดตเองภายใน 1 ชั่วโมง" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
