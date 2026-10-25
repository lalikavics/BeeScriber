# Changelog

## [1.0.0] - 2026-10-25

First public release.

- Transcribe YouTube videos, whole playlists and channels, and local audio / video files with Whisper (faster-whisper, large-v3-turbo by default) on an NVIDIA GPU, or on the CPU.
- The audio is streamed and processed in memory; videos are never downloaded as files.
- Playlists with checkboxes and a title filter; already transcribed videos are recognised.
- Queue with drag-and-drop order, pause and resume per video and in the middle of a video, also after closing the app.
- A failing video never stops the queue; network drops are retried and continue where they stopped.
- Live preview with progress and time left; GPU / VRAM / CPU meters; adjustable GPU load limit.
- Punctuation guard and repetition-loop clean-up for Whisper's typical failure modes.
- Outputs: TXT (paragraphs, one sentence per line or continuous, optional timestamps and title header), SRT, VTT, HTML, PDF, DOCX; re-export of earlier transcripts.
- Optional speaker recognition add-on (pyannote, runs locally, needs a free Hugging Face access key).
- English and Hungarian interface; clipboard auto-load; cookies for age-restricted or members-only videos.
- Windows installer: no Python needed; components and the model are downloaded once at the first start.
