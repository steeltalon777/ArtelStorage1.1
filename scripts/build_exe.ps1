param(
  [string]$Python = "python",
  [switch]$Clean
)

$ErrorActionPreference = "Stop"

if ($Clean) {
  if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
  if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

& $Python -m pip install -r requirements.txt
& $Python -m pip install pyinstaller

& $Python -m PyInstaller --noconfirm --clean --windowed --name ArtelStorage main_app.py
& $Python -m PyInstaller --noconfirm --clean --windowed --name ArtelStorageAdmin admin_app.py

Write-Host "Built: dist\\ArtelStorage\\ArtelStorage.exe"
Write-Host "Built: dist\\ArtelStorageAdmin\\ArtelStorageAdmin.exe"
Write-Host "Next: compile installer\\ArtelStorage.iss in Inno Setup"
