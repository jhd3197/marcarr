"""Tags (the list, custom tags, keep and drop), the review queue, scene search, collections
(saved searches), people, faces and named places."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, Response

from ..errors import MarcarrError, NotFoundError
from ..stages import vocab
from ..store import clean_range, slug
from ..views import FAMILY_NAMES, SUBJECTIVE, source_kind, tag_family, tag_id
from .common import PROPOSE, READ, REVIEW, UI, cache_path, core, fetch_image, frame_file, once, views

router = APIRouter()


# -- the tag list ----------------------------------------------------------------------
def _scene_counts() -> dict[str, dict[str, int]]:
    """Scenes per tag: kept ("accepted") and waiting for review ("proposed").

    Counted the way scene search shows them, so a count and its link agree: only
    videos the library shows, a tag is on a scene when it covers at least half of
    it (the rule in Views.scenes), and a scene with both a kept and a proposed
    range of one tag counts as kept. "rejected" stays a count of dropped ranges,
    since a dropped tag is on no scene."""
    c = core()
    out = {tag: {"accepted": 0, "proposed": 0, "rejected": n["rejected"]}
           for tag, n in c.store.tag_counts().items()}
    by_video: dict[str, list[dict[str, Any]]] = {}
    for r in c.store.tags(status=["accepted", "proposed"]):
        by_video.setdefault(r["video_id"], []).append(r)
    if not by_video:
        return out
    for vid in c.store.current_videos():
        rows = by_video.get(vid["id"])
        if not rows:
            continue
        for s in views().scene_rows(vid["id"]):
            a, b = s["start"], s["end"]
            here: dict[str, str] = {}
            for t in rows:
                if not (t["start"] < b - 0.5 and t["end"] > a + 0.5):
                    continue
                if min(t["end"], b) - max(t["start"], a) < 0.5 * min(b - a, t["end"] - t["start"]):
                    continue
                if here.get(t["tag"]) != "accepted":
                    here[t["tag"]] = t["status"]
            for tag, status in here.items():
                out.setdefault(tag, {"accepted": 0, "proposed": 0, "rejected": 0})[status] += 1
    return out


@router.get("/tags", dependencies=[READ])
def tag_list(family: str | None = None, used: bool = False) -> dict[str, Any]:
    c = core()
    data = vocab.load()
    counts = _scene_counts()
    off = set(c.cfg.tags.families_off)
    labels = set(c.cfg.labels.tags) if c.cfg.labels.write else set()
    fams = []
    zero = {"accepted": 0, "proposed": 0, "rejected": 0}
    mine = []
    for t in c.store.custom_tags():
        f = t["family"]
        if family and (f is None or (f != family.lower() and FAMILY_NAMES.get(f, "").lower() != family.lower())):
            continue
        n = counts.get(t["id"], zero)
        if used and not (n["accepted"] or n["proposed"]):
            continue
        mine.append(_custom_view(t, n, labels, off))
    for f in data["families"]:
        if family and f != family.lower() and FAMILY_NAMES.get(f, "").lower() != family.lower():
            continue
        tags = []
        for t in data["tags"]:
            if t["family"] != f or t.get("retired"):
                continue
            n = counts.get(t["id"], {"accepted": 0, "proposed": 0, "rejected": 0})
            if used and not (n["accepted"] or n["proposed"]):
                continue
            cues = t.get("cues") or {}
            tags.append({"id": t["id"], "name": t["name"], "family": f, "hint": t.get("hint", ""),
                         "see": cues.get("see") or [], "hear": cues.get("hear") or [],
                         "subjective": f in SUBJECTIVE, "label": t["id"] in labels,
                         "off": f in off, "counts": n})
        fams.append({"family": f, "name": FAMILY_NAMES.get(f, f.title()), "subjective": f in SUBJECTIVE,
                     "off": f in off, "tags": tags})
    own = [{"id": t["id"].removeprefix("fc:"), "name": t["name"], "hint": t.get("hint", "")}
           for t in data["cut_tags"]]
    sigs = [{"id": s["id"], "name": s["name"], "hint": s.get("hint", "")} for s in data.get("signals", [])]
    # why the list may be empty: tags come from the AI step
    tagging = {"enabled": c.cfg.ai.enabled, "model": bool(c.cfg.ai.model.strip()),
               "videos_done": c.store.steps_done("tags")}
    return {"mine": mine, "families": fams, "own": own, "signals": sigs, "tagging": tagging}


# -- custom tags ("My tags") -----------------------------------------------------------
def _custom_view(t: dict[str, Any], counts: dict[str, int] | None = None, labels: set[str] | None = None,
                 off: set[str] | None = None) -> dict[str, Any]:
    """A custom tag in the shape of a tag of the list, plus its scope and whether it is retired."""
    c = core()
    if labels is None:
        labels = set(c.cfg.labels.tags) if c.cfg.labels.write else set()
    if off is None:
        off = set(c.cfg.tags.families_off)
    scope = None
    if t["title_id"]:  # one movie, or one show and its episodes
        title = c.store.title_or_none(t["title_id"])
        scope = {"title": t["title_id"], "name": _display_name(title) if title else t["title_id"],
                 "type": title["type"] if title else None, "year": title["year"] if title else None}
    return {"id": t["id"], "name": t["name"], "family": t["family"], "hint": t["hint"],
            "see": t["cues"]["see"], "hear": t["cues"]["hear"],
            "subjective": t["family"] in SUBJECTIVE,
            "label": t["id"] in labels, "off": t["family"] in off,
            "counts": counts if counts is not None else _scene_counts().get(
                t["id"], {"accepted": 0, "proposed": 0, "rejected": 0}),
            "custom": True, "scope": scope, "retired": t["retired"], "created_at": t["created_at"]}


def _custom_body(body: dict[str, Any]) -> dict[str, Any]:
    """The fields of a create or edit body the store takes (scope: a title id, or null)."""
    fields = {k: body[k] for k in ("family", "hint", "see", "hear") if k in body}
    if "scope" in body:
        scope = body["scope"]
        if isinstance(scope, dict):
            scope = scope.get("title")
        if scope is not None and not isinstance(scope, str):
            raise MarcarrError("scope is a show's or a movie's title id, or null for the whole library")
        fields["title_id"] = None if scope in (None, "", "library") else scope
    return fields


@router.post("/tags/mine", dependencies=[UI])
def add_custom_tag(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    row = core().store.add_custom_tag(body.get("name"), tag_id=body.get("id"), **_custom_body(body))
    return _custom_view(row)


@router.patch("/tags/mine/{tag}", dependencies=[UI])
def edit_custom_tag(tag: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    fields = _custom_body(body)
    if "name" in body:
        fields["name"] = body["name"]
    if "retired" in body:
        if not isinstance(body["retired"], bool):
            raise MarcarrError("retired is true or false")
        fields["retired"] = body["retired"]
    return _custom_view(core().store.update_custom_tag(tag, **fields))


@router.delete("/tags/mine/{tag}", dependencies=[UI])
def delete_custom_tag(tag: str) -> dict[str, Any]:
    """Removes a tag no scene has. One that is on any scene is retired instead: its
    scenes keep it, it is no longer proposed."""
    c = core()
    kept = c.store.delete_custom_tag(tag)
    if kept is None and tag in c.cfg.labels.tags:  # nothing left to write to Plex
        from .. import config as cfgmod

        c.save_config(cfgmod.merge_update(c.cfg, {"labels": {"tags": [x for x in c.cfg.labels.tags if x != tag]}}))
    return {"deleted": kept is None, "retired": kept is not None, "tag": _custom_view(kept) if kept else None}


@router.post("/tags/{tag}/label", dependencies=[UI])
def tag_label(tag: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    from .. import config as cfgmod

    c = core()
    tid = tag_id(tag)
    want = list(c.cfg.labels.tags)
    if body.get("label") and tid not in want:
        want.append(tid)
    if not body.get("label"):
        want = [x for x in want if x != tid]
    c.save_config(cfgmod.merge_update(c.cfg, {"labels": {"tags": want}}))
    return {"tag": tid, "label": tid in want}


# -- one tag ---------------------------------------------------------------------------
def _set_status(tid: str, status: str, event: str | None) -> dict[str, Any]:
    c = core()
    row = c.store.update_tag(tid, status=status)
    view = views().tag_view(row)
    if event:
        c.events.emit(event, {"id": tid, "tag": view["name"], "video": row["video_id"], "title": row["title_id"]})
    return view


@router.post("/tags/{tid}/keep", dependencies=[REVIEW])
def keep(tid: str) -> dict[str, Any]:
    return _set_status(tid, "accepted", "tag.kept")


@router.post("/tags/{tid}/drop", dependencies=[REVIEW])
def drop(tid: str) -> dict[str, Any]:
    return _set_status(tid, "rejected", "tag.dropped")


@router.post("/tags/{tid}/undo", dependencies=[REVIEW])
def undo(tid: str) -> dict[str, Any]:
    return _set_status(tid, "proposed", None)


@router.post("/tags/bulk", dependencies=[REVIEW])
def bulk(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    action = body.get("action")
    to = {"keep": ("accepted", "tag.kept"), "drop": ("rejected", "tag.dropped"), "undo": ("proposed", None)}
    if action not in to:
        raise MarcarrError("action is keep, drop or undo")
    status, event = to[action]
    n = 0
    for tid in body.get("ids") or []:
        _set_status(str(tid), status, event)
        n += 1
    return {"changed": n}


@router.patch("/tags/{tid}", dependencies=[REVIEW])
def edit_tag(tid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    c = core()
    cur = c.store.tag(tid)
    fields: dict[str, Any] = {}
    if "start" in body or "end" in body:
        fields["start"], fields["end"] = clean_range(body.get("start", cur["start"]), body.get("end", cur["end"]))
    if "people" in body:
        fields["people"] = [str(p) for p in body["people"] or []]
    if "mentioned" in body:
        fields["mentioned"] = [str(p) for p in body["mentioned"] or []]
    if "tag" in body:
        fields["tag"] = tag_id(body["tag"])
    if "summary" in body:
        fields["summary"] = str(body["summary"] or "")[:500]
    return views().tag_view(c.store.update_tag(tid, **fields)) if fields else views().tag_view(cur)


@router.delete("/tags/{tid}", status_code=204, dependencies=[REVIEW])
def delete_tag(tid: str) -> Response:
    core().store.delete_tag(tid)
    return Response(status_code=204)


# -- the review queue ------------------------------------------------------------------
def _review_items(family: str | None, source: str | None, title: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    c, v = core(), views()
    current = {x["id"]: x for x in c.store.current_videos()}
    rows = [r for r in c.store.tags(status="proposed") if r["video_id"] in current]
    facets: dict[str, Any] = {"families": {}, "sources": {}, "titles": {}}
    titles: dict[str, dict[str, Any]] = {}
    for r in rows:
        fam = tag_family(r["tag"]) or "other"
        facets["families"][fam] = facets["families"].get(fam, 0) + 1
        src = source_kind(r["source"])
        facets["sources"][src] = facets["sources"].get(src, 0) + 1
        facets["titles"][r["title_id"]] = facets["titles"].get(r["title_id"], 0) + 1
    if family:
        rows = [r for r in rows if (tag_family(r["tag"]) or "") == family.lower()]
    if source:
        rows = [r for r in rows if source_kind(r["source"]) == source.lower()]
    if title:
        rows = [r for r in rows if r["title_id"] == title]
    scene_cache: dict[str, list[dict[str, Any]]] = {}
    items = []
    for r in rows:
        t = titles.get(r["title_id"]) or c.store.title_or_none(r["title_id"])
        if t is None:
            continue
        titles[r["title_id"]] = t
        scenes = scene_cache.get(r["video_id"])
        if scenes is None:
            scenes = scene_cache[r["video_id"]] = v.scene_rows(r["video_id"])
        mid = (r["start"] + r["end"]) / 2
        n = next((i + 1 for i, s in enumerate(scenes) if s["start"] <= mid < s["end"]), None)
        items.append({**v.tag_view(r), "title_name": _display_name(t), "year": t["year"], "scene": n,
                      "still": f"/api/v1/videos/{r['video_id']}/frame.jpg?t={r['start'] + (r['end'] - r['start']) * 0.4:.2f}&h=360",
                      "scene_summary": r["summary"]})
    facets["titles"] = [{"id": k, "name": _display_name(titles.get(k) or c.store.title_or_none(k) or {"name": k}), "count": n}
                        for k, n in sorted(facets["titles"].items(), key=lambda kv: -kv[1])]
    return items, facets


def _display_name(t: dict[str, Any]) -> str:
    if t.get("type") == "episode" and t.get("parent_id"):
        show = core().store.title_or_none(t["parent_id"])
        if show:
            return f"{show['name']} S{t['season'] or 0:02d}E{t['episode'] or 0:02d}"
    return str(t.get("name") or "")


@router.get("/review", dependencies=[READ])
def review(family: str | None = None, source: str | None = None, title: str | None = None,
           page: int = 1, per_page: int = 200) -> dict[str, Any]:
    items, facets = _review_items(family, source, title)
    groups: dict[str, dict[str, Any]] = {}
    for it in items:
        g = groups.setdefault(it["video"], {"title": it["title"], "name": it["title_name"], "year": it["year"],
                                            "video": it["video"], "count": 0, "items": []})
        g["count"] += 1
        g["items"].append(it)
    out = list(groups.values())
    for g in out:
        g["items"].sort(key=lambda x: x["start"])
    per_page = max(1, min(per_page, 1000))
    shown, left = [], per_page * max(1, page)
    skip = per_page * (max(1, page) - 1)
    for g in out:
        items_g = g["items"]
        if skip >= len(items_g):
            skip -= len(items_g)
            continue
        take = items_g[skip:skip + left - sum(len(x["items"]) for x in shown) if False else skip + per_page]
        skip = 0
        if take:
            shown.append({**g, "items": take})
        if sum(len(x["items"]) for x in shown) >= per_page:
            break
    return {"total": len(items), "groups": shown, "facets": facets}


@router.get("/review/items", dependencies=[READ])
def review_items(family: str | None = None, source: str | None = None, title: str | None = None,
                 after: str | None = None, limit: int = 50) -> dict[str, Any]:
    items, _ = _review_items(family, source, title)
    if after:
        k = next((i for i, x in enumerate(items) if x["id"] == after), -1)
        items = items[k + 1:]
    return {"total": len(items), "items": items[:max(1, min(limit, 500))]}


# -- scene search ----------------------------------------------------------------------
def _ids(raw: Any) -> list[str]:
    """ "a,b" or ["a", "b"] -> the non-empty parts, in order, once each."""
    parts = raw.split(",") if isinstance(raw, str) else list(raw or [])
    return list(dict.fromkeys(str(x).strip() for x in parts if str(x).strip()))


def _covered(ranges: list[list[float]], a: float, b: float) -> float:
    """Seconds of a..b that the ranges cover (a signal's ranges do not overlap)."""
    return sum(max(0.0, min(y, b) - max(x, a)) for x, y in ranges)


def _find(tags: list[str], person: str | None, q: str, status: str = "accepted", title: str | None = None,
          signals: list[str] | None = None) -> list[tuple[dict[str, Any], str, dict[str, Any], str | None]]:
    """The scenes a search matches, as (title, video id, scene, matching line).

    A scene must have every tag, the person on screen, a dialogue line with the
    words, and every signal over at least half of it. With nothing asked, nothing
    matches."""
    c, v = core(), views()
    want = [tag_id(x) for x in tags]
    sigs = [slug(x) for x in signals or []]
    ql = q.strip().lower()
    if not (want or person or ql or sigs):
        return []
    # accepted: kept only. proposed (or all): kept and waiting. review: waiting only,
    # which leaves out a scene where the tag is already kept.
    statuses = (["accepted", "proposed"] if status in ("proposed", "all")
                else ["proposed"] if status == "review" else ["accepted"])
    videos = c.store.current_videos()
    if title:
        videos = [x for x in videos if x["title_id"] == title]
    if want:
        have: dict[str, set[str]] = {}
        for r in c.store.tags(tag=want, status=statuses):
            have.setdefault(r["video_id"], set()).add(r["tag"])
        videos = [x for x in videos if set(want) <= have.get(x["id"], set())]
    out = []
    for vid in videos:
        t = c.store.title_or_none(vid["title_id"])
        if t is None:
            continue
        measured: dict[str, Any] = {}
        if sigs:  # one more stored document per video, read before the costlier scenes
            measured = (c.store.result(vid["id"], "signals") or {}).get("signals") or {}
            if not all(measured.get(x) for x in sigs):
                continue
        lines = (c.store.result(vid["id"], "subtitles") or {}).get("lines") or [] if ql else []
        if ql and not any(ql in ln["text"].lower() for ln in lines):
            continue
        scenes = v.scenes(vid["id"])
        if not scenes:
            continue
        shown = {**t, "name": _display_name(t)}
        for s in scenes:
            names = {x["tag"] for x in s["tags"] if x["status"] in statuses}
            if want and not set(want) <= names:
                continue
            if person and person not in s["people"]:
                continue
            a, b = s["start"], s["end"]
            if any(_covered(measured[x], a, b) < 0.5 * (b - a) for x in sigs):
                continue
            line = None
            if ql:
                line = next((ln["text"] for ln in lines if a <= ln["start"] < b and ql in ln["text"].lower()), None)
                if line is None:
                    continue
            out.append((shown, vid["id"], s, line))
    return out


@router.get("/search/scenes", dependencies=[READ])
def search(request: Request, tags: str = "", person: str | None = None, q: str = "",
           status: str = "accepted", title: str | None = None, signals: str = "",
           page: int = 1, per_page: int = 60) -> dict[str, Any]:
    v = views()
    hits = [v.hit(t, vid, s, line) for t, vid, s, line in _find(_ids(tags), person, q, status, title, _ids(signals))]
    per_page = max(1, min(per_page, 500))
    page = max(1, page)
    return {"total": len(hits), "page": page, "items": hits[(page - 1) * per_page: page * per_page]}


# -- collections: saved scene searches -------------------------------------------------
def _collection_view(col: dict[str, Any], count: bool = True) -> dict[str, Any]:
    out = {"id": col["id"], "name": col["name"], "tags": col["tags"], "person": col["person"], "q": col["q"],
           "signals": col["signals"], "created_at": col["created_at"]}
    if count:  # kept scenes, found the way scene search finds them
        out["scenes"] = len(_find(col["tags"], col["person"], col["q"], "accepted", None, col["signals"]))
    return out


@router.get("/collections", dependencies=[READ])
def collections() -> dict[str, Any]:
    items = [_collection_view(x) for x in core().store.collections()]
    return {"total": len(items), "items": items}


@router.post("/collections", dependencies=[UI])
def add_collection(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    tags = [tag_id(x) for x in _ids(body.get("tags"))]
    unknown = [x for x in tags if vocab.get(x) is None]
    if unknown:
        raise MarcarrError(f"not in the tag list: {', '.join(unknown)}")
    known = {s["id"] for s in vocab.load().get("signals") or []}
    signals = [slug(x) for x in _ids(body.get("signals"))]
    unknown = [x for x in signals if x not in known]
    if unknown:
        raise MarcarrError(f"not a measured signal: {', '.join(unknown)}")
    col = core().store.add_collection(body.get("name"), tags, str(body.get("person") or "").strip() or None,
                                      " ".join(str(body.get("q") or "").split())[:200], signals)
    return _collection_view(col)


@router.patch("/collections/{cid}", dependencies=[UI])
def rename_collection(cid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    return _collection_view(core().store.rename_collection(cid, body.get("name")))


@router.delete("/collections/{cid}", status_code=204, dependencies=[UI])
def delete_collection(cid: str) -> Response:
    core().store.delete_collection(cid)
    return Response(status_code=204)


# -- people and faces ------------------------------------------------------------------
@router.get("/people", dependencies=[READ])
def people(title: str | None = None, q: str = "") -> dict[str, Any]:
    c, v = core(), views()
    if title:
        items = [{**p, "titles": None} for p in v.cast_people(title)]
        items = [{k: x for k, x in p.items() if k != "titles"} for p in items]
    else:
        counts: dict[str, int] = {}
        order: dict[str, int] = {}
        import json as _json

        for r in c.db.query("SELECT doc FROM casts c JOIN titles t ON t.id = c.title_id WHERE t.type != 'episode'"):
            for cm in _json.loads(r["doc"]):
                counts[cm["person"]] = counts.get(cm["person"], 0) + 1
                order[cm["person"]] = min(order.get(cm["person"], 999), cm.get("order", 999))
        allp = c.store.people()
        items = [v.person_view(allp[pid], counts[pid]) for pid in sorted(counts, key=lambda k: (-counts[k], order[k])) if pid in allp]
    if q:
        ql = q.lower()
        items = [p for p in items if ql in (p["actor"] + " " + p["character"]).lower()]
    return {"total": len(items), "items": items}


@router.get("/people/{pid}", dependencies=[READ])
def person(pid: str) -> dict[str, Any]:
    c, v = core(), views()
    p = c.store.person(pid)
    titles = c.store.titles_with_person(pid)
    hits = _person_hits(pid)
    per: dict[str, int] = {}
    for h in hits:
        per[h["title"]] = per.get(h["title"], 0) + 1
    rows = []
    for tid in titles:
        t = c.store.title_or_none(tid)
        if t:
            rows.append({"id": tid, "name": t["name"], "year": t["year"], "scenes": per.get(tid, 0)})
    franchise = next((t.get("collection") for t in (c.store.title_or_none(x) for x in titles) if t and t.get("collection")), None)
    return {**v.person_view(p, len(titles)), "titles_in": sorted(rows, key=lambda r: (r["year"] or 0, r["name"])),
            "faces_to_confirm": len(c.store.faces(person=pid, confirmed=False)),
            "scene_count": len(hits), "franchise": franchise}


def _person_hits(pid: str, title: str | None = None) -> list[dict[str, Any]]:
    c, v = core(), views()
    out = []
    for vid in c.store.current_videos():
        if title and vid["title_id"] != title:
            continue
        t = c.store.title_or_none(vid["title_id"])
        if t is None:
            continue
        for s in v.scenes(vid["id"]):
            if pid in s["people"]:
                out.append(v.hit({**t, "name": _display_name(t)}, vid["id"], s))
    return out


@router.get("/people/{pid}/scenes", dependencies=[READ])
def person_scenes(pid: str, title: str | None = None) -> dict[str, Any]:
    p = core().store.person(pid)
    hits = _person_hits(pid, title)
    return {"person": views().person_view(p), "total": len(hits), "items": hits}


@router.get("/people/{pid}/faces", dependencies=[READ])
def person_faces(pid: str, confirmed: bool | None = None) -> dict[str, Any]:
    rows = core().store.faces(person=pid, confirmed=confirmed, limit=400)
    return {"total": len(rows), "items": [views().face_view(f) for f in rows]}


@router.get("/people/{pid}/photo")
def person_photo(pid: str) -> Response:
    c = core()
    p = c.store.person(pid)
    local = c.pipeline.local_photo(p["photo"] or "")
    if local is not None:  # an uploaded photo can be replaced, so it is never kept stale
        return FileResponse(local, media_type=PHOTO_TYPES.get(local.suffix, "image/jpeg"),
                            headers={"Cache-Control": "no-cache"})
    url = c.pipeline.photo_source(p["photo"] or "")
    if not url:
        raise NotFoundError("no photo")
    path = fetch_image(url, "people")
    if path is None:
        raise NotFoundError("no photo")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})


PHOTO_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_PHOTO = 10 << 20


def _photo_ext(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


@router.put("/people/{pid}/photo", dependencies=[REVIEW])
async def set_person_photo(pid: str, request: Request) -> dict[str, Any]:
    """Upload a person's photo: the request body is the image itself (JPEG, PNG or
    WebP, up to 10 MB). Faces are matched against it the next time the faces step runs."""
    c = core()
    c.store.person(pid)
    data = await request.body()
    if len(data) > MAX_PHOTO:
        raise MarcarrError("the photo is larger than 10 MB")
    ext = _photo_ext(data)
    if ext is None:
        raise MarcarrError("the photo must be a JPEG, PNG or WebP image")
    folder = c.data_dir / "people"
    folder.mkdir(parents=True, exist_ok=True)
    for old in PHOTO_TYPES:
        (folder / f"{pid}{old}").unlink(missing_ok=True)
    tmp = folder / f"{pid}{ext}.part"
    tmp.write_bytes(data)
    tmp.replace(folder / f"{pid}{ext}")
    p = c.store.set_person_photo(pid, f"local:{pid}{ext}")
    c.pipeline.forget_refs()
    return views().person_view(p)


def _face_set(fid: str, **fields: Any) -> dict[str, Any]:
    return views().face_view(core().store.set_face(fid, **fields))


@router.post("/faces/{fid}/confirm", dependencies=[REVIEW])
def confirm_face(fid: str) -> dict[str, Any]:
    return _face_set(fid, confirmed=1)


@router.post("/faces/{fid}/reject", dependencies=[REVIEW])
def reject_face(fid: str) -> dict[str, Any]:
    return _face_set(fid, confirmed=0)


@router.post("/faces/{fid}/assign", dependencies=[REVIEW])
def assign_face(fid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    core().store.person(str(body.get("person")))
    return _face_set(fid, person_id=str(body["person"]), confirmed=1)


@router.post("/faces/bulk", dependencies=[REVIEW])
def bulk_faces(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    action = body.get("action")
    if action not in ("confirm", "reject"):
        raise MarcarrError("action is confirm or reject")
    n = 0
    for fid in body.get("ids") or []:
        core().store.set_face(str(fid), confirmed=1 if action == "confirm" else 0)
        n += 1
    return {"changed": n}


@router.get("/faces/{fid}/crop.jpg")
def face_crop(fid: str) -> Response:
    f = core().store.face(fid)
    out = cache_path("faces", fid, f["at"], f["box"])

    def make(p: Any) -> None:
        from PIL import Image

        src = frame_file(f["video_id"], f["at"], 720)
        with Image.open(src) as img:
            w, h = img.size
            if f["box"]:
                x, y, bw, bh = f["box"]
                pad = 0.35
                left = max(0, int((x - bw * pad) * w))
                top = max(0, int((y - bh * pad) * h))
                right = min(w, int((x + bw * (1 + pad)) * w))
                bottom = min(h, int((y + bh * (1 + pad)) * h))
                img = img.crop((left, top, right, bottom))
            img.convert("RGB").save(p, "JPEG", quality=85)

    return FileResponse(once(out, make), media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


# -- named places ----------------------------------------------------------------------
def _tree(rows: list[dict[str, Any]], counts: dict[str, int]) -> list[dict[str, Any]]:
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(r)

    def build(r: dict[str, Any]) -> dict[str, Any]:
        kids = [build(k) for k in by_parent.get(r["id"], [])]
        return {"id": r["id"], "name": r["name"], "inside": r["parent_id"], "franchise": r["franchise"],
                "implies": r["implies"], "children": kids, "status": r["status"],
                "scenes": counts.get(r["id"], 0) + sum(k["scenes"] for k in kids)}

    ids = {r["id"] for r in rows}
    return [build(r) for r in rows if r["parent_id"] is None or r["parent_id"] not in ids]


def _place_counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for r in core().store.place_scenes():
        out[r["place_id"]] = out.get(r["place_id"], 0) + 1
    return out


@router.get("/places", dependencies=[READ])
def places(franchise: str | None = None) -> dict[str, Any]:
    c = core()
    rows = c.store.places(franchise)
    counts = _place_counts()
    fr: dict[str, dict[str, Any]] = {}
    for r in c.store.places():
        f = fr.setdefault(r["franchise"], {"name": r["franchise"], "places": 0, "titles": 0})
        f["places"] += 1
    for name, f in fr.items():
        f["titles"] = len(c.store.titles("collection = ? AND type != 'episode'", (name,))) if name else 0
    return {"franchises": list(fr.values()), "items": _tree(rows, counts)}


@router.post("/places", dependencies=[REVIEW])
def add_place(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    c = core()
    p = c.store.add_place(str(body.get("name") or ""), body.get("inside"), str(body.get("franchise") or ""),
                          [tag_id(x) for x in body.get("implies") or []])
    return _tree([p], {})[0]


def _place_full(pid: str) -> dict[str, Any]:
    c = core()
    p = c.store.place(pid)
    rows = [r for r in c.store.places(p["franchise"]) if r["id"] == pid or r["id"].startswith(pid + "/")]
    node = next(n for n in _tree(rows, _place_counts()) if n["id"] == pid)
    path = []
    cur: str | None = pid
    while cur:
        x = c.store.place(cur)
        path.append({"id": x["id"], "name": x["name"]})
        cur = x["parent_id"]
    return {**node, "path": list(reversed(path))}


@router.get("/places/{rest:path}", dependencies=[READ])
def place_get(rest: str) -> dict[str, Any]:
    c, v = core(), views()
    if rest.endswith("/scenes"):
        pid = rest[: -len("/scenes")]
        p = c.store.place(pid)
        hits = []
        for r in c.store.place_scenes(place=pid):
            t = None
            try:
                vv = c.store.video(r["video_id"])
                t = c.store.title_or_none(vv["title_id"])
            except NotFoundError:
                continue
            if t is None:
                continue
            for s in v.scenes(r["video_id"]):
                if s["start"] < r["end"] and s["end"] > r["start"]:
                    hits.append(v.hit({**t, "name": _display_name(t)}, r["video_id"], s))
        return {"place": {"id": p["id"], "name": p["name"], "inside": p["parent_id"], "implies": p["implies"]},
                "total": len(hits), "items": hits}
    return _place_full(rest)


@router.patch("/places/{pid:path}", dependencies=[REVIEW])
def edit_place(pid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    fields: dict[str, Any] = {}
    if body.get("name"):
        fields["name"] = str(body["name"]).strip()[:120]
    if "implies" in body:
        fields["implies"] = [tag_id(x) for x in body["implies"] or []]
    core().store.update_place(pid, **fields)
    return _place_full(pid)


@router.delete("/places/{pid:path}", status_code=204, dependencies=[REVIEW])
def delete_place(pid: str) -> Response:
    core().store.delete_place(pid)
    return Response(status_code=204)


__all__ = ["router", "PROPOSE", "slug"]
