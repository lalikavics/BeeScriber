# -*- coding: utf-8 -*-
"""The job queue (SQLite) and the worker thread that transcribes one job at a time.

Statuses: queued -> running -> done | error ; paused (by the user, skipped until resumed).
Pausing the whole queue puts the running job back to 'queued' with its position kept, so Start continues it.
Finished jobs stay in the table as history (their segments are kept, so other formats can be exported later)."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import traceback
from pathlib import Path

from . import config, exporters, sources
from .audio import AudioStream
from .engine import EngineError, Stop
from .transcriber import Journal, TranscribeError, transcribe

log = logging.getLogger(config.APP_ID)

COLUMNS = ["id", "kind", "source", "video_id", "title", "channel", "duration", "playlist_id", "playlist_title",
           "pl_index", "status", "pos", "lang", "error_code", "error", "outputs", "sort", "created", "updated",
           "started", "finished", "wall", "speed", "output_dir"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL, source TEXT NOT NULL, video_id TEXT, title TEXT, channel TEXT, duration REAL,
  playlist_id TEXT, playlist_title TEXT, pl_index INTEGER,
  status TEXT NOT NULL DEFAULT 'queued', pos REAL NOT NULL DEFAULT 0, lang TEXT,
  error_code TEXT, error TEXT, outputs TEXT, sort REAL NOT NULL,
  created REAL, updated REAL, started REAL, finished REAL, wall REAL, speed REAL, output_dir TEXT);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, sort);
CREATE INDEX IF NOT EXISTS jobs_video ON jobs(video_id);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""
ACTIVE = ("queued", "running", "paused", "error")


def done_key(kind: str, source: str, video_id: str | None) -> str:
    return f"yt:{video_id}" if video_id else f"file:{Path(source).resolve()}".lower() if kind == "file" else source


class JobQueue:
    def __init__(self, settings, emit=None, db_path: Path = config.DB_PATH, jobs_dir: Path = config.JOBS_DIR,
                 engine_factory=None, stream_factory=AudioStream):
        self.settings = settings
        self.emit = emit or (lambda *_a, **_k: None)
        self.jobs_dir = jobs_dir
        self.engine_factory = engine_factory or self._make_engine
        self.stream_factory = stream_factory
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.running = False                 # queue started by the user
        self.current: int | None = None
        self.stop_reason: str | None = None  # set to ask the current job to stop
        self.engine = None
        self.engine_key = None
        self.speed_ema: float | None = None
        self.closing = False
        # a crash or a closed app leaves 'running' rows: they continue from their journal
        self._q("UPDATE jobs SET status='queued' WHERE status='running'")
        self.thread = threading.Thread(target=self._worker, name="worker", daemon=True)
        self.thread.start()

    # ------------------------------------------------------------ db helpers
    def _q(self, sql: str, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def _row(self, job_id: int) -> dict | None:
        r = self._q("SELECT * FROM jobs WHERE id=?", (job_id,))
        return self._dict(r[0]) if r else None

    @staticmethod
    def _dict(r) -> dict:
        d = dict(r)
        d["outputs"] = json.loads(d["outputs"]) if d.get("outputs") else []
        return d

    def _set(self, job_id: int, **fields) -> dict | None:
        fields["updated"] = time.time()
        cols = ", ".join(f"{k}=?" for k in fields)
        self._q(f"UPDATE jobs SET {cols} WHERE id=?", tuple(fields.values()) + (job_id,))
        job = self._row(job_id)
        if job:
            self.emit("job", job=job)
        return job

    # ------------------------------------------------------------ reading
    def jobs(self, history: bool = False) -> list[dict]:
        if history:
            rows = self._q("SELECT * FROM jobs WHERE status='done' ORDER BY finished DESC")
        else:
            rows = self._q("SELECT * FROM jobs WHERE status IN ('queued','running','paused','error') ORDER BY sort")
        return [self._dict(r) for r in rows]

    def done_keys(self) -> set[str]:
        return {done_key(r["kind"], r["source"], r["video_id"])
                for r in self._q("SELECT kind, source, video_id FROM jobs WHERE status='done'")}

    def active_keys(self) -> set[str]:
        return {done_key(r["kind"], r["source"], r["video_id"])
                for r in self._q("SELECT kind, source, video_id FROM jobs WHERE status IN "
                                 "('queued','running','paused','error')")}

    def state(self) -> dict:
        with self.lock:
            jobs = self.jobs()
            left = sum(max(0.0, (j["duration"] or 0) - (j["pos"] or 0)) for j in jobs
                       if j["status"] in ("queued", "running"))
            eta = left / self.speed_ema if self.speed_ema else None
            return {"running": self.running, "current": self.current, "speed": self.speed_ema,
                    "eta_all": eta, "audio_left": left, "counts": {
                        s: sum(1 for j in jobs if j["status"] == s) for s in ("queued", "running", "paused", "error")},
                    "engine": self.engine_info()}

    def engine_info(self) -> dict | None:
        e = self.engine
        if not e:
            return None
        return {"name": e.name, "model": getattr(e, "model_ref", None), "device": e.device, "compute": e.compute,
                "fallback": getattr(e, "fallback", None)}

    # ------------------------------------------------------------ changing the queue
    def add(self, items: list[dict], collection: dict | None = None, output_dir: str | None = None) -> list[int]:
        """items: dicts from sources.load_url()/probe_file(). Items already waiting in the queue are skipped."""
        ids = []
        with self.lock:
            active = self.active_keys()
            top = (self._q("SELECT MAX(sort) AS m FROM jobs")[0]["m"] or 0) + 1
            for k, it in enumerate(items):
                key = done_key(it["kind"], it["source"], it.get("video_id"))
                if key in active:
                    continue
                active.add(key)
                pl = collection if collection and collection.get("type") == "playlist" else None
                now = time.time()
                cur = self.db.execute(
                    "INSERT INTO jobs(kind, source, video_id, title, channel, duration, playlist_id, playlist_title,"
                    " pl_index, status, sort, created, updated, output_dir) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (it["kind"], it["source"], it.get("video_id"), it.get("title"), it.get("channel"),
                     it.get("duration"), pl and pl.get("id"), pl and pl.get("title"), it.get("index") if pl else None,
                     "queued", top + k, now, now, output_dir))
                ids.append(cur.lastrowid)
            self.cv.notify_all()
        for i in ids:
            self.emit("job", job=self._row(i))
        return ids

    def start(self) -> None:
        with self.lock:
            self.running = True
            self.cv.notify_all()
        self.emit("queue", state=self.state())

    def pause_all(self, now: bool = True) -> None:
        """now=True: stop the current job immediately (its finished windows are kept)."""
        with self.lock:
            self.running = False
            if now and self.current is not None:
                self.stop_reason = "pause"
            self.cv.notify_all()
        self.emit("queue", state=self.state())

    def pause_job(self, job_id: int) -> None:
        with self.lock:
            if self.current == job_id:
                self.stop_reason = "pause_job"
            else:
                self._q("UPDATE jobs SET status='paused' WHERE id=? AND status IN ('queued','error')", (job_id,))
        self.emit("job", job=self._row(job_id))

    def resume_job(self, job_id: int) -> None:
        self._set(job_id, status="queued", error_code=None, error=None)
        with self.lock:
            self.cv.notify_all()

    retry = resume_job

    def remove(self, job_ids: list[int]) -> None:
        for job_id in job_ids:
            with self.lock:
                if self.current == job_id:
                    self.stop_reason = "cancel"      # the worker deletes it when it stops
                    continue
                self._q("DELETE FROM jobs WHERE id=? AND status!='done'", (job_id,))
            Journal(job_id, self.jobs_dir).reset()
            self.emit("removed", id=job_id)

    def move(self, job_id: int, to_index: int) -> None:
        """Move a waiting job to position `to_index` (0 = first) of the active list."""
        with self.lock:
            order = [j["id"] for j in self.jobs()]
            if job_id not in order:
                return
            order.remove(job_id)
            order.insert(max(0, min(to_index, len(order))), job_id)
            for k, i in enumerate(order):
                self.db.execute("UPDATE jobs SET sort=? WHERE id=?", (float(k + 1), i))
        self.emit("reordered", order=order)

    def delete_history(self, job_ids: list[int] | None = None) -> int:
        """Forget finished jobs (all if job_ids is None). Transcript files on disk are left alone."""
        with self.lock:
            rows = self._q("SELECT id FROM jobs WHERE status='done'" if job_ids is None else
                           f"SELECT id FROM jobs WHERE status='done' AND id IN ({','.join('?' * len(job_ids))})",
                           () if job_ids is None else tuple(job_ids))
            for r in rows:
                self.db.execute("DELETE FROM jobs WHERE id=?", (r["id"],))
                Journal(r["id"], self.jobs_dir).reset()
                (self.jobs_dir / f"{r['id']}.speakers.json").unlink(missing_ok=True)
        self.emit("history", count=len(rows))
        return len(rows)

    def reexport(self, job_id: int, formats: list[str]) -> list[str]:
        job = self._row(job_id)
        if not job or job["status"] != "done":
            raise ValueError("not a finished job")
        segs = self.segments(job_id)
        out = exporters.export(job, segs, self.settings, formats)
        merged = list(dict.fromkeys((job["outputs"] or []) + out))
        self._set(job_id, outputs=json.dumps(merged, ensure_ascii=False))
        return out

    def segments(self, job_id: int) -> list[dict]:
        from . import diarize
        segs = Journal(job_id, self.jobs_dir).load()[1]
        return diarize.apply(segs, diarize.load(job_id, self.jobs_dir))

    def _speakers(self, jid: int, job: dict, segs: list[dict]) -> list[dict]:
        """Optional speaker step (pyannote). Any failure leaves the transcript without speaker names."""
        from . import audio, diarize
        if not diarize.installed() or not diarize.token_get():
            self.emit("speakers", id=jid, status="unavailable")
            return segs
        try:
            self.emit("speakers", id=jid, status="running")
            pcm = audio.read_all(job["kind"], job["source"], self.settings, self._should_stop)
            n = int(self.settings.get("speakers") or 0) or None
            turns = diarize.Diarizer.run(pcm, n)
            del pcm
            spk_segs = diarize.split_by_speaker(segs, turns)
            diarize.save(jid, spk_segs, self.jobs_dir)
            found = len({x["speaker"] for x in spk_segs if x.get("speaker")})
            self.emit("speakers", id=jid, status="done", count=found)
            log.info("job %s: %d speakers, %d turns from pyannote", jid, found, len(turns))
            return spk_segs
        except Stop:
            raise
        except Exception as e:  # noqa: BLE001
            log.error("speaker step failed: %s", traceback.format_exc())
            self.emit("speakers", id=jid, status="error", error=str(e)[-400:])
            return segs

    def close(self, timeout: float = 15) -> None:
        with self.lock:
            self.closing = True
            self.running = False
            if self.current is not None:
                self.stop_reason = "shutdown"
            self.cv.notify_all()
        self.thread.join(timeout)
        with self.lock:
            self.db.close()

    # ------------------------------------------------------------ worker
    def _make_engine(self, status):
        from .engine import WhisperEngine
        s = self.settings
        model = s.get("custom_model") or s.get("model")
        return WhisperEngine(model, s.get("device"), s.get("compute"), status=status,
                             cancelled=lambda: self.closing)

    def _ensure_engine(self):
        s = self.settings
        key = (s.get("custom_model") or s.get("model"), s.get("device"), s.get("compute"))
        if self.engine is None or self.engine_key != key:
            self.engine = None
            self.emit("engine", status="loading", model=key[0])
            self.engine = self.engine_factory(lambda st, **kw: self.emit("engine", status=st, **kw))
            self.engine_key = key
            self.emit("engine", status="ready", info=self.engine_info(), load_s=round(self.engine.load_s, 1))
        return self.engine

    def _next(self) -> dict | None:
        rows = self._q("SELECT * FROM jobs WHERE status='queued' ORDER BY sort LIMIT 1")
        return self._dict(rows[0]) if rows else None

    def _should_stop(self):
        return self.stop_reason

    def _worker(self) -> None:
        while True:
            with self.lock:
                while not self.closing and (not self.running or not self._next()):
                    if self.running and not self._next():
                        self.running = False             # queue finished
                        self.emit("queue", state=self.state(), finished=True)
                    self.cv.wait(1.0)
                if self.closing:
                    return
                job = self._next()
                self.current = job["id"]
                self.stop_reason = None
            try:
                self._run(job)
            except Exception:  # noqa: BLE001  (never let the worker die)
                log.error("worker crash on job %s:\n%s", job["id"], traceback.format_exc())
                self._set(job["id"], status="error", error_code="internal", error=traceback.format_exc()[-1500:])
            finally:
                with self.lock:
                    self.current = None
                    self.stop_reason = None
                self.emit("queue", state=self.state())

    def _run(self, job: dict) -> None:
        jid = job["id"]
        try:
            engine = self._ensure_engine()
        except Exception as e:  # noqa: BLE001
            log.error("engine load failed: %s", traceback.format_exc())
            self.pause_all(now=False)
            self.emit("engine", status="error", error=str(e)[-800:])
            return
        t0 = time.time()
        job = self._set(jid, status="running", started=job.get("started") or t0, error_code=None, error=None)
        journal = Journal(jid, self.jobs_dir)
        dur = job.get("duration")

        def on_event(ev: str, **d):
            if ev == "accepted":
                if d.get("avg_speed"):
                    sp = d["avg_speed"]
                    self.speed_ema = sp if not self.speed_ema else 0.7 * self.speed_ema + 0.3 * sp
                self._q("UPDATE jobs SET pos=?, updated=? WHERE id=?", (d["pos"], time.time(), jid))
                eta = (max(0.0, dur - d["pos"]) / d["avg_speed"]) if dur and d.get("avg_speed") else None
                self.emit("progress", id=jid, pos=d["pos"], duration=dur, speed=d.get("speed"), eta=eta,
                          state=self.state())
            elif ev == "language":
                self._q("UPDATE jobs SET lang=? WHERE id=?", (d["lang"], jid))
            self.emit(ev, id=jid, **d)

        try:
            res = transcribe({"kind": job["kind"], "source": job["source"], "duration": dur}, engine, journal,
                             self.settings, on_event, self._should_stop, self.stream_factory)
        except Stop as s:
            pos = journal.load()[0]
            if s.reason == "cancel":
                with self.lock:
                    self._q("DELETE FROM jobs WHERE id=?", (jid,))
                journal.reset()
                self.emit("removed", id=jid)
            else:
                self._set(jid, status="paused" if s.reason == "pause_job" else "queued", pos=pos,
                          wall=(job.get("wall") or 0) + time.time() - t0)
            return
        except (TranscribeError, sources.SourceError) as e:
            self._set(jid, status="error", error_code=e.code, error=e.detail, pos=journal.load()[0],
                      wall=(job.get("wall") or 0) + time.time() - t0)
            return
        except EngineError as e:
            self._set(jid, status="error", error_code="engine", error=str(e)[-1500:])
            return
        wall = (job.get("wall") or 0) + time.time() - t0
        job = self._set(jid, lang=res["lang"], pos=res["pos"], duration=dur or res["pos"])
        if not res["segs"]:
            self._set(jid, status="error", error_code="no_speech", wall=wall)
            return
        segs = res["segs"]
        if self.settings.get("diarize"):
            try:
                segs = self._speakers(jid, job, segs)
            except Stop as s:
                self._set(jid, status="paused" if s.reason == "pause_job" else "queued", wall=wall)
                return
            wall = (job.get("wall") or 0) + time.time() - t0
        try:
            outputs = exporters.export(job, segs, self.settings)
        except Exception as e:  # noqa: BLE001
            log.error("export failed: %s", traceback.format_exc())
            self._set(jid, status="error", error_code="export", error=str(e)[-1500:], wall=wall)
            return
        self._set(jid, status="done", outputs=json.dumps(outputs, ensure_ascii=False), finished=time.time(),
                  wall=wall, speed=round(res["pos"] / wall, 1) if wall else None)
        if self.settings.get("pause_after_video"):
            self.pause_all(now=False)
