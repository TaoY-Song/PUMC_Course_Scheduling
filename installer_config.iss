; PUMC智能排课系统安装脚本 - 包含免责声明功能

#define MyAppName "PUMC智能排课系统"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "中国医学科学院 北京协和医学院 阜外医院"
#define MyAppURL "https://www.pumc.edu.cn/"
#define MyAppExeName "PUMC_Course_Scheduling.exe"
#define MyAppId "PUMC-Course-Scheduling"

[Setup]
; 应用基本信息
AppId={{{#MyAppId}}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 安装路径设置
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableProgramGroupPage=yes

; 免责声明和许可协议 - 强制显示
LicenseFile=disclaimer.txt
InfoBeforeFile=readme_install.txt
InfoAfterFile=readme_after.txt

; 输出设置
OutputDir=installer_output
OutputBaseFilename=PUMC_Course_Scheduling_Setup_v{#MyAppVersion}
SetupIconFile=PUMC校徽.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; 权限和架构设置
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; 安装选项
DisableWelcomePage=no
DisableReadyPage=no
DisableFinishedPage=no
ShowLanguageDialog=yes

; 卸载设置
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; 使用默认英文界面，中文内容在文本文件中显示

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; OnlyBelowVersion: 6.1
Name: "startmenuicon"; Description: "Create Start Menu icon"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; 主程序文件 - 包含PyInstaller生成的所有文件
Source: "dist\PUMC_Course_Scheduling\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 文档文件
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion; DestName: "使用说明.txt"
Source: "disclaimer.txt"; DestDir: "{app}"; Flags: ignoreversion
; 示例文件（如果存在）
Source: "*.xlsx"; DestDir: "{app}\examples"; Flags: ignoreversion external skipifsourcedoesntexist
Source: "*.xls"; DestDir: "{app}\examples"; Flags: ignoreversion external skipifsourcedoesntexist

[Icons]
; 程序组图标
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\使用说明"; Filename: "{app}\使用说明.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; 桌面图标
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

; 快速启动图标
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: quicklaunchicon

; 开始菜单图标
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startmenuicon

[Run]
; 安装完成后运行程序
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

[UninstallDelete]
; 卸载时删除的文件和目录
Type: filesandordirs; Name: "{app}"
Type: files; Name: "{autodesktop}\{#MyAppName}.lnk"
Type: files; Name: "{autoprograms}\{#MyAppName}.lnk"

[Registry]
; 注册表项（用于程序识别和卸载）
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "DisplayName"; ValueData: "{#MyAppName}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#MyAppVersion}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "Publisher"; ValueData: "{#MyAppPublisher}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{#MyAppURL}"

[Code]
// 自定义安装逻辑
function InitializeSetup(): Boolean;
begin
  Result := True;
  // 可以在这里添加额外的初始化检查
end;

// 检查系统要求
function CheckSystemRequirements(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  if Version.Major < 10 then
  begin
    MsgBox('本软件需要 Windows 10 或更高版本。', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

// 在显示许可协议前进行系统检查
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = wpLicense then
  begin
    if not CheckSystemRequirements() then
    begin
      Result := True;
      WizardForm.Close;
    end;
  end;
end;
