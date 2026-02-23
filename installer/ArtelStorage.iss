# ArtelStorage Installer (Inno Setup)
#
# Build flow:
# 1) Build 2 exe via PyInstaller into dist\ArtelStorage and dist\ArtelStorageAdmin
# 2) Compile this .iss in Inno Setup to produce a single installer

#define AppName "ArtelStorage"
#define AppVersion "1.1"
#define AppPublisher "OOO AS Gorizont"

; Where PyInstaller outputs should live
#define MainDistDir "dist\\ArtelStorage"
#define AdminDistDir "dist\\ArtelStorageAdmin"

[Setup]
AppId={{9B5E6A30-6E7B-4B21-9D2C-0F4C5A1C1F21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\\{#AppName}
DefaultGroupName={#AppName}
OutputDir=dist_installer
OutputBaseFilename=ArtelStorage_{#AppVersion}_Setup
Compression=lzma
SolidCompression=yes

; Needs admin for Program Files install. If you prefer per-user install, change DefaultDirName.
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "Создать ярлыки на рабочем столе"; Flags: unchecked

[Files]
; Main app
Source: "{#MainDistDir}\\*"; DestDir: "{app}\\Main"; Flags: recursesubdirs ignoreversion
; Admin app
Source: "{#AdminDistDir}\\*"; DestDir: "{app}\\Admin"; Flags: recursesubdirs ignoreversion

[Icons]
; Start menu
Name: "{group}\\ArtelStorage"; Filename: "{app}\\Main\\ArtelStorage.exe"
Name: "{group}\\ArtelStorage Admin"; Filename: "{app}\\Admin\\ArtelStorageAdmin.exe"

; Desktop (optional)
Name: "{commondesktop}\\ArtelStorage"; Filename: "{app}\\Main\\ArtelStorage.exe"; Tasks: desktopicon
Name: "{commondesktop}\\ArtelStorage Admin"; Filename: "{app}\\Admin\\ArtelStorageAdmin.exe"; Tasks: desktopicon

[Run]
; Optional: launch after install
Filename: "{app}\\Main\\ArtelStorage.exe"; Description: "Запустить ArtelStorage"; Flags: nowait postinstall skipifsilent
