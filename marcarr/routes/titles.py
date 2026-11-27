"""Titles, videos, scenes and their pictures."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .. import brief as briefmod
from .. import graph as graphmod
from .. import states as stmod
from ..errors import MarcarrError, NotFoundError
from ..stages import index as idx
from ..store import STEPS, clean_range
from ..views import source_kind, tag_family, tag_id
from .common import (
    PROPOSE,
    READ,
    REVIEW,
    RUN,
    cache_path,
    clip_file,
    core,
    frame_file,
    source_of,
    views,
)

router = APIRouter()
PER_PAGE = 60
FILTERS = ("all", "movies", "shows", "analysed", "review", "failed", "running", "notrun")


# -- titles ----------------------------------------------------------------------------
def _summaries(where: str, args: tuple[Any, ...]) -> list[dict[str, Any]]:
    c, v = core(), views()
    titles = c.store.titles(where, args)
    review = c.store.review_counts()
    all_rows = c.store.all_step_rows()
    current = {x["title_id"]: x for x in c.store.current_videos()}
    nvid: dict[str, int] = {}
    for r in c.db.query("SELECT title_id, COUNT(*) AS n FROM videos GROUP BY title_id"):
        nvid[r["title_id"]] = r["n"]
    out = []
    for t in titles:
        if t["type"] == "show":
            out.append(v.title_summary(t, review=review))
        else:
            vid = current.get(t["id"])
            out.append(v.title_summary(t, video=vid, rows=all_rows.get(vid["id"], {}) if vid else {},
                                       review=review, nvideos=nvid.get(t["id"], 0)))
    return out


def _match(f: str, s: dict[str, Any]) -> bool:
    kind = s["state"]["kind"]
    return {
        "all": True, "movies": s["type"] == "movie", "shows": s["type"] == "show",
        "analysed": s["analysed"], "review": s["to_review"] > 0, "failed": kind == "failed",
        "running": kind in ("run", "queued"), "notrun": kind == "notrun",
    }.get(f, True)


@router.get("/titles", dependencies=[READ])
def list_titles(type: str | None = None, analysed: bool | None = None, q: str = "",
                filter: str = "all", page: int = 1, per_page: int = PER_PAGE,
                parent: str | None = None, season: int | None = None) -> dict[str, Any]:
    if parent:
        where, args = "parent_id = ?", [parent]
        if season is not None:
            where += " AND season = ?"
            args.append(season)
    else:
        where, args = "type IN ('movie', 'show')", []
    if type in ("movie", "show", "episode"):
        where += " AND type = ?"
        args.append(type)
    items = _summaries(where, tuple(args))
    if parent:
        items.sort(key=lambda s: (s.get("season") or 0, s.get("episode") or 0))
        _episode_tags(items)
    if q:  # every word somewhere in the name: "potter sorcerer"
        words = q.lower().split()
        items = [s for s in items if all(w in s["name"].lower() for w in words)]
    counts = {f: sum(1 for s in items if _match(f, s)) for f in FILTERS}
    if analysed is not None:
        items = [s for s in items if s["analysed"] == analysed]
    items = [s for s in items if _match(filter, s)]
    per_page = max(1, min(per_page, 500))
    total = len(items)
    page = max(1, page)
    return {"total": total, "page": page, "items": items[(page - 1) * per_page: page * per_page],
            "counts": counts}


def _episode_tags(items: list[dict[str, Any]]) -> None:
    """The few most common kept or proposed tags of each episode, for the season table."""
    v = views()
    vids = [s["video_id"] for s in items if s.get("video_id")]
    tags = core().store.tags(videos=vids, status=["accepted", "proposed"]) if vids else []
    per: dict[str, dict[str, dict[str, Any]]] = {}
    for t in tags:
        per.setdefault(t["video_id"], {}).setdefault(t["tag"], v.tag_ref(t))
    for s in items:
        s["tags"] = list(per.get(s.get("video_id") or "", {}).values())[:4]


@router.get("/titles/{tid}", dependencies=[READ])
def get_title(tid: str) -> dict[str, Any]:
    return views().title_detail(tid)


@router.get("/titles/{tid}/graph", dependencies=[READ])
def title_graph(tid: str, request: Request) -> dict[str, Any]:
    """Who is seen with whom in a film or episode: people with their screen time,
    first sighting and longest absence, and the pairs that share scenes.
    ?video= picks an edition (default: the current one); ?through=N stops at scene N."""
    c, v = core(), views()
    t = c.store.title(tid)
    vid = request.query_params.get("video")
    if vid:
        if c.store.video(vid)["title_id"] != tid:
            raise NotFoundError(f"video {vid} is not a video of {tid}")
    else:
        cur = c.store.current_video(tid)
        if cur is None:
            raise NotFoundError(f"{t['name']} has no video yet")
        vid = cur["id"]
    raw = request.query_params.get("through")
    through = None
    if raw:
        try:
            through = max(1, int(raw))
        except ValueError as exc:
            raise MarcarrError(f"through must be a scene number, not {raw!r}") from exc
    scenes = v.scenes(vid)
    cast = {p["id"]: p for p in v.cast_people(tid)}
    ids = {p for s in scenes for k in ("seen", "speakers", "mentioned") for p in s[k]}
    for pid, p in c.store.people([x for x in ids if x not in cast]).items():
        cast[pid] = v.person_view(p)
    return {"title": tid, "video": vid, "total_scenes": len(scenes), **graphmod.build(scenes, cast, through)}


@router.post("/titles/{tid}/cast", dependencies=[REVIEW])
def add_cast(tid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    """Add a person to a title by hand, for a home video or anyone the catalogue
    misses. `name` is who they are on screen; `actor` (optional) who plays them.
    Upload their photo with PUT /people/{id}/photo so faces can be matched."""
    c = core()
    p = c.store.add_cast_member(tid, str(body.get("name") or ""), str(body.get("actor") or ""))
    c.pipeline.forget_refs()
    return views().person_view(p)


@router.delete("/titles/{tid}/cast/{pid}", status_code=204, dependencies=[REVIEW])
def remove_cast(tid: str, pid: str) -> Response:
    c = core()
    c.store.remove_cast_member(tid, pid)
    c.pipeline.forget_refs()
    return Response(status_code=204)


@router.get("/titles/{tid}/poster")
def poster(tid: str, width: int = 300) -> Response:
    c = core()
    t = c.store.title(tid)
    plex = c.plex()
    if not t["poster"] or plex is None:
        raise NotFoundError("no poster")
    width = max(80, min(int(width), 800))
    out = cache_path("posters", "clean", tid, t["poster"], width)
    if not out.is_file():
        # The item's own agent art, not an upload with ratings and badges drawn on (Kometa)
        path = plex.clean_art_path(str(t["plex_key"] or ""), "poster") if t["plex_key"] else None
        data = plex.artwork(str(t["plex_key"] or ""), "poster", width, path=path or t["poster"])
        if not data:
            raise NotFoundError("no poster")
        out.write_bytes(data)
    return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@router.post("/titles/{tid}/run", dependencies=[RUN])
def run_title(tid: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:  # noqa: B008
    c = core()
    t = c.store.title(tid)
    steps = body.get("steps") or None
    if t["type"] == "show":
        n = 0
        for e in c.store.titles("parent_id = ?", (tid,)):
            vid = c.store.current_video(e["id"])
            if vid and c.pipeline.submit(vid["id"], steps, only_needed=not steps)["queued"]:
                n += 1
        return {"queued": n}
    vid = c.store.current_video(tid)
    if vid is None:
        raise MarcarrError("this title has no file Marcarr can open yet")
    res = c.pipeline.submit(vid["id"], steps, only_needed=not steps)
    return {"queued": 1 if res["queued"] else 0, **res}


# -- videos ----------------------------------------------------------------------------
@router.get("/videos/{vid}", dependencies=[READ])
def get_video(vid: str) -> dict[str, Any]:
    return views().video_view(core().store.video(vid))


@router.post("/videos/{vid}/run", dependencies=[RUN])
def run_video(vid: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:  # noqa: B008
    steps = body.get("steps") or None
    if steps:
        steps = ["subtitles" if s in ("subs",) else s for s in steps]
    return core().pipeline.submit(vid, steps)


@router.get("/videos/{vid}/scenes", dependencies=[READ])
def list_scenes(vid: str, request: Request, tag: str | None = None, review: bool | None = None) -> dict[str, Any]:
    core().store.video(vid)
    lo = _num(request.query_params.get("from"))
    hi = _num(request.query_params.get("to"))
    items = views().scenes(vid)
    if lo is not None:
        items = [s for s in items if s["end"] > lo]
    if hi is not None:
        items = [s for s in items if s["start"] < hi]
    if tag:
        want = tag_id(tag)
        items = [s for s in items if any(t["tag"] == want for t in s["tags"])]
    if review:
        items = [s for s in items if s["to_review"] > 0]
    return {"total": len(items), "items": items}


def _num(s: str | None) -> float | None:
    try:
        return float(s) if s not in (None, "") else None
    except ValueError as exc:
        raise MarcarrError(f"not a number: {s}") from exc


@router.get("/videos/{vid}/scenes/{n}", dependencies=[READ])
def get_scene(vid: str, n: int) -> dict[str, Any]:
    return views().scene_detail(vid, n)


@router.get("/videos/{vid}/scenes/{n}/brief", dependencies=[READ])
def scene_brief(vid: str, n: int, request: Request) -> dict[str, Any]:
    """The scene as plain text to paste anywhere (the same text the MCP get_scene
    tool gives). ?link= is added at the end, so the reader can get back here."""
    link = (request.query_params.get("link") or "")[:500]
    return {"text": briefmod.scene_brief(views().scene_detail(vid, n), link=link)}


@router.patch("/videos/{vid}/scenes/{n}", dependencies=[REVIEW])
def move_scene(vid: str, n: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    """Move a scene's start or end. The old edge goes, the new one becomes a manual
    cut; with snap, the new edge lands on the nearest camera cut."""
    c = core()
    rows = views().scene_rows(vid)
    if not 1 <= n <= len(rows):
        raise NotFoundError(f"scene {n} not found")
    s = rows[n - 1]
    doc = c.pipeline.index_doc(vid)
    with c.db.transaction():
        for edge in ("start", "end"):
            if edge not in body or body[edge] is None:
                continue
            new = float(body[edge])
            if body.get("snap"):
                new = idx.snap(doc, new, 10.0)
            old = s[edge]
            first, last = rows[0]["start"], rows[-1]["end"]
            if abs(new - old) < 0.01:
                continue
            if old not in (first, last):
                c.store.drop_scene_edits_near(vid, old)
                c.store.add_scene_edit(vid, "join", old)
            if first < new < last:
                c.store.drop_scene_edits_near(vid, new)
                c.store.add_scene_edit(vid, "cut", new)
    scenes = c.pipeline.rebuild_scenes(vid)
    target = float(body.get("start", s["start"]) if body.get("start") is not None else s["start"])
    if body.get("snap") and body.get("start") is not None:
        target = idx.snap(doc, target, 10.0)
    k = next((i + 1 for i, x in enumerate(scenes) if x["start"] <= target + 0.01 < x["end"]), n)
    return views().scene_detail(vid, min(max(1, k), len(scenes)))


@router.post("/videos/{vid}/scenes/{n}/place", dependencies=[REVIEW])
def scene_place(vid: str, n: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    rows = views().scene_rows(vid)
    if not 1 <= n <= len(rows):
        raise NotFoundError(f"scene {n} not found")
    s = rows[n - 1]
    core().store.set_place_scene(vid, s["start"], s["end"], body.get("place"))
    return views().scenes(vid)[n - 1]


@router.get("/videos/{vid}/scenes/{n}/still.jpg")
def scene_still(vid: str, n: int) -> Response:
    rows = views().scene_rows(vid)
    if not 1 <= n <= len(rows):
        raise NotFoundError(f"scene {n} not found")
    s = rows[n - 1]
    t = s["start"] + (s["end"] - s["start"]) * 0.4
    return FileResponse(frame_file(vid, t, 360), media_type="image/jpeg",
                        headers={"Cache-Control": "max-age=86400"})


@router.get("/videos/{vid}/frame.jpg")
def frame(vid: str, t: float, h: int = 240) -> Response:
    return FileResponse(frame_file(vid, t, h), media_type="image/jpeg",
                        headers={"Cache-Control": "max-age=86400"})


@router.get("/videos/{vid}/clip.mp4")
def clip(vid: str, request: Request) -> Response:
    a = _num(request.query_params.get("from")) or 0.0
    b = _num(request.query_params.get("to")) or a + 30
    return FileResponse(clip_file(vid, a, b), media_type="video/mp4")


@router.get("/videos/{vid}/at/{t}", dependencies=[READ])
def at_time(vid: str, t: float) -> dict[str, Any]:
    c, v = core(), views()
    c.store.video(vid)
    n = v.scene_at(vid, t)
    scene = v.scenes(vid)[n - 1] if n else None
    tags = [x for x in c.store.tags(video=vid, status=["accepted", "proposed"]) if x["start"] <= t < x["end"]]
    people = list(scene["people"]) if scene else []
    sig = (c.store.result(vid, "signals") or {}).get("signals") or {}
    here = [k for k, rs in sig.items() if any(a <= t < b for a, b in rs)]
    subs = (c.store.result(vid, "subtitles") or {}).get("lines") or []
    if any(ln["start"] <= t < ln["end"] for ln in subs) and "dialogue" not in here:
        here.append("dialogue")
    return {"t": t, "scene": n, "people": people,
            "mentioned": list(scene["mentioned"]) if scene else [],
            "speakers": list(scene["speakers"]) if scene else [],
            "tags": [{"tag": x["tag"], "name": v.tag_ref(x)["name"], "status": x["status"]} for x in tags],
            "place": scene["place"] if scene else None, "signals": sorted(here)}


@router.get("/videos/{vid}/lines", dependencies=[READ])
def lines(vid: str, request: Request) -> dict[str, Any]:
    lo = _num(request.query_params.get("from"))
    hi = _num(request.query_params.get("to"))
    rows = (core().store.result(vid, "subtitles") or {}).get("lines") or []
    rows = [x for x in rows if (lo is None or x["end"] > lo) and (hi is None or x["start"] < hi)]
    return {"total": len(rows), "items": rows}


@router.get("/videos/{vid}/shots", dependencies=[READ])
def shots(vid: str, request: Request) -> dict[str, Any]:
    lo = _num(request.query_params.get("from"))
    hi = _num(request.query_params.get("to"))
    rows = (core().store.result(vid, "shots") or {}).get("shots") or []
    rows = [x for x in rows if (lo is None or x[1] > lo) and (hi is None or x[0] < hi)]
    return {"total": len(rows), "items": [{"start": a, "end": b} for a, b in rows]}


@router.get("/videos/{vid}/signals", dependencies=[READ])
def signals(vid: str, signal: str | None = None) -> dict[str, Any]:
    core().store.video(vid)
    doc = (core().store.result(vid, "signals") or {}).get("signals") or {}
    items = [{"signal": k, "start": a, "end": b} for k, rs in doc.items() for a, b in rs
             if not signal or k == signal]
    items.sort(key=lambda x: (x["start"], x["signal"]))
    return {"total": len(items), "items": items}


@router.get("/videos/{vid}/faces", dependencies=[READ])
def video_faces(vid: str, person: str | None = None, confirmed: bool | None = None) -> dict[str, Any]:
    core().store.video(vid)
    rows = core().store.faces(video=vid, person=person, confirmed=confirmed)
    return {"total": len(rows), "items": [views().face_view(f) for f in rows]}


@router.get("/videos/{vid}/tags", dependencies=[READ])
def video_tags(vid: str, status: str | None = "accepted", family: str | None = None,
               source: str | None = None) -> dict[str, Any]:
    core().store.video(vid)
    rows = core().store.tags(video=vid, status=None if status in (None, "all") else status)
    if family:
        fam = family.lower()
        rows = [r for r in rows if tag_family(r["tag"]) == fam]
    if source:
        src = source.lower()
        rows = [r for r in rows if source_kind(r["source"]) == src or r["source"] == src]
    return {"total": len(rows), "items": [views().tag_view(r) for r in rows]}


@router.post("/videos/{vid}/tags", dependencies=[PROPOSE])
def propose_tag(vid: str, request: Request, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    """Add a tag. Apps and AI clients propose; the web page may add it kept."""
    c = core()
    v = c.store.video(vid)
    names = body.get("tags") or [body.get("tag")]
    names = [n for n in names if n]
    if not names:
        raise MarcarrError("give a tag")
    a, b = clean_range(body.get("start"), body.get("end"), v["duration"])
    if body.get("snap", True):
        doc = c.pipeline.index_doc(vid)
        if doc["shots"]:
            a, b = idx.snap(doc, a), idx.snap(doc, b)
            if b <= a:
                a, b = clean_range(body.get("start"), body.get("end"), v["duration"])
    who = source_of(request)
    status = body.get("status") or "proposed"
    if who != "person" and status == "accepted":
        status = "proposed"  # an app proposes; a person decides
    ev = body.get("evidence") or {}
    if isinstance(ev, list):
        ev = {"seen": ev}
    people = [str(p) for p in body.get("people") or []]
    mentioned = [str(p) for p in body.get("mentioned") or []]
    out = []
    for name in names:
        tag = tag_id(name)
        if not tag:
            raise MarcarrError(f"bad tag {name!r}")
        row = c.store.add_tag(vid, v["title_id"], tag, a, b, status=status, source=who,
                              confidence=body.get("confidence"), people=people, evidence=ev, mentioned=mentioned,
                              summary=str(body.get("summary") or ""))
        view = views().tag_view(row)
        if status == "proposed":
            c.events.emit("tag.proposed", {"tag": view})
        out.append(view)
    return out[0] if len(out) == 1 else JSONResponse(out)  # type: ignore[return-value]


# -- how characters are in a scene ----------------------------------------------------
@router.get("/videos/{vid}/presence", dependencies=[READ])
def list_presence(vid: str, request: Request) -> dict[str, Any]:
    c = core()
    c.store.video(vid)
    rows = c.store.presence(video=vid, person=request.query_params.get("person") or None,
                            start=_num(request.query_params.get("from")), end=_num(request.query_params.get("to")))
    return {"total": len(rows), "items": [views().presence_view(r) for r in rows]}


@router.post("/videos/{vid}/presence", dependencies=[PROPOSE])
def add_presence(vid: str, request: Request, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    """Report a character in a stretch: seen on screen, mentioned by name, or heard
    speaking. Apps propose; the web page may add it kept."""
    c = core()
    v = c.store.video(vid)
    a, b = clean_range(body.get("start"), body.get("end"), v["duration"])
    who = source_of(request)
    status = body.get("status") or "proposed"
    if who != "person" and status == "accepted":
        status = "proposed"
    at = _num(body.get("at")) if body.get("at") is not None else None
    row = c.store.add_presence(vid, str(body.get("person") or ""), a, b, str(body.get("how") or ""),
                               source=who, status=status, at=at, note=str(body.get("note") or ""))
    return views().presence_view(row)


@router.post("/presence/{pid}/keep", dependencies=[REVIEW])
def keep_presence(pid: str) -> dict[str, Any]:
    return views().presence_view(core().store.set_presence_status(pid, "accepted"))


@router.post("/presence/{pid}/drop", dependencies=[REVIEW])
def drop_presence(pid: str) -> dict[str, Any]:
    return views().presence_view(core().store.set_presence_status(pid, "rejected"))


@router.delete("/presence/{pid}", status_code=204, dependencies=[REVIEW])
def delete_presence(pid: str) -> Response:
    core().store.delete_presence(pid)
    return Response(status_code=204)


# -- the whole analysis in one document -----------------------------------------------
@router.get("/videos/{vid}/analysis", dependencies=[READ])
def analysis(vid: str) -> dict[str, Any]:
    c, v = core(), views()
    vv = c.store.video(vid)
    t = c.store.title(vv["title_id"])
    info = v.info(vid)
    scenes = v.scenes(vid)
    sig = (c.store.result(vid, "signals") or {}).get("signals") or {}
    return {
        "format": "marcarr-analysis/1",
        "title": {"id": t["id"], "name": t["name"], "year": t["year"], "type": t["type"],
                  "season": t["season"], "episode": t["episode"]},
        "video": {"id": vid, "duration": vv["duration"], "width": vv["width"], "height": vv["height"],
                  "edition": vv["edition"], "content_key": vv["content_key"]},
        "steps": {s: i["state"] for s, i in info.items()},
        "shots": (c.store.result(vid, "shots") or {}).get("shots") or [],
        "subtitles": (c.store.result(vid, "subtitles") or {}).get("lines") or [],
        "scenes": [{k: s[k] for k in ("n", "start", "end", "people", "seen", "speakers", "mentioned", "place",
                                    "summary", "still")}
                   | {"tags": [x["name"] for x in s["tags"] if x["status"] == "accepted"]} for s in scenes],
        "tags": [v.tag_view(r) for r in c.store.tags(video=vid, status=["accepted", "proposed"])],
        "signals": [{"signal": k, "start": a, "end": b} for k, rs in sig.items() for a, b in rs],
        "people": v.cast_people(t["id"]),
        "faces": [{"person": f["person_id"], "at": f["at"], "score": round(f["score"], 2),
                   "confirmed": f["confirmed"]} for f in c.store.faces(video=vid)],
    }


STEP_NAMES = STEPS
__all__ = ["router", "stmod"]
