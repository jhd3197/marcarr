"""The state of each step of a video, as the UI and the API report it.

Stored rows say what the last run did (done, failed, none, off, run, queued).
On top of that:

* a done step whose inputs finished again later is ``rerun`` (stale);
* a step with no row is ``off`` (turned off in Settings), ``none`` (not
  supported here: no AI, no face models) or ``notrun``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config

STEPS = ("shots", "subtitles", "scenes", "signals", "cast", "faces", "tags")
DEPS: dict[str, tuple[str, ...]] = {
    "shots": (),
    "subtitles": (),
    "scenes": ("shots", "subtitles"),
    "signals": ("shots", "subtitles"),
    "cast": (),
    "faces": ("scenes", "cast"),
    "tags": ("scenes", "cast"),
}
# Bump when a step's output changes shape or meaning: done steps become stale.
VERSIONS = {"shots": 1, "subtitles": 1, "scenes": 1, "signals": 1, "cast": 1, "faces": 1, "tags": 1}
FACE_MODELS = ("face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx")


@dataclass
class Caps:
    """What this install can do right now."""

    ai: bool
    ai_reason: str
    faces: bool
    faces_reason: str


def caps(cfg: Config) -> Caps:
    ai_ok = cfg.ai.enabled and bool(cfg.ai.model.strip())
    ai_reason = "" if ai_ok else ("Tags need AI. Turn it on in Settings." if not cfg.ai.enabled
                                  else "Tags need a model. Pick one in Settings.")
    from .stages import faces as faces_mod

    if not faces_mod.available():
        faces_ok, faces_reason = False, "Faces need OpenCV, which is not installed here."
    elif not all((cfg.data_dir / "models" / m).is_file() for m in FACE_MODELS):
        faces_ok, faces_reason = False, "Faces need two models that are not downloaded yet. Get them in Settings."
    else:
        faces_ok, faces_reason = True, ""
    return Caps(ai_ok, ai_reason, faces_ok, faces_reason)


def models_present(data_dir: Path) -> list[dict[str, Any]]:
    out = []
    for m in FACE_MODELS:
        p = data_dir / "models" / m
        out.append({"name": m, "present": p.is_file(), "size": p.stat().st_size if p.is_file() else None})
    return out


def unsupported(step: str, cfg: Config, c: Caps) -> tuple[str, str] | None:
    """(state, detail) when a step cannot run now, else None."""
    if not cfg.analysis.steps.get(step, True):
        return "off", "Turned off in Settings"
    if step == "tags" and not c.ai:
        return "off", c.ai_reason
    if step == "faces":
        if not cfg.faces.enabled:
            return "off", "Turned off in Settings"
        if not c.faces:
            return "none", c.faces_reason
    return None


def step_info(rows: dict[str, dict[str, Any]], cfg: Config, c: Caps) -> dict[str, dict[str, Any]]:
    """step -> {state, detail, seconds, ai_cost, finished_at, progress}."""
    out: dict[str, dict[str, Any]] = {}
    for s in STEPS:
        r = rows.get(s)
        info = {"state": "notrun", "detail": "", "seconds": None, "ai_cost": 0.0,
                "finished_at": None, "progress": None}
        if r is not None:
            info.update(state=r["state"], detail=r.get("detail") or "", seconds=r.get("seconds"),
                        ai_cost=r.get("ai_cost") or 0.0, finished_at=r.get("finished_at"),
                        progress=r.get("progress") if r["state"] == "run" else None)
            if r["state"] == "done":
                stale = r.get("version", 1) != VERSIONS[s]
                for d in DEPS[s]:
                    dep = rows.get(d)
                    seen = (r.get("inputs") or {}).get(d)
                    now_at = dep.get("finished_at") if dep and dep["state"] in ("done", "none") else None
                    if now_at and now_at != seen:
                        stale = True
                if stale:
                    info["state"] = "rerun"
        if info["state"] in ("notrun",):
            no = unsupported(s, cfg, c)
            if no:
                info["state"], info["detail"] = no
        out[s] = info
    return out


def states(rows: dict[str, dict[str, Any]], cfg: Config, c: Caps) -> dict[str, str]:
    return {s: i["state"] for s, i in step_info(rows, cfg, c).items()}


GOOD = ("done", "none", "off")


def needs_run(state: str) -> bool:
    return state in ("notrun", "rerun", "failed")


def state_line(info: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The one line under a poster: kind, text and progress of the whole video."""
    st = {s: i["state"] for s, i in info.items()}
    for i, s in enumerate(STEPS):
        if st[s] == "run":
            p = info[s].get("progress") or 0.0
            return {"kind": "run", "text": f"Analysing: {s}, step {i + 1} of 7",
                    "progress": round((i + p) / len(STEPS), 3)}
    if any(v == "queued" for v in st.values()):
        return {"kind": "queued", "text": "Waiting to be analysed", "progress": None}
    failed = [s for s in STEPS if st[s] == "failed"]
    if failed:
        return {"kind": "failed", "text": f"Failed at {failed[0]}", "progress": None}
    if any(v == "rerun" for v in st.values()):
        return {"kind": "rerun", "text": "Needs a rerun", "progress": None}
    if all(v in GOOD for v in st.values()):
        return {"kind": "done", "text": "Analysed", "progress": None}
    if any(v == "done" for v in st.values()):
        done = sum(v in GOOD for v in st.values())
        return {"kind": "notrun", "text": f"Partly analysed, {done} of 7 steps", "progress": None}
    return {"kind": "notrun", "text": "Not analysed", "progress": None}


def summary_text(info: dict[str, dict[str, Any]]) -> str:
    """"Analysed, 7 of 7 steps" / "5 of 7 steps. Tags need AI" for the title header."""
    st = {s: i["state"] for s, i in info.items()}
    done = sum(v == "done" for v in st.values())
    if done == 7:
        return "Analysed, 7 of 7 steps"
    reasons = []
    if st["tags"] == "off":
        reasons.append("Tags need AI")
    if st["subtitles"] == "none":
        reasons.append("This file has no subtitles")
    if st["faces"] == "none":
        reasons.append("Faces are not available")
    return f"{done} of 7 steps" + (". " + ". ".join(reasons) if reasons else "")
