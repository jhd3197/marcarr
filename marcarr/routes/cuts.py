"""A film's versions and cuts: what an Extended adds, and moving a time between versions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Request

from ..cuts import edition_labels, map_time
from ..errors import MarcarrError, NotFoundError
from .common import PROPOSE, READ, REVIEW, RUN, core, source_of

router = APIRouter()


def _runtimes(title_id: str) -> list[tuple[str, float]]:
    """Published cut runtimes from the newest research run, for naming versions."""
    for run in core().store.research_runs(title_id, "cuts"):
        eds = (run.get("result") or {}).get("editions") or []
        out = [(str(e.get("name") or ""), float(e["runtime_minutes"]))
               for e in eds if e.get("name") and e.get("runtime_minutes")]
        if out:
            return out
    return []


def versions(title_id: str) -> list[dict[str, Any]]:
    c = core()
    vids = c.store.videos_of(title_id)
    labels = edition_labels([v for v in vids if v.get("in_plex", 1)] or vids, _runtimes(title_id))
    out = []
    for v in vids:
        lab = labels.get(v["id"], {"name": v["edition"], "guessed": False})
        streams = v["streams"] if isinstance(v["streams"], list) else json.loads(v["streams"] or "[]")
        steps = c.store.step_rows(v["id"])
        out.append({
            "id": v["id"], "edition": lab["name"], "guessed": lab["guessed"],
            "named": v["edition"], "duration": v["duration"], "file": Path(v["path"]).name,
            "in_plex": bool(v.get("in_plex", 1)), "current": bool(v["current"]),
            "audio": [s.get("language") or "" for s in streams if s.get("type") == "audio"],
            "steps_done": sum(1 for r in steps.values() if r["state"] == "done"),
            "has_shots": c.store.result(v["id"], "shots") is not None,
        })
    return out


def cut_view(r: dict[str, Any]) -> dict[str, Any]:
    src = r["source"]
    return {**r, "source_kind": src.split(":", 1)[0],
            "rough": src.startswith("research")}


@router.get("/titles/{tid}/cuts", dependencies=[READ])
def title_cuts(tid: str) -> dict[str, Any]:
    c = core()
    t = c.store.title(tid)
    vs = versions(tid)
    present = [v for v in vs if v["in_plex"]]
    compare = None
    if len(present) >= 2:
        ranked = sorted(present, key=lambda v: v["duration"] or 0)
        doc = c.store.cut_map(ranked[0]["id"], ranked[-1]["id"])
        if doc is not None:
            compare = {"a": ranked[0]["id"], "b": ranked[-1]["id"], "same_film": doc["same_film"],
                       "coverage": doc["coverage"], "speed": doc["speed"], "gaps": len(doc["gaps"])}
    runs = [{"id": r["id"], "question": r["question"], "model": r["model"], "cost": r["cost"],
             "created_at": r["created_at"], "sources": r["sources"],
             "editions": (r["result"] or {}).get("editions") or []}
            for r in c.store.research_runs(tid, "cuts")[:3]]
    return {
        "title": {"id": t["id"], "name": t["name"], "year": t["year"], "type": t["type"]},
        "versions": vs,
        "ranges": [cut_view(r) for r in c.store.cut_ranges(tid)],
        "compare": compare,
        "research": runs,
        "can": {
            "compare": None if len(present) >= 2 else "only one version of this film is in Plex",
            "research": c.research.available(),
        },
    }


@router.post("/titles/{tid}/cuts", dependencies=[PROPOSE])
def add_cut(tid: str, request: Request, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    """Mark footage one cut has and another lacks. A person's mark is kept at once;
    an app's waits for review."""
    c = core()
    c.store.title(tid)
    vid = body.get("video")
    if vid:
        v = c.store.video(vid)
        if v["title_id"] != tid:
            raise MarcarrError("that video belongs to another title")
    who = source_of(request)
    status = body.get("status") or ("accepted" if who == "person" else "proposed")
    if who != "person" and status == "accepted":
        status = "proposed"
    row = c.store.add_cut_range(
        tid, edition=str(body.get("edition") or ""), base=str(body.get("base") or ""),
        kind=str(body.get("kind") or "added"), video_id=vid, start=body.get("start"),
        end=body.get("end"), extra=body.get("extra"), status=status, source=who,
        confidence=body.get("confidence"), note=str(body.get("note") or ""),
        evidence=[str(x) for x in body.get("evidence") or []])
    c.events.emit("cut.changed", {"title": tid, "range": row["id"]})
    return cut_view(row)


@router.patch("/cuts/{cid}", dependencies=[REVIEW])
def change_cut(cid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    c = core()
    fields = {k: body[k] for k in ("status", "start", "end", "note", "edition", "base", "kind", "video_id")
              if k in body}
    row = c.store.update_cut_range(cid, **fields)
    c.events.emit("cut.changed", {"title": row["title_id"], "range": cid})
    return cut_view(row)


@router.post("/titles/{tid}/cuts/keep", dependencies=[REVIEW])
def keep_all(tid: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:  # noqa: B008
    """Keep every proposed range (of one source kind: compare, research)."""
    c = core()
    kind = str(body.get("source") or "")
    n = 0
    for r in c.store.cut_ranges(tid, status="proposed"):
        if not kind or r["source"].split(":", 1)[0] == kind:
            c.store.update_cut_range(r["id"], status="accepted")
            n += 1
    return {"kept": n}


@router.delete("/cuts/{cid}", dependencies=[REVIEW])
def delete_cut(cid: str) -> dict[str, Any]:
    c = core()
    row = c.store.cut_range(cid)
    c.store.delete_cut_range(cid)
    c.events.emit("cut.changed", {"title": row["title_id"], "range": cid})
    return {"deleted": cid}


@router.post("/titles/{tid}/cuts/compare", dependencies=[RUN])
def compare(tid: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:  # noqa: B008
    return core().cuts.submit(tid, body.get("a"), body.get("b"))


@router.post("/titles/{tid}/cuts/research", dependencies=[RUN])
def research(tid: str) -> dict[str, Any]:
    return core().research.submit(tid)


@router.get("/research/{rid}", dependencies=[READ])
def research_run(rid: str) -> dict[str, Any]:
    return core().store.research_run(rid)


@router.get("/videos/{vid}/to/{other}", dependencies=[READ])
def to_other(vid: str, other: str, t: float) -> dict[str, Any]:
    """A time of one version in another version of the same film, once they were
    compared. ``at`` is null where the footage is only in the first."""
    c = core()
    a, b = c.store.video(vid), c.store.video(other)
    if a["title_id"] != b["title_id"]:
        raise MarcarrError("the two videos are of different titles")
    doc = c.store.cut_map(vid, other)
    if doc is not None:
        return {"at": map_time(doc, t), "speed": doc["speed"]}
    doc = c.store.cut_map(other, vid)
    if doc is None:
        raise NotFoundError("these versions were not compared yet: POST /titles/{id}/cuts/compare")
    inverse = {"speed": 1 / float(doc["speed"] or 1.0),
               "segments": [{"a": s["b"], "b": s["a"],
                             "offset": -float(s["offset"]) / float(doc["speed"] or 1.0)}
                            for s in doc["segments"]]}
    return {"at": map_time(inverse, t), "speed": inverse["speed"]}
