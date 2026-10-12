; Windows installer for the desktop build: one ScanpathStudio-…-setup.exe in
; place of "extract the .zip, find the .exe". It wraps PyInstaller's onedir
; folder unchanged — the zip stays a release asset beside it.
;
; Built by .github/workflows/desktop.yml after the smoke test:
;   ISCC.exe /DAppVersion=<version> /DNumericVersion=<x.y.z> /DSourceDir=<abs dist\ScanpathStudio>
;            /DOutputDir=<dir> /DOutputBaseFilename=<name> desktop\windows_installer.iss
;
; Per-user, no admin prompt: installs to %LOCALAPPDATA%\Programs\Scanpath Studio,
; adds a Start-menu entry and an "Apps" uninstall entry. The datasets and
; settings the app saves (ENG-26) live outside {app} and survive an uninstall.

#ifndef AppVersion
  #error Pass /DAppVersion=<version>
#endif
#ifndef NumericVersion
  #error Pass /DNumericVersion=<x.y.z> (Windows file versions are integers only)
#endif
#ifndef SourceDir
  #error Pass /DSourceDir=<absolute path to dist\ScanpathStudio>
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "ScanpathStudio-windows-x86_64-setup"
#endif

[Setup]
; Never change AppId: it is how a newer installer finds and upgrades this one.
AppId={{6F1C9A52-3B7E-4D21-9C8A-5E2F4B7D1A93}
AppName=Scanpath Studio
AppVersion={#AppVersion}
VersionInfoVersion={#NumericVersion}
AppVerName=Scanpath Studio {#AppVersion}
AppPublisher=Scanpath Studio contributors
AppPublisherURL=https://github.com/lacclab/scanpath-studio
AppSupportURL=https://github.com/lacclab/scanpath-studio/issues
AppUpdatesURL=https://github.com/lacclab/scanpath-studio/releases/latest
DefaultDirName={autopf}\Scanpath Studio
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icons\icon.ico
UninstallDisplayIcon={app}\ScanpathStudio.exe
UninstallDisplayName=Scanpath Studio
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

; An upgrade replaces the bundle rather than layering on top of it: a native
; module the previous version shipped and this one dropped would otherwise
; stay on disk, where Python could still import it.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Scanpath Studio"; Filename: "{app}\ScanpathStudio.exe"
Name: "{autodesktop}\Scanpath Studio"; Filename: "{app}\ScanpathStudio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ScanpathStudio.exe"; Description: "{cm:LaunchProgram,Scanpath Studio}"; Flags: nowait postinstall skipifsilent

; Anything written into the bundle after install (an in-place update, a cache
; file) was never recorded by the installer; without this the uninstall leaves
; a half-empty _internal folder behind.
[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
