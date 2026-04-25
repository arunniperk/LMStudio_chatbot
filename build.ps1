# build.ps1
$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "Building Local Chatbot Installer..."

Write-Host "`n =========================================" -ForegroundColor Cyan
Write-Host "  Local Chatbot - EXE & Installer Builder" -ForegroundColor Cyan
Write-Host " =========================================`n" -ForegroundColor Cyan

Write-Host "[1/4] Installing PyInstaller..." -ForegroundColor White
pip install pyinstaller --quiet

Write-Host "[2/4] Installing dependencies..." -ForegroundColor White
pip install -r requirements.txt --quiet

Write-Host "[3/4] Building EXE files... (1-3 minutes)" -ForegroundColor White
pyinstaller chatbot.spec --noconfirm

Write-Host "[4/4] Creating Setup Installer Wizard..." -ForegroundColor White
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"

if (Test-Path $iscc) {
    & $iscc setup.iss
    Write-Host "`n =========================================" -ForegroundColor Green
    Write-Host "  INSTALLER BUILT SUCCESSFULLY" -ForegroundColor Green
    Write-Host " =========================================" -ForegroundColor Green
    Write-Host " Your standalone installer is located at:"
    Write-Host " dist_installer\LocalChatbot_Setup.exe`n" -ForegroundColor Cyan
} else {
    Write-Host "`n =========================================" -ForegroundColor Yellow
    Write-Host "  PYINSTALLER BUILD COMPLETE" -ForegroundColor Yellow
    Write-Host " =========================================" -ForegroundColor Yellow
    Write-Host " App compiled, but no Setup Installer was created."
    Write-Host " To generate a .exe installer wizard, you need Inno Setup 6."
    Write-Host " 1. Download and install from: https://jrsoftware.org/isdl.php"
    Write-Host " 2. Run this script again.`n"
    Write-Host " For now, your portable folder is in: dist\LMStudio_Chatbot\`n"
}