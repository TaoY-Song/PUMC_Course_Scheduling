; PUMC 智能排课系统 v3.0 — Inno Setup 安装脚本
; 开发者：STaoY
;
; 使用前提：
;   1. cd web && npm run build && cd ..
;   2. pyinstaller app_web.py --name PUMC_Scheduler --onedir --noconsole --icon installer/PUMClogo.ico --add-data "web/dist;web/dist"
;   3. iscc installer\pumc_scheduler.iss
;
; 产出：installer_output\PUMC_Scheduler_v3.0_Setup.exe

#define MyAppName      "PUMC智能排课系统"
#define MyAppVersion   "3.0"
#define MyAppPublisher "STaoY"
#define MyAppExeName   "PUMC_Scheduler.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\installer_output
OutputBaseFilename=PUMC_Scheduler_v{#MyAppVersion}_Setup
SetupIconFile=PUMClogo.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "..\dist\PUMC_Scheduler\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载{#MyAppName}";   Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动{#MyAppName}"; Flags: nowait postinstall skipifsilent
