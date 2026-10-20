# -*- coding: utf-8 -*-
"""Audio as a stream: yt-dlp -> ffmpeg -> 16 kHz mono PCM in memory. Nothing is written to disk.
Can start at any position (resume): local files seek directly, YouTube streams are decoded and skipped."""
from __future__ import annotations

import collections
import subprocess
import threading

from . import sources, tools
from .engine import Stop

SR = 16000
SR_BYTES = SR * 2                 # mono, 16-bit


class PcmBuffer:
    """Raw audio filled by a reader thread; the download keeps running while the GPU works."""

    def __init__(self, max_seconds: int = 1200):
        self.buf = bytearray()
        self.cv = threading.Condition()
        self.eof = False
        self.closed = False
        self.total = 0
        self.max_bytes = max_seconds * SR_BYTES

    def feed(self, stream) -> None:
        try:
            while not self.closed:
                data = stream.read(65536)
                if not data:
                    break
                with self.cv:
                    while len(self.buf) > self.max_bytes and not self.closed:   # do not hold the whole video
                        self.cv.wait(0.5)
                    self.buf += data
                    self.total += len(data)
                    self.cv.notify_all()
        except (OSError, ValueError):
            pass
        finally:
            with self.cv:
                self.eof = True
                self.cv.notify_all()

    def wait_for(self, nbytes: int, should_stop=None):
        with self.cv:
            while len(self.buf) < nbytes and not self.eof:
                self.cv.wait(0.5)
                if should_stop:
                    r = should_stop()
                    if r:
                        raise Stop(r)
            return len(self.buf), self.eof

    def peek(self, nbytes: int) -> bytes:
        with self.cv:
            return bytes(self.buf[:nbytes])

    def consume(self, nbytes: int) -> None:
        with self.cv:
            del self.buf[:nbytes]
            self.cv.notify_all()

    def close(self) -> None:
        with self.cv:
            self.closed = True
            self.cv.notify_all()


class _Tail:
    def __init__(self, stream, keep: int = 80):
        self.lines = collections.deque(maxlen=keep)
        self.t = threading.Thread(target=self._run, args=(stream,), daemon=True)
        self.t.start()

    def _run(self, stream) -> None:
        try:
            for raw in iter(stream.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    self.lines.append(line)
        except (OSError, ValueError):
            pass

    def text(self) -> str:
        return "\n".join(self.lines)


class AudioStream:
    def __init__(self, kind: str, source: str, start_at: float = 0.0, settings=None):
        self.kind, self.source, self.start_at, self.settings = kind, source, max(0.0, start_at), settings
        self.buffer = PcmBuffer()
        self.procs: list[subprocess.Popen] = []
        self.tails: list[_Tail] = []
        self.reader: threading.Thread | None = None

    def start(self) -> "AudioStream":
        ff = tools.tool("ffmpeg")
        if not ff:
            raise sources.SourceError("tools", "ffmpeg missing")
        env, nw = tools.env(), tools.no_window()
        ss = ["-ss", f"{self.start_at:.3f}"] if self.start_at > 0 else []
        out = ["-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
        if self.kind == "file":
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin"] + ss + ["-i", self.source] + out
            ffp = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, **nw)
            self.procs = [ffp]
        else:
            yt = tools.tool("yt-dlp")
            if not yt:
                raise sources.SourceError("tools", "yt-dlp missing")
            ytcmd = [yt, "--no-playlist", "-f", "bestaudio/best", "-o", "-", "--no-progress", "--no-part",
                     "--encoding", "utf-8"] + (sources.cookie_args(self.settings) if self.settings else []) + \
                    ["--", self.source]
            ytp = subprocess.Popen(ytcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, **nw)
            # -ss after -i: decode and skip (exact position, works on a pipe)
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", "pipe:0"] + ss + out
            ffp = subprocess.Popen(cmd, stdin=ytp.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=env, **nw)
            ytp.stdout.close()                      # ffmpeg owns the pipe now
            self.procs = [ytp, ffp]
            self.tails.append(_Tail(ytp.stderr))
        self.tails.append(_Tail(ffp.stderr))
        self.reader = threading.Thread(target=self.buffer.feed, args=(ffp.stdout,), daemon=True)
        self.reader.start()
        return self

    def errors(self) -> str:
        return "\n".join(t.text() for t in self.tails).strip()

    def returncodes(self) -> list:
        return [p.poll() for p in self.procs]

    def close(self) -> None:
        self.buffer.close()
        for p in reversed(self.procs):
            if p.poll() is None:
                p.terminate()
        for p in self.procs:
            try:
                p.wait(timeout=10)
            except Exception:  # noqa: BLE001
                p.kill()
        if self.reader:
            self.reader.join(timeout=3)
        for p in self.procs:
            for s in (p.stdout, p.stderr):
                try:
                    if s:
                        s.close()
                except Exception:  # noqa: BLE001
                    pass
        for t in self.tails:
            t.t.join(timeout=2)


def read_all(kind: str, source: str, settings=None, should_stop=None) -> bytes:
    """The whole audio as 16 kHz mono PCM, in memory only (for the speaker step: ~115 MB per hour)."""
    st = AudioStream(kind, source, 0.0, settings).start()
    out = bytearray()
    try:
        buf = st.buffer
        while True:
            n, eof = buf.wait_for(SR_BYTES * 60, should_stop)
            if n:
                out += buf.peek(n)
                buf.consume(n)
            if eof and not buf.buf:
                break
    finally:
        errors = st.errors()
        st.close()
    if not out:
        raise sources.SourceError(sources.classify_error(errors), errors)
    return bytes(out)
