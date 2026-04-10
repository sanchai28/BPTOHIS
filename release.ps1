# ============================================================
# release.ps1 - BPTOHIS Release Script
# ใช้งาน: .\release.ps1
# ต้องการ: git, gh CLI, PyInstaller ติดตั้งแล้ว
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  BPTOHIS Release Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 0: อ่านเวอร์ชันปัจจุบัน ─────────────────────────
$currentVersion = (Get-Content "version.txt" -Raw).Trim()
Write-Host "เวอร์ชันปัจจุบัน: " -NoNewline
Write-Host "v$currentVersion" -ForegroundColor Yellow

# ── Step 1: กรอกเวอร์ชันใหม่ ──────────────────────────────
$newVersion = Read-Host "`nกรอกเวอร์ชันใหม่ (เช่น 1.1.0)"
if (-not $newVersion -or $newVersion -eq $currentVersion) {
    Write-Host "เวอร์ชันไม่ถูกต้องหรือเหมือนเดิม ยกเลิก" -ForegroundColor Red
    exit 1
}

$releaseNotes = Read-Host "Release notes (สั้นๆ)"
if (-not $releaseNotes) { $releaseNotes = "อัปเดตเวอร์ชัน $newVersion" }

Write-Host ""
Write-Host "── จะ Release v$newVersion ──" -ForegroundColor Green
Write-Host "Notes: $releaseNotes"
$confirm = Read-Host "ยืนยัน? (Y/N)"
if ($confirm -ne "Y" -and $confirm -ne "y") { Write-Host "ยกเลิก"; exit 0 }

# ── Step 2: อัปเดต version.txt ────────────────────────────
Write-Host "`n[1/5] อัปเดต version.txt..." -ForegroundColor Cyan
Set-Content "version.txt" $newVersion -Encoding UTF8
Write-Host "     version.txt = $newVersion" -ForegroundColor Green

# ── Step 3: Git commit & push ─────────────────────────────
Write-Host "`n[2/5] Git commit & push..." -ForegroundColor Cyan
git add .
git commit -m "Release v$newVersion`: $releaseNotes"
git tag "v$newVersion"
git push origin master
git push origin "v$newVersion"
Write-Host "     Push สำเร็จ" -ForegroundColor Green

# ── Step 4: PyInstaller Build ─────────────────────────────
Write-Host "`n[3/5] PyInstaller build (one-dir)..." -ForegroundColor Cyan
if (Test-Path "dist\BPTOHIS_v2") {
    Remove-Item -Recurse -Force "dist\BPTOHIS_v2"
}
pyinstaller BPTOHIS_v2_onedir.spec --noconfirm
if (-not (Test-Path "dist\BPTOHIS_v2\BPTOHIS_v2.exe")) {
    Write-Host "Build ล้มเหลว! ไม่พบ exe" -ForegroundColor Red
    exit 1
}
Write-Host "     Build สำเร็จ" -ForegroundColor Green

# ── Step 5: แตก version.txt ลงใน dist ────────────────────
Set-Content "dist\BPTOHIS_v2\version.txt" $newVersion -Encoding UTF8

# ── Step 6: ZIP ───────────────────────────────────────────
Write-Host "`n[4/5] กำลัง ZIP..." -ForegroundColor Cyan
$zipPath = "$ScriptDir\BPTOHIS_v2.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "dist\BPTOHIS_v2" -DestinationPath $zipPath -CompressionLevel Optimal
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "     BPTOHIS_v2.zip ($sizeMB MB)" -ForegroundColor Green

# ── Step 7: GitHub Release ────────────────────────────────
Write-Host "`n[5/5] สร้าง GitHub Release v$newVersion..." -ForegroundColor Cyan
gh release create "v$newVersion" $zipPath `
    --title "BPTOHIS v$newVersion" `
    --notes $releaseNotes `
    --latest
Write-Host "     Release สำเร็จ" -ForegroundColor Green

# ── Cleanup ───────────────────────────────────────────────
Remove-Item $zipPath -Force

# ── Done ──────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Release v$newVersion เสร็จสมบูรณ์!" -ForegroundColor Green
Write-Host "  https://github.com/sanchai28/BPTOHIS/releases" -ForegroundColor Green
Write-Host "  เครื่อง kiosk จะอัปเดตเองภายใน 1 ชั่วโมง" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
