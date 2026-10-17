#define MyAppName "TG_Coper"
#define MyAppVersion "4.8.1"
#define MyAppPublisher "TG_Coper"
#define MyAppExeName "TG_Coper.exe"

[Setup]
AppId={{7B29C14C-3A62-4EAF-9C4D-4A0D0E4C4811}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\TG_Coper
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=TG_Coper_Setup
SetupIconFile=TG_Coper.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
CloseApplications=force
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "dist\TG_Coper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TG_Coper"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{localappdata}\TG_Coper"
Name: "{autodesktop}\TG_Coper"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{localappdata}\TG_Coper"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить TG_Coper"; Flags: nowait postinstall skipifsilent
