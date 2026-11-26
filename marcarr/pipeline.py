"""The seven steps of one video, run as one "analyse" job per video.

Each step records its state, what it read (the finish time of the steps it
depends on, so a rerun upstream marks it stale), how long it took and what
the AI cost. A step that cannot run here (no AI, no face models, no
subtitles) is recorded as off or none and the rest still run.
"""

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import ai
from . import states as stmod
from .errors import JobCancelled, MarcarrError, NotFoundError
from .stages import cast as cast_mod
from .stages import index as idx
from .stages import subs as subs_mod
from .store import STEPS, now

if TYPE_CHECKING:
    from .core import Core
    from .jobs import JobContext

log = logging.getLogger("marcarr.pipeline")

MIN_SHOT = 0.4  # a "shot" shorter than this is a flash, merged into the one before
STILL_H = 360


class StepSkip(Exception):
    """A step that cannot run here: (state, detail)."""

    def __init__(self, state: str, detail: str):
        super().__init__(detail)
        self.state = state
        self.detail = detail


def merge_flashes(shots: list[tuple[float, float]], min_len: float = MIN_SHOT) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in shots:
        if out and b - a < min_len:
            out[-1][1] = b
        else:
            out.append([a, b])
    if len(out) > 1 and out[0][1] - out[0][0] < min_len:
        out[1][0] = out[0][0]
        out.pop(0)
    return [(round(a, 3), round(b, 3)) for a, b in out]


def apply_edits(scenes: list[dict[str, Any]], edits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Manual corrections on top of the automatic scenes: a "cut" splits the scene
    it falls in, a "join" removes the boundary at that time."""
    bounds = sorted({s["start"] for s in scenes} | {scenes[-1]["end"]}) if scenes else []
    shots_of = {(s["start"], s["end"]): s.get("shots", 0) for s in scenes}
    manual: set[float] = set()
    for e in edits:
        at = float(e["at"])
        if e["kind"] == "join":
            bounds = [b for b in bounds if abs(b - at) > 0.05 or b in (bounds[0], bounds[-1])]
        elif e["kind"] == "cut" and bounds and bounds[0] < at < bounds[-1]:
            if all(abs(b - at) > 0.05 for b in bounds):
                bounds.append(round(at, 3))
                bounds.sort()
            manual.add(round(at, 3))
    out = []
    for a, b in zip(bounds, bounds[1:], strict=False):
        out.append({"id": f"s{len(out) + 1:04d}", "start": a, "end": b,
                    "shots": shots_of.get((a, b), 0), "manual": a in manual or b in manual})
    return out


class Pipeline:
    def __init__(self, core: Core):
        self.core = core
        self.store = core.store
        self._engine: Any = None

    # -- submitting --------------------------------------------------------------------
    def submit(self, vid: str, steps: list[str] | None = None, *, only_needed: bool = False) -> dict[str, Any]:
        """Queue an analysis of one video. With no steps: every step that is not done
        (only_needed) or all seven."""
        v = self.store.video(vid)
        t = self.store.title(v["title_id"])
        info = stmod.step_info(self.store.step_rows(vid), self.core.cfg, self.core.caps())
        if steps:
            bad = [s for s in steps if s not in STEPS]
            if bad:
                raise MarcarrError(f"unknown step: {', '.join(bad)}")
            want = [s for s in STEPS if s in steps]
        elif only_needed:
            want = [s for s in STEPS if stmod.needs_run(info[s]["state"])]
        else:
            want = list(STEPS)
        # steps that read a rerun step's output run again too, and so do the ones
        # that never ran because it failed (STEPS is in dependency order)
        for s in STEPS:
            if (s not in want and any(d in want for d in stmod.DEPS[s])
                    and info[s]["state"] in ("done", "rerun", "notrun", "failed")):
                want.append(s)
        want = [s for s in STEPS if s in want]
        if not want:
            return {"queued": False, "position": 0, "steps": []}
        for s in want:
            if info[s]["state"] not in ("off",):
                self.store.set_step(vid, s, state="queued", progress=None)
        name = t["name"] if t["type"] != "episode" else f"{t['name']} (S{t['season'] or 0:02d}E{t['episode'] or 0:02d})"
        job = self.core.worker.submit("analyse", f"Analyse {name}", {"video": vid, "steps": want})
        position = self.core.jobs.count("queued")
        return {"queued": True, "position": position, "job": job["id"], "steps": want}

    def submit_left(self) -> int:
        """Queue every current video that has a step to run."""
        n = 0
        all_rows = self.store.all_step_rows()
        for v in self.store.current_videos():
            info = stmod.step_info(all_rows.get(v["id"], {}), self.core.cfg, self.core.caps())
            if any(i["state"] in ("run", "queued") for i in info.values()):
                continue
            if any(stmod.needs_run(i["state"]) for i in info.values()):
                if self.submit(v["id"], only_needed=True)["queued"]:
                    n += 1
        return n

    def finished(self, job: dict[str, Any]) -> None:
        """After an analyse job: steps it left queued or running go back to what they were."""
        vid = job["payload"].get("video")
        if not vid:
            return
        for s, r in self.store.step_rows(vid).items():
            if r["state"] in ("queued", "run"):
                back = "done" if r.get("finished_at") and r.get("seconds") is not None else "notrun"
                detail = "Cancelled" if job["status"] == "cancelled" else (job.get("message") or "")
                self.store.set_step(vid, s, state="failed" if job["status"] == "failed" and back == "notrun" else back,
                                    detail=detail[:300], progress=None)
        with contextlib.suppress(Exception):
            info = stmod.step_info(self.store.step_rows(vid), self.core.cfg, self.core.caps())
            if all(i["state"] in stmod.GOOD for i in info.values()):
                v = self.store.video(vid)
                self.core.events.emit("video.analysed", {
                    "video": vid, "title": v["title_id"],
                    "seconds_spent": round(sum(i["seconds"] or 0 for i in info.values())),
                    "ai_cost": round(sum(i["ai_cost"] for i in info.values()), 4)})

    # -- the job -----------------------------------------------------------------------
    def job_analyse(self, payload: dict[str, Any], ctx: JobContext) -> dict[str, Any]:
        vid = payload["video"]
        v = self.store.video(vid)
        if not Path(v["path"]).is_file():
            raise NotFoundError(f"the file is not where it was: {v['path']}")
        steps = [s for s in STEPS if s in payload.get("steps", STEPS)]
        done: dict[str, str] = {}
        for i, step in enumerate(steps):
            ctx.check()
            ctx.phase(i + 1, len(steps), step)
            done[step] = self.run_step(vid, step, ctx, i, len(steps))
        return {"video": vid, "steps": done, "message": "done"}

    def run_step(self, vid: str, step: str, ctx: JobContext, i: int = 0, n: int = 1) -> str:
        cfg = self.core.cfg
        caps = self.core.caps()
        rows = self.store.step_rows(vid)
        no = stmod.unsupported(step, cfg, caps)
        if no:
            self.store.set_step(vid, step, state=no[0], detail=no[1], progress=None)
            return no[0]
        for d in stmod.DEPS[step]:
            dep = rows.get(d)
            if d in ("subtitles", "cast"):
                continue  # these may be missing: scenes without lines, tags without a cast
            if not dep or dep["state"] != "done":
                self.store.set_step(vid, step, state="failed", progress=None,
                                    detail=f"Needs the {d} step first")
                return "failed"
        inputs = {d: (rows.get(d) or {}).get("finished_at") for d in stmod.DEPS[step]}
        started = time.monotonic()
        self.store.set_step(vid, step, state="run", progress=0.0, started_at=now(), detail="")
        last = [0.0]

        def progress(p: float, msg: str = "") -> None:
            ctx.check()
            p = max(0.0, min(1.0, p))
            if p - last[0] >= 0.01 or msg:
                last[0] = p
                self.store.set_step(vid, step, progress=round(p, 3))
                ctx.progress((i + p) / max(1, n), f"{step}: {msg}" if msg else step)

        state, detail = "done", ""
        with ai.metered() as meter:
            try:
                detail = getattr(self, f"step_{step}")(vid, progress, ctx)
            except StepSkip as skip:
                state, detail = skip.state, skip.detail
            except JobCancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - recorded on the step
                log.exception("step %s of %s failed", step, vid)
                state, detail = "failed", str(exc) or exc.__class__.__name__
        seconds = round(time.monotonic() - started, 1)
        self.store.set_step(vid, step, state=state, detail=(detail or "")[:300], progress=None,
                            seconds=seconds, ai_cost=round(meter.cost, 4), finished_at=now(),
                            inputs=inputs, version=stmod.VERSIONS[step])
        self.store.add_usage(vid, step, meter.cost, meter.tokens)
        v = self.store.video(vid)
        self.core.events.emit("step.finished", {"video": vid, "title": v["title_id"], "step": step,
                                                "state": state, "seconds": seconds})
        return state

    # -- shots -------------------------------------------------------------------------
    def step_shots(self, vid: str, progress: Any, ctx: JobContext) -> str:
        from prompture.media.understand import detect_shots, probe_video

        v = self.store.video(vid)
        info = probe_video(v["path"])
        total = info.duration or v["duration"] or 0.0

        def seen(pos: float) -> None:
            if total:
                progress(min(pos / total, 1.0), f"{int(pos // 60)} min read")

        try:
            shots = detect_shots(v["path"], cancel=ctx.cancel, progress=seen, threshold=idx.CUT_THRESHOLD)
        except TypeError:
            shots = detect_shots(v["path"], cancel=ctx.cancel, threshold=idx.CUT_THRESHOLD)
        ctx.check()
        pairs = merge_flashes([(s.start, s.end) for s in shots])
        self.store.save_result(vid, "shots", {
            "version": 1, "threshold": idx.CUT_THRESHOLD, "duration": info.duration,
            "width": info.width, "height": info.height, "shots": [[a, b] for a, b in pairs]})
        return f"{len(pairs):,} shots"

    # -- subtitles ---------------------------------------------------------------------
    def step_subtitles(self, vid: str, progress: Any, ctx: JobContext) -> str:
        v = self.store.video(vid)
        ff = self.core.cfg.ffmpeg
        lang = self.core.cfg.analysis.language
        progress(0.05, "reading subtitles")
        lines, src = subs_mod.load(v["path"], ff.binary, ff.probe_binary, lang)
        if not lines and self.core.cfg.analysis.transcribe:
            progress(0.1, "transcribing the audio")
            from prompture.media.understand import transcribe

            t = transcribe(v["path"], language=lang, max_source_bytes=1 << 40)
            lines = subs_mod.from_transcript(t.segments)
            src = {"kind": "transcript", "model": t.model}
        self.store.save_result(vid, "subtitles", {"version": 1, "source": src,
                                                  "lines": [ln.to_dict() for ln in lines]})
        if not lines:
            raise StepSkip("none", "This file has no subtitles")
        return f"{len(lines):,} lines ({src.get('kind', '')})"

    # -- scenes ------------------------------------------------------------------------
    def build_scenes(self, vid: str) -> list[dict[str, Any]]:
        shots = (self.store.result(vid, "shots") or {}).get("shots") or []
        lines = [subs_mod.Line(x["start"], x["end"], x["text"])
                 for x in (self.store.result(vid, "subtitles") or {}).get("lines") or []]
        scenes = idx.group_scenes([(a, b) for a, b in shots], lines)
        return apply_edits(scenes, self.store.scene_edits(vid))

    def step_scenes(self, vid: str, progress: Any, ctx: JobContext) -> str:
        scenes = self.build_scenes(vid)
        self.store.save_result(vid, "scenes", {"version": 1, "scenes": scenes})
        return f"{len(scenes):,} scenes"

    def rebuild_scenes(self, vid: str) -> list[dict[str, Any]]:
        """After a person moved an edge: same rule plus their corrections."""
        scenes = self.build_scenes(vid)
        self.store.save_result(vid, "scenes", {"version": 1, "scenes": scenes})
        return scenes

    def index_doc(self, vid: str) -> dict[str, Any]:
        """The FansCut-shaped index document the ported stages read."""
        shots = self.store.result(vid, "shots") or {}
        subs = self.store.result(vid, "subtitles") or {}
        scenes = self.store.result(vid, "scenes") or {}
        v = self.store.video(vid)
        return {"duration": shots.get("duration") or v["duration"], "width": shots.get("width") or v["width"],
                "height": shots.get("height") or v["height"], "shots": shots.get("shots") or [],
                "lines": subs.get("lines") or [], "scenes": scenes.get("scenes") or []}

    # -- signals -----------------------------------------------------------------------
    def step_signals(self, vid: str, progress: Any, ctx: JobContext) -> str:
        from .stages import signals as sig

        v = self.store.video(vid)
        doc = self.index_doc(vid)
        engine = None
        if self.core.caps().faces:
            with contextlib.suppress(Exception):
                engine = self.face_engine()
        w, h = doc.get("width") or 1920, doc.get("height") or 1080
        width = sig.WIDTH
        height = max(2, round(width * h / w / 2) * 2)
        total = float(doc.get("duration") or 0)
        samples = []
        ff = self.core.cfg.ffmpeg
        for t, img in sig.frames(v["path"], width, height, ffmpeg=ff.binary, cancel=ctx.cancel):
            luma, thumb, nf, fh = sig.measure(img, engine)
            samples.append(sig.Sample(t, luma, thumb, nf, fh))
            if total and len(samples) % 30 == 0:
                progress(0.85 * min(t / total, 1.0), f"looking at the picture ({int(t // 60)} min)")
        ctx.check()
        progress(0.87, "listening")
        loud = sig.levels(v["path"], ffmpeg=ff.binary)
        ranges = sig.label(doc, samples, loud)
        self.store.save_result(vid, "signals", {
            "version": sig.VERSION, "faces": engine is not None,
            "signals": {k: [[a, b] for a, b in rs] for k, rs in ranges.items()}})
        return f"{sum(len(r) for r in ranges.values()):,} ranges in {len(ranges)} signals"

    # -- cast --------------------------------------------------------------------------
    def fetch_cast(self, title_id: str) -> tuple[str, list[dict[str, Any]]]:
        t = self.store.title(title_id)
        src_title = t
        if t["type"] == "episode" and t["parent_id"]:
            src_title = self.store.title_or_none(t["parent_id"]) or t
        people: list[dict[str, Any]] = []
        source = ""
        plex = self.core.plex()
        if plex and src_title.get("plex_key"):
            try:
                people = cast_mod.from_plex(plex.metadata(str(src_title["plex_key"])))
                source = "plex"
            except MarcarrError as exc:
                log.warning("Plex cast of %s: %s", title_id, exc)
        key = self.core.cfg.catalogues.tmdb_api_key
        if not people and key and src_title.get("tmdb_id") and src_title["type"] == "movie":
            people = cast_mod.fetch_tmdb(key, int(src_title["tmdb_id"]), self.core.session)
            source = "tmdb"
        return source, people

    def step_cast(self, vid: str, progress: Any, ctx: JobContext) -> str:
        v = self.store.video(vid)
        source, people = self.fetch_cast(v["title_id"])
        if not people:
            raise StepSkip("none", "No cast: Plex lists nobody and no TMDB key is set")
        saved = self.store.save_cast(v["title_id"], source, people)
        t = self.store.title(v["title_id"])
        if t["parent_id"]:
            self.store.save_cast(t["parent_id"], source, people)
        self._refs_cache.pop(v["title_id"], None) if hasattr(self, "_refs_cache") else None
        return f"{len(saved)} people from {source.upper() if source == 'tmdb' else source.title()}"

    # -- faces -------------------------------------------------------------------------
    def face_engine(self) -> Any:
        from .stages import faces as faces_mod

        if self._engine is None:
            det, rec = faces_mod.ensure_models(self.core.data_dir / "models", None)
            self._engine = faces_mod.FaceEngine(det, rec)
        return self._engine

    def job_face_models(self, payload: dict[str, Any], ctx: JobContext) -> dict[str, Any]:
        from .stages import faces as faces_mod

        ctx.progress(0.1, "Downloading the face models")
        faces_mod.ensure_models(self.core.data_dir / "models", self.core.session)
        self.core.forget_caps()
        return {"message": "Face models downloaded"}

    def face_refs(self, title_id: str) -> dict[str, dict[str, Any]]:
        """Reference faces of a title's cast, from their photos, keyed by person id."""
        from .stages import faces as faces_mod

        if not hasattr(self, "_refs_cache"):
            self._refs_cache: dict[str, dict[str, dict[str, Any]]] = {}
        if title_id in self._refs_cache:
            return self._refs_cache[title_id]
        engine = self.face_engine()
        cache = self.core.data_dir / "cache" / "cast"
        refs: dict[str, dict[str, Any]] = {}
        cast = self.store.cast(title_id)
        t = self.store.title_or_none(title_id)
        if not cast and t and t.get("parent_id"):
            cast = self.store.cast(t["parent_id"])
        for c in cast[:40]:
            pid, url = c["person"], self.photo_source(c.get("photo") or "")
            if pid in refs or not url:
                continue
            photo = faces_mod.photo_cache(cache, url, self.core.session)
            feat = engine.reference(photo) if photo else None
            if feat is not None:
                refs[pid] = {"character": c.get("character") or "", "photo": url, "feature": feat}
        self._refs_cache[title_id] = refs
        return refs

    def photo_source(self, photo: str) -> str:
        """A cast photo URL Marcarr can download (Plex paths go through the server)."""
        if photo.startswith(("http://", "https://")):
            return photo
        plex = self.core.plex()
        if photo.startswith("/") and plex is not None:
            return f"{plex.base_url}{photo}?X-Plex-Token={self.core.cfg.plex.token}"
        return ""

    def step_faces(self, vid: str, progress: Any, ctx: JobContext) -> str:
        import cv2
        import numpy as np
        from prompture.media.understand import extract_frame

        from .stages import faces as faces_mod

        v = self.store.video(vid)
        engine = self.face_engine()
        refs = self.face_refs(v["title_id"])
        if not refs:
            raise StepSkip("none", "No cast photos to match faces against")
        scenes = (self.store.result(vid, "scenes") or {}).get("scenes") or []
        per = max(1, int(self.core.cfg.faces.per_scene))
        sure = self.core.cfg.faces.sure
        found: list[dict[str, Any]] = []
        for k, s in enumerate(scenes):
            ctx.check()
            a, b = s["start"], s["end"]
            for j in range(per):
                t = round(a + (b - a) * (j + 0.5) / per, 2)
                try:
                    data = extract_frame(v["path"], t, height=720)
                except Exception:  # noqa: BLE001 - one unreadable frame is not fatal
                    continue
                img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    continue
                named = faces_mod.name_faces(engine, img, refs, set())
                for f in named:
                    if not f["name"]:
                        continue
                    found.append({"person": f["name"], "at": t, "score": f["match"] or 0.0,
                                  "box": f["box"], "confirmed": 1 if (f["match"] or 0) >= sure else None})
            progress((k + 1) / max(1, len(scenes)), f"scene {k + 1} of {len(scenes)}")
        self.store.replace_faces(vid, found)
        people = {f["person"] for f in found}
        return f"{len(found):,} faces of {len(people)} people"

    # -- tags --------------------------------------------------------------------------
    def step_tags(self, vid: str, progress: Any, ctx: JobContext) -> str:
        from .tagging import run_tagging

        cfg = self.core.cfg
        spent = self.store.month_cost()
        if cfg.ai.monthly_limit and spent >= cfg.ai.monthly_limit:
            raise MarcarrError(f"This month's AI limit is reached (${spent:.2f} of "
                               f"${cfg.ai.monthly_limit:.2f}). Raise it in Settings.")
        return run_tagging(self.core, vid, progress, ctx)
