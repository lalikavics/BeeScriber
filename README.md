<p align="center"><img src="app/beescriber/ui/logo.png" width="96" alt="BeeScriber"></p>

<h1 align="center">BeeScriber</h1>

<p align="center"><b>YouTube videos, whole playlists and your own audio / video files → text, entirely on your own PC.</b><br>
Free · local · Whisper on your GPU · Windows 10 / 11</p>

<p align="center"><a href="#magyarul">Magyarul lent ↓</a></p>

---

BeeScriber streams the audio (videos are never downloaded as files), runs OpenAI's Whisper *large-v3-turbo* model on your NVIDIA graphics card and writes clean transcripts. On a mid-range card (RTX 3060 Ti) an hour of speech takes about 2–3 minutes. Your audio and transcripts are not sent anywhere.

## Features
- **Sources:** videos, playlists or channels (one link per line), or audio / video files (MP3, WAV, M4A, FLAC, OGG, OPUS, MP4, MKV, WEBM, MOV, …). Links can be picked up from the clipboard automatically.
- **Playlists:** untick the videos you don't need, filter by title; already transcribed videos are recognised.
- **Queue:** drag-and-drop order, pause / resume per video **and in the middle of a video** – closing the app keeps the progress. Built for long runs (hundreds of videos).
- **Robust:** a failing video (private, deleted, bot check) never stops the queue; network drops are retried and continue where they stopped.
- **Live preview** of the text while it is being written, with progress and time left; GPU / VRAM / CPU meters and an adjustable GPU load limit.
- **Clean text:** punctuation guard and clean-up of Whisper's repetition loops.
- **Outputs:** TXT (paragraphs, one sentence per line or continuous; optional timestamps and title header), SRT, VTT, HTML, PDF, DOCX. File name templates, a folder per playlist, re-export later in other formats.
- **Speaker recognition (optional add-on):** "Speaker 1:", "Speaker 2:" … with pyannote, also running locally.
- Automatic language detection (99 languages), model choice (large-v3-turbo, large-v3, medium, small, base or your own CTranslate2 model), cookies for age-restricted or members-only videos.
- English and Hungarian interface.

## Install
1. Download **`BeeScriber-<version>-setup.exe`** from [Releases](https://github.com/lalikavics/BeeScriber/releases) and run it. No administrator rights and no Python needed.
2. Choose **Standard**, or **Standard + speaker recognition** if you want speaker labels (see below).
3. At the first start BeeScriber downloads the remaining components once, with one progress bar: yt-dlp, FFmpeg, Deno, the Whisper model (1.6 GB) and, with an NVIDIA card, the CUDA libraries (about 1.3 GB).

**Requirements:** Windows 10 / 11 64-bit · NVIDIA GPU with 4 GB+ memory recommended (the CPU works too, but much slower) · about 4 GB free space (7 GB with the speaker add-on) · Microsoft Edge WebView2 Runtime (part of Windows 11 and up-to-date Windows 10).

### Speaker recognition add-on
The speaker model is free, but it may only be downloaded after you accept its terms, so it needs a free Hugging Face access key:
1. Create a free account on [huggingface.co](https://huggingface.co/join).
2. Accept the terms on the [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) model page.
3. Create an access token of type **Read** in [your settings](https://huggingface.co/settings/tokens).
4. Paste it into BeeScriber (the app opens a short guide for this). The key is stored only on your computer.

You can also add the add-on later: *Settings → Add-on setup*.

## Development
Python 3.12, Windows.
```bat
py -3.12 -m venv tools\venv
tools\venv\Scripts\pip install -r installer\requirements.txt nvidia-cublas-cu12 nvidia-cudnn-cu12
BeeScriber.bat                  :: start (the first start downloads the tools and the model)
BeeScriber-debug.bat            :: with a console and the developer tools (F12)
cd app && ..\tools\venv\Scripts\python -m beescriber.cli selftest
```
Build the installer: `powershell -ExecutionPolicy Bypass -File installer\build.ps1` (needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)). GitHub Actions builds it for every `v*` tag.

## Credits
Created by **Lalikavics**.

BeeScriber is a front end; the actual work is done by excellent projects of others, which are **not part of BeeScriber** and are used under their own licences: [Whisper](https://github.com/openai/whisper) (OpenAI, MIT) · [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (SYSTRAN, MIT) · [CTranslate2](https://github.com/OpenNMT/CTranslate2) (MIT) · [faster-whisper-large-v3-turbo](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo) (Mobius Labs, MIT) · [pyannote.audio](https://github.com/pyannote/pyannote-audio) and [speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) (MIT / CC BY 4.0) · [PyTorch](https://pytorch.org) (BSD) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense) · [FFmpeg](https://ffmpeg.org) (LGPL/GPL) · [Deno](https://deno.com) (MIT) · [pywebview](https://pywebview.flowrl.com) (BSD) · ReportLab (BSD) · python-docx (MIT).

Enjoy it? You can [buy me a coffee ☕](https://buymeacoffee.com/lalikavics) – never required, and nothing changes either way: BeeScriber is and stays completely free, with no paid version and no locked features.

## Legal notice
- **What belongs to whom.** Only the program itself (source code, user interface, name and logo) is the work of the author. The models, libraries and tools listed above, and every video, audio file and transcript you process, belong to their respective owners.
- **Independent project.** BeeScriber is not affiliated with, sponsored or endorsed by YouTube, Google, OpenAI, Hugging Face or pyannote. Their names and trademarks belong to their owners and are used here only to describe compatibility.
- **Your responsibility.** You decide what you transcribe and how you use the results, and you alone are responsible for it. Transcribe only content you have the right to use, and comply with copyright law, the terms of service of the sites you use (including YouTube's) and data protection law – transcripts and speaker labels may contain personal data.
- **Your data.** No telemetry; nothing is collected. Settings, history, transcripts, cookies and access keys stay on your computer.
- **Accuracy.** Automatic transcripts and speaker labels can contain errors. Check them before you rely on them or publish them.
- **No warranty.** Provided "as is", without warranty of any kind; to the fullest extent permitted by law the author is not liable for any damage arising from its use. See [LICENSE](LICENSE) (GNU GPL v3.0, sections 15–17).

---

## Magyarul

A **BeeScriber** YouTube-videókat, teljes lejátszási listákat és csatornákat, valamint saját hang- és videófájlokat alakít szöveggé, teljesen a saját gépeden. A hangot letöltés nélkül, folyamként dolgozza fel (a videó nem mentődik fájlként), a Whisper *large-v3-turbo* modell a videókártyán fut. Közepes kártyán (RTX 3060 Ti) egy óra beszéd kb. 2–3 perc. A hang és az átiratok nem kerülnek fel sehová.

**Tudja:** lejátszási lista jelölőnégyzetekkel és cím szerinti szűréssel; a már átírt videók felismerése; sor húzással rendezve, szünet és folytatás videónként és videó közben is (a program bezárása után is); a hibás videó nem állítja meg a sort; élő előnézet; GPU / VRAM / CPU kijelző és GPU-terhelés korlát; írásjel-őr és ismétlődés-szűrés; TXT / SRT / VTT / HTML / PDF / DOCX kimenet; beszélők jelölése (kiegészítő); automatikus nyelvfelismerés; sütik korhatáros vagy csak tagoknak szóló videókhoz; magyar és angol felület.

### Telepítés
1. Töltsd le a **`BeeScriber-<verzió>-setup.exe`** fájlt a [Releases](https://github.com/lalikavics/BeeScriber/releases) oldalról, és futtasd. Rendszergazdai jog és Python nem kell.
2. Válaszd a **Normál**, vagy ha a beszélők jelölését is szeretnéd, a **Normál + beszélők felismerése** telepítést.
3. Az első indításkor a BeeScriber egyszer, egy folyamatjelzővel letölti a többi összetevőt: yt-dlp, FFmpeg, Deno, a Whisper modell (1,6 GB), és NVIDIA kártya esetén a CUDA-könyvtárak (kb. 1,3 GB).

**Rendszerigény:** Windows 10 / 11 64 bites · ajánlott NVIDIA videókártya legalább 4 GB memóriával (processzoron is fut, de jóval lassabban) · kb. 4 GB szabad hely (a beszélő-kiegészítővel 7 GB) · Microsoft Edge WebView2 (a Windows 11 és a frissített Windows 10 része).

### Beszélők felismerése (kiegészítő)
A beszélőmodell ingyenes, de csak a feltételei elfogadása után tölthető le, ezért ingyenes Hugging Face hozzáférési kulcs kell hozzá:
1. Hozz létre ingyenes fiókot a [huggingface.co](https://huggingface.co/join) oldalon.
2. Fogadd el a feltételeket a [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) modell oldalán.
3. A [beállításaidban](https://huggingface.co/settings/tokens) hozz létre egy **Read** típusú kulcsot (token).
4. Illeszd be a BeeScriberbe (a program ehhez rövid útmutatót nyit meg). A kulcs csak a gépeden tárolódik.

A kiegészítőt később is hozzáadhatod: *Beállítások → Kiegészítő beállítása*.

### Jogi nyilatkozat
- **Mi kié.** A szerző munkája kizárólag maga a program (forráskód, kezelőfelület, név és logó). A fent felsorolt modellek, könyvtárak és eszközök, valamint minden feldolgozott videó, hangfájl és átirat a jogosultjaik tulajdona.
- **Független projekt.** A BeeScriber nem áll kapcsolatban a YouTube-bal, a Google-lel, az OpenAI-jal, a Hugging Face-szel vagy a pyannote-tal, és ők nem is támogatják. A nevük és védjegyeik a tulajdonosaiké, és csak a kompatibilitás leírására szerepelnek.
- **A te felelősséged.** Te döntöd el, mit írsz át és hogyan használod fel az eredményt, és ezért egyedül te felelsz. Csak olyan tartalmat írj át, amelynek a felhasználására jogosult vagy, és tartsd be a szerzői jogot, a használt oldalak (köztük a YouTube) feltételeit és az adatvédelmi szabályokat – az átiratok és a beszélők jelölése személyes adatot tartalmazhat.
- **Az adataid.** Nincs telemetria, a program semmit nem gyűjt. A beállítások, az előzmények, az átiratok, a sütik és a kulcsok a gépeden maradnak.
- **Pontosság.** A gépi átirat és a beszélők jelölése tartalmazhat hibát; közzététel vagy felhasználás előtt ellenőrizd.
- **Nincs garancia.** A program „ahogy van” alapon, garancia nélkül érhető el; a jogszabályok által megengedett legteljesebb mértékben a szerző nem felel a használatából eredő károkért. Lásd: [LICENSE](LICENSE) (GNU GPL v3.0, 15–17. pont).

Készítette: **Lalikavics**. Tetszik? [Meghívhatsz egy kávéra ☕](https://buymeacoffee.com/lalikavics) – sosem kötelező, és semmi nem változik tőle: a BeeScriber ingyenes, és az is marad.

---

<sub><i>Developed with the help of Claude (Anthropic).</i></sub>
