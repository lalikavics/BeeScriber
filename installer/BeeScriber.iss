; BeeScriber installer (Inno Setup 6). Built by installer\build.ps1, which passes AppVersion, Src (the prepared
; program folder with the bundled Python) and Root (the source folder).
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Src
  #define Src "..\build\dist"
#endif
#ifndef Root
  #define Root ".."
#endif
#define AppName "BeeScriber"
#define AppExe "BeeScriber.exe"

[Setup]
AppId={{DD466B09-C69A-4221-B0B6-CAC2FC489EF1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Lalikavics
AppPublisherURL=https://github.com/lalikavics/BeeScriber
AppSupportURL=https://github.com/lalikavics/BeeScriber/issues
AppUpdatesURL=https://github.com/lalikavics/BeeScriber/releases
AppCopyright=Copyright (C) 2026 Lalikavics - GNU GPL v3.0
; per-user install: no administrator rights needed, and the program can add the CUDA libraries and the
; speaker add-on to its own Python later
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile={#Root}\app\beescriber\ui\logo.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputBaseFilename={#AppName}-{#AppVersion}-setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
; the Whisper model (1.6 GB) and, with an NVIDIA card, the CUDA libraries (1.3 GB) are downloaded at the first start
ExtraDiskSpaceRequired=3200000000
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "notice-en.txt"
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"; InfoBeforeFile: "notice-hu.txt"

[Types]
Name: "standard"; Description: "{cm:TypeStandard}"
Name: "full"; Description: "{cm:TypeFull}"
Name: "custom"; Description: "{cm:TypeCustom}"; Flags: iscustom

[Components]
Name: "main"; Description: "{cm:CompMain}"; Types: standard full custom; Flags: fixed
Name: "speakers"; Description: "{cm:CompSpeakers}"; Types: full; ExtraDiskSpace: 5500000000

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "Lalikavics.BeeScriber"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; AppUserModelID: "Lalikavics.BeeScriber"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
; an update replaces the program files; the downloaded CUDA libraries / add-on in python\ are kept
Type: filesandordirs; Name: "{app}\app"

[UninstallDelete]
; packages added after the installation (CUDA libraries, speaker add-on) and the compiled program files
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\app"
Type: files; Name: "{app}\install.json"

[CustomMessages]
english.TypeStandard=Standard
english.TypeFull=Standard + speaker recognition
english.TypeCustom=Custom
english.CompMain=BeeScriber (required)
english.CompSpeakers=Speaker recognition add-on (optional, about 3 GB extra download)
english.SpkTitle=Speaker recognition add-on
english.SpkSub=A few extra steps are needed. You can also add it later in the app.
english.SpkText=With this add-on BeeScriber can mark who is speaking ("Speaker 1:", "Speaker 2:"). It runs on this PC, but it needs a free Hugging Face access key, because the speaker model may only be downloaded after you accept its terms.%n%nWhat you will need to do:%n%n1.  Create a free account on huggingface.co (if you do not have one).%n2.  Open the model page pyannote/speaker-diarization-community-1 and accept its terms (one click).%n3.  Create an access token of type "Read" in your Hugging Face settings.%n4.  At the first start BeeScriber downloads the add-on (PyTorch and pyannote, about 3 GB), then opens a short guide with these links, where you paste the key.%n%nThe key is stored only on this computer. If you do not want this now, go back and choose "Standard" - you can add the add-on later from the settings.
english.UninstData=Also delete the downloaded model, settings, history and access key (%1)?%n%nYour transcripts are not deleted.
english.NoWebView=BeeScriber needs the Microsoft Edge WebView2 Runtime, which seems to be missing on this PC.%n%nIt is free and usually already installed with Windows 10 / 11. Open the download page now?
hungarian.TypeStandard=Normál
hungarian.TypeFull=Normál + beszélők felismerése
hungarian.TypeCustom=Egyéni
hungarian.CompMain=BeeScriber (kötelező)
hungarian.CompSpeakers=Beszélők felismerése kiegészítő (nem kötelező, kb. 3 GB további letöltés)
hungarian.SpkTitle=Beszélők felismerése kiegészítő
hungarian.SpkSub=Ehhez néhány további lépés kell. Később a programban is hozzáadhatod.
hungarian.SpkText=Ezzel a kiegészítővel a BeeScriber jelölni tudja, ki beszél („1. beszélő:”, „2. beszélő:”). A gépeden fut, de ingyenes Hugging Face hozzáférési kulcs kell hozzá, mert a beszélőmodellt csak a feltételei elfogadása után lehet letölteni.%n%nEzt kell majd megtenned:%n%n1.  Hozz létre ingyenes fiókot a huggingface.co oldalon (ha még nincs).%n2.  Nyisd meg a pyannote/speaker-diarization-community-1 modell oldalát, és fogadd el a feltételeit (egy kattintás).%n3.  A Hugging Face beállításaiban hozz létre egy „Read” típusú hozzáférési kulcsot (token).%n4.  Az első indításkor a BeeScriber letölti a kiegészítőt (PyTorch és pyannote, kb. 3 GB), majd megnyit egy rövid útmutatót ezekkel a linkekkel, ahová a kulcsot beillesztheted.%n%nA kulcs csak ezen a gépen tárolódik. Ha most nem szeretnéd, lépj vissza, és válaszd a „Normál” telepítést – a kiegészítőt később a beállításokban is hozzáadhatod.
hungarian.UninstData=Töröljem a letöltött modellt, a beállításokat, az előzményeket és a hozzáférési kulcsot is (%1)?%n%nAz átiratok nem törlődnek.
hungarian.NoWebView=A BeeScriberhez a Microsoft Edge WebView2 futtatókörnyezet kell, ami úgy tűnik, hiányzik erről a gépről.%n%nIngyenes, és Windows 10 / 11 alatt általában már telepítve van. Megnyissam most a letöltési oldalt?

[Code]
var
  SpkPage: TOutputMsgWizardPage;

function HasWebView2: Boolean;
var
  V: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0'));
end;

procedure InitializeWizard;
begin
  SpkPage := CreateOutputMsgPage(wpSelectComponents, CustomMessage('SpkTitle'), CustomMessage('SpkSub'),
    CustomMessage('SpkText'));
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = SpkPage.ID) and not WizardIsComponentSelected('speakers');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
  Opt: String;
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsComponentSelected('speakers') then Opt := 'true' else Opt := 'false';
    SaveStringToFile(ExpandConstant('{app}\install.json'), '{"speakers": ' + Opt + '}', False);
    if (not WizardSilent) and (not HasWebView2) then
      if MsgBox(CustomMessage('NoWebView'), mbConfirmation, MB_YESNO) = IDYES then
        ShellExec('open', 'https://developer.microsoft.com/microsoft-edge/webview2/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Data: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Data := ExpandConstant('{localappdata}\BeeScriber');
    if DirExists(Data) and (not UninstallSilent) then
      if MsgBox(FmtMessage(CustomMessage('UninstData'), [Data]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Data, True, True, True);
  end;
end;
