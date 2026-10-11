[Setup]
AppName=KeyFlow
AppVersion=1.2.0
DefaultDirName={autopf}\KeyFlow
DefaultGroupName=KeyFlow
OutputDir=Output
OutputBaseFilename=KeyFlowSetup
Compression=lzma
SolidCompression=yes
LicenseFile=eula.txt
SetupIconFile=assets\logo.ico
UninstallDisplayIcon={app}\KeyFlow.exe
WizardImageFile=assets\logo.bmp
WizardSmallImageFile=assets\logo.bmp

[Files]
Source: "dist\KeyFlow.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\logo.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\KeyFlow"; Filename: "{app}\KeyFlow.exe"
Name: "{commondesktop}\KeyFlow"; Filename: "{app}\KeyFlow.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
