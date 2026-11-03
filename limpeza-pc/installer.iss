; Instalador do LimpaOne (Inno Setup 6)
; Compile depois de gerar dist\LimpaOne.exe:  ISCC.exe /DMyAppVersion=3.0.0 installer.iss
#ifndef MyAppVersion
  #define MyAppVersion "3.0.0"
#endif
#define MyAppName "LimpaOne"
#define MyAppExe "LimpaOne.exe"

[Setup]
AppId={{6B0B6E1A-4C1E-4E52-9C5B-2F6A1D3C7E11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Sarzi Tecnologia
AppPublisherURL=https://limpaone.sarzitecnologia.com.br
AppSupportURL=https://github.com/gabrielsarzi/teste/issues
AppUpdatesURL=https://github.com/gabrielsarzi/teste/releases
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription=Instalador do LimpaOne
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
OutputDir=dist
OutputBaseFilename=LimpaOne-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\LimpaOne"
