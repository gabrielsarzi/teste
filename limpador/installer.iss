; Instalador do LimpaPC (Inno Setup 6) — compile depois de gerar dist\LimpaPC.exe
#define MyAppName "LimpaPC"
#define MyAppVersion "1.0.0"
#define MyAppExe "LimpaPC.exe"

[Setup]
AppId={{6B0B6E1A-4C1E-4E52-9C5B-2F6A1D3C7E11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=LimpaPC
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=LimpaPC-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExe}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppName} (administrador)"; Filename: "{app}\{#MyAppExe}"; Comment: "Abra com botão direito > Executar como administrador para limpar pastas do sistema"

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
