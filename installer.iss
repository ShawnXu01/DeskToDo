; Inno Setup 安装脚本：选安装目录 + 开始菜单/桌面快捷方式 + 可选开机自启动
; 编译前需要先用 PyInstaller 把 dist\DeskToDo 目录打好（见 desktodo.spec）

#define MyAppName "DeskToDo"
#define MyAppVersion "1.6"
#define MyAppExeName "DeskToDo.exe"

[Setup]
AppId={{8F2C9C9C-2B9B-4B3C-9B2A-DESKTODO0001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=DeskToDo-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=deskcal\assets\images\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："
Name: "autostart"; Description: "开机自动启动 DeskToDo"; GroupDescription: "附加选项："

[Files]
Source: "dist\DeskToDo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DeskCal"; ValueData: """{app}\{#MyAppExeName}"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "安装完成后立即启动 DeskToDo"; Flags: nowait postinstall skipifsilent
