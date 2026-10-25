/* UI texts. English is the default and the fallback for every missing Hungarian key. */
const I18N = {
en: {
  diarize: 'Mark who speaks', diarizeHint: 'Optional add-on (pyannote, ~3 GB, local). A new paragraph starts with “Speaker 1:” at every change.',
  speakers: 'Number of speakers', spkAuto: 'Automatic', dSetupBtn: 'Add-on setup',
  dTitle: 'Speaker recognition – add-on', dStep1: '1. Download the add-on', dStep1Text: 'PyTorch and pyannote, about 3 GB, once. Everything runs on this PC.',
  dInstall: 'Download and install', dInstalling: 'Installing… ({0}/{1}) {2}', dInstalled: '✓ Installed',
  dNotInstallable: 'In this version the add-on is installed with the separate add-on pack.',
  dStep2: '2. Free Hugging Face access', dStep2Text: 'The authors of the model ask every user to accept its terms once:',
  dLinkJoin: 'Create a free account', dLinkModel: 'Open the model page and click “Agree and access repository”', dLinkToken: 'Create an access token (type: Read) and paste it here',
  dTokenPh: 'hf_…', dTokenPhSaved: 'A token is saved – paste a new one only to replace it', dCheck: 'Check', dChecking: 'Checking…', dTokOk: '✓ Token accepted – stored only on this PC.', dHasToken: '✓ A token is already saved.',
  dTok_invalid: 'Hugging Face did not accept this token. A token is shown only once, when it is created – create a new one (type: Read) and paste that.', dTok_terms: 'The token works and is saved, but the model terms are not accepted yet – open the model page, click “Agree and access repository”, then press Check again.',
  dTok_network: 'Hugging Face could not be reached. Check the internet connection.', dTok_unknown: 'The token could not be checked.',
  dEnable: 'Switch on', dNeedBoth: 'Both steps are needed first.',
  spkRunning: 'Recognising speakers…', spkDone: 'Speakers found: {0}', spkError: 'Speaker recognition failed – the transcript is saved without names.', spkUnavailable: 'Speaker recognition is on, but the add-on is not ready (Settings → Add-on setup).',
  coffee: 'Buy me a coffee', clipWatch: 'Load YouTube links from the clipboard automatically', clipLoaded: 'Link found on the clipboard – loading…',
  fmtList: 'Audio: MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, WMA, AIFF · Video: MP4, MKV, WEBM, MOV, AVI, M4V, WMV, FLV, MPG, TS',
  header: 'Title at the top of the text', gpuLimit: 'GPU load', gpuHint: 'Below 100% the GPU rests a little between pieces of work, so the PC stays smooth.',
  advanced: 'Advanced', cut: 'Cut', copyC: 'Copy', paste: 'Paste', selectAll: 'Select all',
  wMin: 'Minimise', wMax: 'Maximise', wRestore: 'Restore', wClose: 'Close',
  brandSub: 'Transcribe YouTube & media', byline: 'Created by', about: 'About', start: 'Start', resume: 'Continue',
  pause: 'Pause', pausing: 'Pausing…',
  // status
  stIdle: 'Ready', stWorking: 'Working', stLoading: 'Loading model…', stDownloadModel: 'Downloading model…',
  stEngineErr: 'Engine error', stNoTools: 'Tools missing',
  // cards
  c1: 'Source', c2: 'Output', c3: 'Settings',
  srcPh: 'Paste YouTube links – videos, playlists or channels, one per line',
  load: 'Load', loading: 'Loading…', loadingList: 'Loading the list…', addFiles: 'Add files…', dropHint: 'or drop audio / video files anywhere on the window',
  folder: 'Folder', browse: 'Browse…', open: 'Open', formats: 'Formats', txtLayout: 'Text layout',
  lay_paragraphs: 'Paragraphs', lay_sentences: 'One sentence per line', lay_plain: 'Continuous text',
  timestamps: 'Timestamps', timestampsHint: 'In TXT, HTML, PDF and DOCX (SRT / VTT always have them)',
  plSub: 'Separate folder per playlist', names: 'File names', nameTpl: 'Single videos and files', plNameTpl: 'Playlist videos',
  nameHint: 'Fields: {title} {index:03} {channel} {playlist} {id} {date}',
  model: 'Model', modelHint: 'large-v3-turbo: best speed / quality. large-v3: a little more accurate, ~3× slower.',
  customModel: 'Own model folder (CTranslate2)', language: 'Language', lang_auto: 'Detect automatically',
  device: 'Processor', dev_auto: 'Automatic (GPU if available)', dev_cuda: 'GPU (NVIDIA)', dev_cpu: 'CPU (slow)',
  guard: 'Punctuation guard', guardHint: 'Re-does a section if Whisper dropped the punctuation (costs a few seconds).',
  cookies: 'Cookies', ck_none: 'None', ck_browser: 'From browser', ck_file: 'cookies.txt file',
  cookiesHint: 'Only needed for age-restricted / members videos or when YouTube asks to sign in. Firefox works best on Windows.',
  browser: 'Browser', updYt: 'Update yt-dlp', updating: 'Updating…', tools: 'Tools',
  // tabs
  tabList: 'Loaded', tabPreview: 'Live preview', tabHistory: 'History',
  // list
  listEmpty: 'Load a playlist or video in “Source”, or drop files here.\nYou can untick videos you don’t need before adding them to the queue.',
  filter: 'Filter by title…', all: 'All', none: 'None', notDone: 'Not transcribed yet', selected: '{0} selected · {1}',
  addQueue: 'Add to queue', addStart: 'Add and start', bothNote: 'This link points to a video inside a playlist. The whole playlist was loaded.',
  onlyVideo: 'Load only the video', videos: '{0} videos', clearList: 'Clear',
  b_done: 'transcribed', b_queue: 'in queue', b_unavailable: 'unavailable', b_members: 'members only', b_live: 'live / upcoming',
  // preview
  pvEmpty: 'The transcript appears here while it is being made.', autoscroll: 'Follow', copy: 'Copy', copied: 'Copied.',
  speed: '{0}× real time', left: '{0} left', redo: 'Punctuation fixed', lang: 'Language: {0}',
  // queue
  queue: 'Queue', qEmpty: 'The queue is empty.', qLeft: '{0} audio left · about {1}', retryAll: 'Retry failed',
  clearQueue: 'Remove waiting', pauseAfter: 'Pause after the current video', unfinished: '{0} unfinished from last time – press Continue.',
  s_queued: 'waiting', s_running: 'transcribing', s_paused: 'paused', s_error: 'error', s_done: 'done',
  jPause: 'Pause', jResume: 'Resume', jRemove: 'Remove', jRetry: 'Retry', jUp: 'Move up', jDown: 'Move down', jTop: 'To the top',
  // history
  hEmpty: 'Finished transcripts appear here. The app uses this list to recognise videos you already have.',
  hDelAll: 'Delete history', hDelConfirm: 'Delete {0} history entries? The transcript files on disk stay where they are.',
  hDel: 'Delete', folderBtn: 'Folder', export: 'Export…', exportTitle: 'Export again in other formats', exportDo: 'Export',
  exported: 'Exported: {0}', finished: 'Finished',
  // dialogs
  ok: 'OK', cancel: 'Cancel', close: 'Close', yes: 'Yes', confirm: 'Confirm',
  toolsMissing: 'Missing tools: {0}. They are downloaded once into the app folder (~150 MB).', toolsGet: 'Download',
  toolsDone: 'Tools are ready.', noneLoaded: 'Nothing new was loaded.', added: '{0} added to the queue.', addedNone: 'They are all in the queue already.',
  queueDone: 'Queue finished.', nothingSel: 'Nothing is selected.',
  // errors
  e_invalid: 'Not a link or file I can use', e_bot: 'YouTube asks to confirm you are not a bot – set cookies in Settings → Advanced.',
  e_private: 'Private video', e_members: 'Members-only video – needs cookies of a member account',
  e_age: 'Age-restricted – needs cookies of a signed-in account', e_live: 'Live or upcoming – try again when it has ended',
  e_js: 'YouTube changed something – try “Update yt-dlp”.', e_forbidden: 'YouTube refused the download (403) – update yt-dlp or set cookies.',
  e_cookies: 'Cookies could not be read – close the browser, or use a cookies.txt file.', e_unavailable: 'Video unavailable',
  e_network: 'Network problem', e_unknown: 'Unknown error', e_tools: 'yt-dlp / ffmpeg missing', e_no_audio: 'No audio in this source',
  e_incomplete: 'The download kept stopping – progress is saved, Retry continues.', e_no_speech: 'No speech was found',
  e_export: 'Could not write the files – check the folder.', e_engine: 'Speech engine error', e_internal: 'Internal error',
  e_file_missing: 'File not found', e_file_type: 'Not a supported audio / video file (see the list under “Add files”)',
  aboutTitle: 'About {0}',
},
hu: {
  diarize: 'Beszélők megkülönböztetése', diarizeHint: 'Választható kiegészítő (pyannote, ~3 GB, helyben fut). Minden beszélőváltásnál új bekezdés kezdődik, „1. beszélő:” jelöléssel.',
  speakers: 'Beszélők száma', spkAuto: 'Automatikus', dSetupBtn: 'Kiegészítő beállítása',
  dTitle: 'Beszélők felismerése – kiegészítő', dStep1: '1. A kiegészítő letöltése', dStep1Text: 'PyTorch és pyannote, kb. 3 GB, egyszer. Minden a gépeden fut.',
  dInstall: 'Letöltés és telepítés', dInstalling: 'Telepítés… ({0}/{1}) {2}', dInstalled: '✓ Telepítve',
  dNotInstallable: 'Ebben a változatban a kiegészítő a külön kiegészítő csomaggal telepíthető.',
  dStep2: '2. Ingyenes Hugging Face-hozzáférés', dStep2Text: 'A modell készítői minden felhasználótól egyszer kérik a feltételek elfogadását:',
  dLinkJoin: 'Ingyenes fiók létrehozása', dLinkModel: 'A modell oldalán kattints az „Agree and access repository” gombra', dLinkToken: 'Hozz létre egy hozzáférési kulcsot (típus: Read), és másold ide',
  dTokenPh: 'hf_…', dTokenPhSaved: 'Van mentett kulcs – csak csere esetén másolj be újat', dCheck: 'Ellenőrzés', dChecking: 'Ellenőrzés…', dTokOk: '✓ A kulcs elfogadva – csak ezen a gépen tárolódik.', dHasToken: '✓ Már van mentett kulcs.',
  dTok_invalid: 'A Hugging Face nem fogadta el ezt a kulcsot. A kulcs csak létrehozáskor látható egyszer – hozz létre egy újat (típus: Read), és azt másold be.', dTok_terms: 'A kulcs jó és el van mentve, de a modell feltételei még nincsenek elfogadva – nyisd meg a modell oldalát, kattints az „Agree and access repository” gombra, majd nyomd meg újra az Ellenőrzést.',
  dTok_network: 'A Hugging Face nem érhető el. Ellenőrizd az internetkapcsolatot.', dTok_unknown: 'A kulcsot nem sikerült ellenőrizni.',
  dEnable: 'Bekapcsolás', dNeedBoth: 'Előbb mindkét lépés kell.',
  spkRunning: 'Beszélők felismerése…', spkDone: 'Felismert beszélők: {0}', spkError: 'A beszélők felismerése nem sikerült – az átirat nevek nélkül mentődött.', spkUnavailable: 'A beszélők megkülönböztetése be van kapcsolva, de a kiegészítő nincs kész (Beállítások → Kiegészítő beállítása).',
  coffee: 'Buy me a coffee', clipWatch: 'A vágólapra másolt YouTube-linkek automatikus betöltése', clipLoaded: 'Link a vágólapon – betöltés…',
  fmtList: 'Hang: MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, WMA, AIFF · Videó: MP4, MKV, WEBM, MOV, AVI, M4V, WMV, FLV, MPG, TS',
  header: 'Cím a szöveg elején', gpuLimit: 'GPU-terhelés', gpuHint: '100% alatt a videókártya a munkadarabok között kicsit pihen, így a gép gördülékeny marad.',
  advanced: 'Haladó', cut: 'Kivágás', copyC: 'Másolás', paste: 'Beillesztés', selectAll: 'Mindent kijelöl',
  wMin: 'Kis méret', wMax: 'Teljes méret', wRestore: 'Előző méret', wClose: 'Bezárás',
  brandSub: 'YouTube és média átírása', byline: 'Készítette:', about: 'Névjegy', start: 'Indítás', resume: 'Folytatás',
  pause: 'Szünet', pausing: 'Megállítás…',
  stIdle: 'Kész', stWorking: 'Dolgozik', stLoading: 'Modell betöltése…', stDownloadModel: 'Modell letöltése…',
  stEngineErr: 'Motorhiba', stNoTools: 'Hiányzó eszközök',
  c1: 'Forrás', c2: 'Kimenet', c3: 'Beállítások',
  srcPh: 'Illessz be YouTube-linkeket – videó, lejátszási lista vagy csatorna, soronként egyet',
  load: 'Betöltés', loading: 'Betöltés…', loadingList: 'Lista betöltése…', addFiles: 'Fájlok hozzáadása…', dropHint: 'vagy húzz hang- / videófájlokat bárhová az ablakra',
  folder: 'Mappa', browse: 'Tallózás…', open: 'Megnyitás', formats: 'Formátumok', txtLayout: 'Szöveg tördelése',
  lay_paragraphs: 'Bekezdések', lay_sentences: 'Soronként egy mondat', lay_plain: 'Folyó szöveg',
  timestamps: 'Időbélyegek', timestampsHint: 'TXT-ben, HTML-ben, PDF-ben és DOCX-ben (az SRT / VTT-ben mindig van)',
  plSub: 'Lejátszási listánként külön mappa', names: 'Fájlnevek', nameTpl: 'Egyes videók és fájlok', plNameTpl: 'Lejátszási lista videói',
  nameHint: 'Mezők: {title} {index:03} {channel} {playlist} {id} {date}',
  model: 'Modell', modelHint: 'large-v3-turbo: a legjobb sebesség / minőség. large-v3: kicsit pontosabb, ~3× lassabb.',
  customModel: 'Saját modell mappa (CTranslate2)', language: 'Nyelv', lang_auto: 'Automatikus felismerés',
  device: 'Feldolgozó', dev_auto: 'Automatikus (GPU, ha van)', dev_cuda: 'GPU (NVIDIA)', dev_cpu: 'CPU (lassú)',
  guard: 'Írásjel-őr', guardHint: 'Újra átír egy részt, ha a Whisper elhagyta az írásjeleket (pár másodperc).',
  cookies: 'Sütik (cookie)', ck_none: 'Nincs', ck_browser: 'Böngészőből', ck_file: 'cookies.txt fájl',
  cookiesHint: 'Csak korhatáros / tagoknak szóló videókhoz kell, vagy ha a YouTube bejelentkezést kér. Windowson a Firefox működik a legjobban.',
  browser: 'Böngésző', updYt: 'yt-dlp frissítése', updating: 'Frissítés…', tools: 'Eszközök',
  tabList: 'Betöltve', tabPreview: 'Élő előnézet', tabHistory: 'Előzmények',
  listEmpty: 'Tölts be egy lejátszási listát vagy videót a „Forrás” részben, vagy húzz ide fájlokat.\nA sorba tétel előtt kiveheted a pipát azokból a videókból, amelyek nem kellenek.',
  filter: 'Szűrés cím szerint…', all: 'Mind', none: 'Egyik sem', notDone: 'Még nincs átirata', selected: '{0} kijelölve · {1}',
  addQueue: 'Sorba tétel', addStart: 'Sorba tétel és indítás', bothNote: 'Ez a link egy lejátszási lista egyik videójára mutat. A teljes listát töltöttem be.',
  onlyVideo: 'Csak a videó betöltése', videos: '{0} videó', clearList: 'Ürítés',
  b_done: 'van átirata', b_queue: 'sorban', b_unavailable: 'nem elérhető', b_members: 'csak tagoknak', b_live: 'élő / közelgő',
  pvEmpty: 'Az átirat itt jelenik meg, miközben készül.', autoscroll: 'Követés', copy: 'Másolás', copied: 'Kimásolva.',
  speed: '{0}× valós idő', left: 'még {0}', redo: 'Írásjelek javítva', lang: 'Nyelv: {0}',
  queue: 'Sor', qEmpty: 'A sor üres.', qLeft: 'még {0} hang · kb. {1}', retryAll: 'Hibásak újra',
  clearQueue: 'Várakozók törlése', pauseAfter: 'Szünet az aktuális videó után', unfinished: '{0} befejezetlen a legutóbbiból – nyomd meg a Folytatást.',
  s_queued: 'vár', s_running: 'átírás', s_paused: 'szünetel', s_error: 'hiba', s_done: 'kész',
  jPause: 'Szünet', jResume: 'Folytatás', jRemove: 'Törlés', jRetry: 'Újra', jUp: 'Feljebb', jDown: 'Lejjebb', jTop: 'Az elejére',
  hEmpty: 'Itt jelennek meg az elkészült átiratok. A program ebből ismeri fel, melyik videónak van már átirata.',
  hDelAll: 'Előzmények törlése', hDelConfirm: 'Törlöd a(z) {0} előzményt? A lemezen lévő átiratfájlok megmaradnak.',
  hDel: 'Törlés', folderBtn: 'Mappa', export: 'Exportálás…', exportTitle: 'Exportálás újra más formátumokba', exportDo: 'Exportálás',
  exported: 'Elkészült: {0}', finished: 'Elkészült',
  ok: 'OK', cancel: 'Mégse', close: 'Bezárás', yes: 'Igen', confirm: 'Megerősítés',
  toolsMissing: 'Hiányzó eszközök: {0}. Egyszer kell letölteni őket az app mappájába (~150 MB).', toolsGet: 'Letöltés',
  toolsDone: 'Az eszközök készen állnak.', noneLoaded: 'Nem töltődött be semmi új.', added: '{0} elem a sorba került.', addedNone: 'Mind benne van már a sorban.',
  queueDone: 'A sor végére értem.', nothingSel: 'Nincs kijelölve semmi.',
  e_invalid: 'Ez nem használható link vagy fájl', e_bot: 'A YouTube botellenőrzést kér – állíts be sütiket: Beállítások → Haladó.',
  e_private: 'Privát videó', e_members: 'Csak tagoknak – egy tag fiók sütijei kellenek',
  e_age: 'Korhatáros – bejelentkezett fiók sütijei kellenek', e_live: 'Élő vagy közelgő adás – próbáld újra, ha véget ért',
  e_js: 'A YouTube változtatott valamit – próbáld a „yt-dlp frissítése” gombot.', e_forbidden: 'A YouTube megtagadta a letöltést (403) – frissítsd a yt-dlp-t, vagy állíts be sütiket.',
  e_cookies: 'A sütik nem olvashatók – zárd be a böngészőt, vagy használj cookies.txt fájlt.', e_unavailable: 'A videó nem elérhető',
  e_network: 'Hálózati hiba', e_unknown: 'Ismeretlen hiba', e_tools: 'Hiányzik a yt-dlp / ffmpeg', e_no_audio: 'Nincs hang ebben a forrásban',
  e_incomplete: 'A letöltés többször megszakadt – a haladás mentve, az Újra folytatja.', e_no_speech: 'Nem találtam beszédet',
  e_export: 'Nem tudtam a fájlokat kiírni – ellenőrizd a mappát.', e_engine: 'Beszédfelismerő hiba', e_internal: 'Belső hiba',
  e_file_missing: 'A fájl nem található', e_file_type: 'Nem támogatott fájltípus (a lista a „Fájlok hozzáadása” alatt látható)',
  aboutTitle: 'Névjegy – {0}',
}};

const LANG_NAMES = {en: 'English', hu: 'Magyar', de: 'Deutsch', fr: 'Français', es: 'Español', it: 'Italiano',
  pt: 'Português', nl: 'Nederlands', pl: 'Polski', ro: 'Română', sk: 'Slovenčina', cs: 'Čeština', ru: 'Русский',
  uk: 'Українська', tr: 'Türkçe', ja: '日本語', zh: '中文', ko: '한국어', ar: 'العربية', hi: 'हिन्दी'};

const ABOUT = {
en: name => `<p><b>${name}</b> turns YouTube videos, whole playlists and your own audio or video files into text on your own computer. Speech recognition runs locally with the Whisper model on your graphics card (or on the processor). Your audio and transcripts are not sent to any server: the program only connects to the internet to stream the audio of the videos you add, and to download its components and models once. Videos are not saved as files – the audio is processed in memory.</p>
<p>Created by <b>Lalikavics</b>. Developed with the help of Claude (Anthropic). Version ${'{VER}'}. The program is free software under the <b>GNU GPL v3.0</b> licence.</p>
<h3>Support</h3>
<p>I code, draw and create, just for the fun of it. I'm a bit like a Renaissance polymath, just with internet access, visual skills and more bugs. 😄<br>Enjoy my free projects? You can <a href="#" data-url="{COFFEE}">buy me a coffee ☕ or a pizza 🍕</a>. It's never required, but always appreciated, and it keeps me creating more useful (or totally useless) things.</p>
<p><b>Nothing changes if you do, or if you don't.</b> ${name} is and stays completely free: no paid version, no locked features, no extra support or priority for supporters. A coffee is a voluntary thank-you, not a purchase.</p>
<h3>Built on</h3>
<p>${name} is a front end: the speech recognition itself is done by models and tools made by others. They are not part of the program; they belong to their authors and are used under their own licences:</p>
<ul>
<li><b>Whisper</b> speech recognition model – OpenAI (MIT); converted for faster-whisper by Mobius Labs (MIT)</li>
<li><b>faster-whisper</b> – SYSTRAN (MIT); <b>CTranslate2</b> – OpenNMT (MIT)</li>
<li>Speaker recognition add-on: <b>pyannote.audio</b> (MIT) and the <b>speaker-diarization-community-1</b> model (CC BY 4.0) – pyannote / Hervé Bredin and contributors; <b>PyTorch</b> (BSD)</li>
<li><b>yt-dlp</b> – the yt-dlp contributors (Unlicense); <b>Deno</b> – the Deno authors (MIT)</li>
<li><b>FFmpeg</b> – the FFmpeg developers (LGPL/GPL)</li>
<li><b>pywebview</b>, <b>ReportLab</b>, <b>python-docx</b> – their authors (BSD/MIT)</li>
</ul>
<h3>Legal notice</h3>
<p><b>What belongs to the author.</b> Only the program itself is the work of the author: its source code, its user interface, its name and its logo. Nothing else.</p>
<p><b>What does not.</b> The speech recognition and speaker models (Whisper, pyannote), the libraries and the tools listed above are not part of ${name} and were not made by its author. They are downloaded from their official sources, they belong to their authors, and their own licences and terms apply to them – some models (for example the pyannote speaker model) can only be used after you accept their terms with the provider yourself. The author claims no rights to them and gives no warranty for them. Every video, audio file and transcript you process also belongs to its own rights holders, not to the author.</p>
<p><b>Independence.</b> ${name} is an independent, non-commercial project. It is not affiliated with, sponsored or endorsed by YouTube, Google, OpenAI, Hugging Face, pyannote or any other company named here; their names and trademarks belong to their owners and are used only to describe compatibility.</p>
<p><b>Your responsibility.</b> You decide what you transcribe and how you use the results, and you alone are responsible for it. Use the program only for content you have the right to use, and comply with copyright law, with the terms of service of the sites you use (including YouTube's) and with data protection law. Transcripts and especially speaker labels may contain personal data of the people speaking; handle them accordingly and do not publish them without the necessary permission. The program gives you no rights to any content; publishing or sharing someone else's content as text may require the rights holder's permission. Cookies, if you use them, come from your own browser and account, at your own risk.</p>
<p><b>Your data.</b> The program has no telemetry and does not collect anything. Settings, history, transcripts, cookies and the Hugging Face access key are stored only on this computer, in your user folder; you can delete them at any time.</p>
<p><b>Accuracy.</b> Automatic transcripts and speaker labels can contain errors, omissions and wrong attributions. Check them before you rely on them, quote them or publish them; they are not suitable as a verbatim legal, medical or official record without human review.</p>
<p><b>No warranty, no liability.</b> The program is provided "as is", free of charge, without warranty of any kind, express or implied, including fitness for a particular purpose. To the fullest extent permitted by law, the author is not liable for any direct or indirect damage, loss of data, costs or legal consequences arising from the use or inability to use the program, the third-party models and tools, or the content processed with them (see sections 15–17 of the GNU GPL v3.0).</p>`,
hu: name => `<p>A <b>${name}</b> YouTube-videókat, teljes lejátszási listákat és saját hang- vagy videófájlokat alakít szöveggé a saját gépeden. A beszédfelismerést a Whisper modell végzi helyben, a videókártyádon (vagy a processzoron). A hangot és az átiratokat a program nem küldi el semmilyen szerverre: az internetet csak a hozzáadott videók hangjának lekéréséhez (streameléséhez), valamint az összetevők és modellek egyszeri letöltéséhez használja. A videók nem mentődnek fájlként – a hang a memóriában dolgozódik fel.</p>
<p>Készítette: <b>Lalikavics</b>. Developed with the help of Claude (Anthropic). Verzió: ${'{VER}'}. A program szabad szoftver, a <b>GNU GPL v3.0</b> licenc alatt.</p>
<h3>Támogatás</h3>
<p>Programozom, rajzolok és alkotok, egyszerűen a kedvemért. Kicsit olyan vagyok, mint egy reneszánsz polihisztor, csak internettel, vizuális érzékkel és több hibával. 😄<br>Tetszenek az ingyenes projektjeim? <a href="#" data-url="{COFFEE}">Meghívhatsz egy kávéra ☕ vagy egy pizzára 🍕</a>. Sosem kötelező, de mindig jólesik, és segít abban, hogy még több hasznos (vagy teljesen haszontalan) dolgot hozzak létre.</p>
<p><b>Semmi nem változik, akár adsz, akár nem.</b> A ${name} ingyenes, és az is marad: nincs fizetős változat, nincsenek zárolt funkciók, a támogatók sem kapnak extra szolgáltatást vagy elsőbbséget. A kávé önkéntes köszönet, nem vásárlás.</p>
<h3>Amire épül</h3>
<p>A ${name} egy kezelőfelület: magát a beszédfelismerést mások által készített modellek és eszközök végzik. Ezek nem a program részei, a szerzőik tulajdonát képezik, és a saját licencük szerint használhatók:</p>
<ul>
<li><b>Whisper</b> beszédfelismerő modell – OpenAI (MIT); faster-whisperhez átalakítva: Mobius Labs (MIT)</li>
<li><b>faster-whisper</b> – SYSTRAN (MIT); <b>CTranslate2</b> – OpenNMT (MIT)</li>
<li>Beszélőfelismerő kiegészítő: <b>pyannote.audio</b> (MIT) és a <b>speaker-diarization-community-1</b> modell (CC BY 4.0) – pyannote / Hervé Bredin és közreműködők; <b>PyTorch</b> (BSD)</li>
<li><b>yt-dlp</b> – a yt-dlp közreműködői (Unlicense); <b>Deno</b> – a Deno szerzői (MIT)</li>
<li><b>FFmpeg</b> – az FFmpeg fejlesztői (LGPL/GPL)</li>
<li><b>pywebview</b>, <b>ReportLab</b>, <b>python-docx</b> – a szerzőik (BSD/MIT)</li>
</ul>
<h3>Jogi nyilatkozat</h3>
<p><b>Mi a szerzőé.</b> A szerző munkája kizárólag maga a program: a forráskódja, a kezelőfelülete, a neve és a logója. Semmi más.</p>
<p><b>Mi nem az.</b> A beszédfelismerő és beszélőfelismerő modellek (Whisper, pyannote), valamint a fent felsorolt könyvtárak és eszközök nem a ${name} részei, és nem a szerzője készítette őket. Ezeket a program a hivatalos forrásukból tölti le; a szerzőik tulajdonát képezik, és a saját licencük, illetve felhasználási feltételeik vonatkoznak rájuk – egyes modellek (például a pyannote beszélőmodell) csak azután használhatók, hogy a feltételeiket te magad elfogadtad a szolgáltatónál. A szerző ezekre semmilyen jogot nem formál, és semmilyen garanciát nem vállal értük. Minden videó, hangfájl és átirat, amelyet feldolgozol, szintén a saját jogosultjaié, nem a szerzőé.</p>
<p><b>Függetlenség.</b> A ${name} független, nem kereskedelmi projekt. Nem áll kapcsolatban a YouTube-bal, a Google-lel, az OpenAI-jal, a Hugging Face-szel, a pyannote-tal vagy bármely más itt említett céggel, és ők nem is szponzorálják vagy támogatják; a nevük és védjegyeik a tulajdonosaiké, és csak a kompatibilitás leírására szerepelnek.</p>
<p><b>A te felelősséged.</b> Te döntöd el, mit írsz át és hogyan használod fel az eredményt, és ezért egyedül te felelsz. A programot csak olyan tartalomhoz használd, amelynek a felhasználására jogosult vagy, és tartsd be a szerzői jogot, a használt oldalak (köztük a YouTube) felhasználási feltételeit és az adatvédelmi szabályokat (GDPR). Az átiratok – különösen a beszélők jelölése – a megszólalók személyes adatait tartalmazhatják; ennek megfelelően kezeld őket, és a szükséges engedély nélkül ne tedd közzé. A program semmilyen jogot nem ad a tartalmakra; más tartalmának szövegként való közzétételéhez vagy megosztásához a jogosult engedélye kellhet. Ha sütiket használsz, azok a saját böngésződből és fiókodból származnak, a saját felelősségedre.</p>
<p><b>Az adataid.</b> A programban nincs telemetria, semmit nem gyűjt. A beállítások, az előzmények, az átiratok, a sütik és a Hugging Face hozzáférési kulcs kizárólag ezen a gépen, a felhasználói mappádban tárolódnak; bármikor törölheted őket.</p>
<p><b>Pontosság.</b> A gépi átirat és a beszélők jelölése tartalmazhat hibát, kihagyást és téves hozzárendelést. Mielőtt támaszkodsz rá, idézed vagy közzéteszed, ellenőrizd; emberi ellenőrzés nélkül nem alkalmas szó szerinti jogi, orvosi vagy hivatalos jegyzőkönyvnek.</p>
<p><b>Nincs garancia, nincs felelősség.</b> A program ingyenes, és „ahogy van” alapon, mindenféle kifejezett vagy hallgatólagos garancia nélkül érhető el, ideértve azt is, hogy egy adott célra alkalmas-e. A jogszabályok által megengedett legteljesebb mértékben a szerző nem felel semmilyen közvetlen vagy közvetett kárért, adatvesztésért, költségért vagy jogi következményért, amely a program, a külső modellek és eszközök, illetve a velük feldolgozott tartalom használatából vagy használhatatlanságából ered (lásd a GNU GPL v3.0 15–17. pontját).</p>`
};
