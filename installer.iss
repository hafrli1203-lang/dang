; Inno Setup Script — 당근 광고 기획 도우미
; https://jrsoftware.org/isinfo.php
;
; 사전 조건:
;   1. python build.py 로 dist/당근광고도우미/ 빌드 완료
;   2. Inno Setup 6 설치: https://jrsoftware.org/isdl.php
;
; 빌드:
;   ISCC installer.iss
;   또는 Inno Setup Compiler GUI에서 이 파일 열기 → Compile

#define MyAppName      "당근 광고 기획 도우미"
#define MyAppNameEN    "DaangnAdReporter"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "이프컴퍼니"
#define MyAppURL       "https://github.com/hafrli1203-lang/dang"
#define MyAppExeName   "당근광고도우미.exe"
#define BuildDir       "dist\당근광고도우미"

[Setup]
AppId={{B226DDC9-CC73-42D2-BB7C-5643C7E24005}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppNameEN}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=당근광고도우미_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app_icon.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application files from PyInstaller onedir output
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; .env template — user can copy to .env and edit
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion
; Icon file for shortcuts
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
{ === .env 설정 페이지 === }

var
  EnvPage: TWizardPage;
  AnthropicKeyEdit: TNewEdit;
  OpenaiKeyEdit: TNewEdit;

procedure InitializeWizard;
begin
  { API 키 입력 페이지 추가 }
  EnvPage := CreateCustomPage(
    wpSelectTasks,
    'API 키 설정',
    'AI 기능을 사용하려면 API 키를 입력하세요. (나중에 .env 파일에서 수정 가능)'
  );

  { Anthropic API Key }
  with TNewStaticText.Create(EnvPage) do
  begin
    Parent := EnvPage.Surface;
    Caption := 'Anthropic API Key (Claude):';
    Left := 0;
    Top := 12;
  end;

  AnthropicKeyEdit := TNewEdit.Create(EnvPage);
  with AnthropicKeyEdit do
  begin
    Parent := EnvPage.Surface;
    Left := 0;
    Top := 32;
    Width := EnvPage.SurfaceWidth;
    Text := '';
  end;

  { OpenAI API Key }
  with TNewStaticText.Create(EnvPage) do
  begin
    Parent := EnvPage.Surface;
    Caption := 'OpenAI API Key (GPT / 이미지):';
    Left := 0;
    Top := 72;
  end;

  OpenaiKeyEdit := TNewEdit.Create(EnvPage);
  with OpenaiKeyEdit do
  begin
    Parent := EnvPage.Surface;
    Left := 0;
    Top := 92;
    Width := EnvPage.SurfaceWidth;
    Text := '';
  end;

  with TNewStaticText.Create(EnvPage) do
  begin
    Parent := EnvPage.Surface;
    Caption := '* 비워두면 해당 AI 엔진을 사용할 수 없습니다.' + #13#10 +
               '* 설치 후 %LOCALAPPDATA%\daangn_ad_reporter\.env 에서 수정할 수 있습니다.';
    Left := 0;
    Top := 132;
    Font.Color := clGray;
    Font.Size := 8;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvContent: String;
  EnvPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(ExpandConstant('{localappdata}\daangn_ad_reporter'));
    EnvPath := ExpandConstant('{localappdata}\daangn_ad_reporter\.env');
    EnvContent :=
      '# 당근 광고 기획 도우미 — 환경 설정' + #13#10 +
      '#' + #13#10 +
      '# API 키를 입력하세요. 최소 1개 이상 필요합니다.' + #13#10 +
      #13#10 +
      'ANTHROPIC_API_KEY=' + AnthropicKeyEdit.Text + #13#10 +
      'OPENAI_API_KEY=' + OpenaiKeyEdit.Text + #13#10 +
      #13#10 +
      '# 모델 설정 (기본값 사용 시 비워두세요)' + #13#10 +
      '# CLAUDE_MODEL=claude-opus-4-6' + #13#10 +
      '# OPENAI_MODEL=gpt-4o' + #13#10 +
      '# OPENAI_IMAGE_MODEL=gpt-image-2' + #13#10 +
      #13#10 +
      '# NiceGUI 저장소 암호' + #13#10 +
      'STORAGE_SECRET=daangn-reporter-secret-' + GetDateTimeString('yyyymmdd', #0, #0) + #13#10;

    { 기존 .env가 있으면 덮어쓰지 않음 }
    if not FileExists(EnvPath) then
      SaveStringToFile(EnvPath, EnvContent, False)
    else if (AnthropicKeyEdit.Text <> '') or (OpenaiKeyEdit.Text <> '') then
      { 키를 입력한 경우에만 새로 저장 }
      SaveStringToFile(EnvPath, EnvContent, False);
  end;
end;
