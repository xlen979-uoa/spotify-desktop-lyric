; Inno Setup 安装脚本（由 GitHub Actions 自动编译）
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8F3C2A51-6B7E-4D2B-9C1A-5E4F7A2B9D10}
AppName=Spotify Lyrics
AppVersion={#AppVersion}
AppPublisher=Cecilia
DefaultDirName={autopf}\SpotifyLyrics
DefaultGroupName=Spotify Lyrics
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=SpotifyLyrics-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\SpotifyLyrics.exe
Compression=lzma2
SolidCompression=yes
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "autostart"; Description: "Start automatically when Windows starts"; Flags: unchecked

[Files]
Source: "dist\SpotifyLyrics.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Spotify Lyrics"; Filename: "{app}\SpotifyLyrics.exe"
Name: "{group}\Uninstall Spotify Lyrics"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Spotify Lyrics"; Filename: "{app}\SpotifyLyrics.exe"; Tasks: desktopicon
Name: "{userstartup}\Spotify Lyrics"; Filename: "{app}\SpotifyLyrics.exe"; Tasks: autostart

[Run]
Filename: "{app}\SpotifyLyrics.exe"; Description: "Launch Spotify Lyrics"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im SpotifyLyrics.exe"; Flags: runhidden; RunOnceId: "KillApp"
