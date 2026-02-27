#ifndef RepoRoot
#define RepoRoot ".."
#endif

#ifndef OutputDir
#define OutputDir "dist"
#endif

#define AppName "Vimo"
#define AppVersion "1.0.0"
#define AppPublisher "Vimo"
#define AppExeName "Vimo.exe"

[Setup]
AppId={{5F9412B4-0728-4DB0-9708-F592256FE7CC}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Vimo
DefaultGroupName=Vimo
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=VimoSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\vimo\dist\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#RepoRoot}\setup.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\uninstall.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\how_to_install.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#RepoRoot}\server\*"; DestDir: "{app}\server"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "node_modules\*,storage\*,.git\*"
Source: "{#RepoRoot}\vimo\dist\Vimo.exe"; DestDir: "{app}\vimo\dist"; Flags: ignoreversion
Source: "{#RepoRoot}\vimo\core\connection.example.json"; DestDir: "{app}\vimo\core"; Flags: ignoreversion

[Icons]
Name: "{group}\Vimo"; Filename: "{app}\vimo\dist\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Vimo Server"; Filename: "cmd.exe"; Parameters: "/k cd /d ""{app}\server"" && npm run start"; WorkingDir: "{app}\server"
Name: "{group}\Vimo Bootstrap"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\setup.ps1"" -Broker local -ForceEnv -SkipBuild -NonInteractive"; WorkingDir: "{app}"
Name: "{group}\Uninstall Vimo Data"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\uninstall.ps1"""; WorkingDir: "{app}"
Name: "{autodesktop}\Vimo"; Filename: "{app}\vimo\dist\{#AppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\setup.ps1"" -Broker local -ForceEnv -SkipBuild -NonInteractive"; Description: "Run Vimo Bootstrap now"; Flags: postinstall nowait skipifsilent
