[Setup]
AppId=LocalChatbot_LMStudio
AppName=Local Chatbot
AppVersion=1.0
AppPublisher=Local Chatbot
; Installs to Local AppData (no Admin rights required) or Program Files depending on user
DefaultDirName={autopf}\Local Chatbot
DefaultGroupName=Local Chatbot
OutputDir=dist_installer
OutputBaseFilename=LocalChatbot_Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\LMStudio_Chatbot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Local Chatbot"; Filename: "{app}\LMStudio_Chatbot.exe"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\Local Chatbot"; Filename: "{app}\LMStudio_Chatbot.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\LMStudio_Chatbot.exe"; Description: "{cm:LaunchProgram,Local Chatbot}"; Flags: nowait postinstall skipifsilent