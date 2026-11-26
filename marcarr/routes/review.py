"""Tags (the list, keep and drop), the review queue, scene search, people,
faces and named places."""

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
@router.get("/tags", dependencies=[READ])
def tag_list(family: str | None = None, used: bool = False) -> dict[str, Any]:
    c = core()
    data = vocab.load()
    counts = c.store.tag_counts()
    off = set(c.cfg.tags.families_off)
    labels = set(c.cfg.labels.tags) if c.cfg.labels.write else set()
    fams = []
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
    return {"families": fams, "own": own, "signals": sigs}


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
@router.get("/search/scenes", dependencies=[READ])
def search(request: Request, tags: str = "", person: str | None = None, q: str = "",
           status: str = "accepted", title: str | None = None, page: int = 1, per_page: int = 60) -> dict[str, Any]:
    c, v = core(), views()
    want = [tag_id(x) for x in tags.split(",") if x.strip()]
    statuses = ["accepted", "proposed"] if status in ("proposed", "all") else ["accepted"]
    videos = c.store.current_videos()
    if title:
        videos = [x for x in videos if x["title_id"] == title]
    if want:
        have: dict[str, set[str]] = {}
        for r in c.store.tags(tag=want, status=statuses):
            have.setdefault(r["video_id"], set()).add(r["tag"])
        videos = [x for x in videos if set(want) <= have.get(x["id"], set())]
    ql = q.strip().lower()
    hits = []
    for vid in videos:
        t = c.store.title_or_none(vid["title_id"])
        if t is None:
            continue
        lines = (c.store.result(vid["id"], "subtitles") or {}).get("lines") or [] if ql else []
        if ql and not any(ql in ln["text"].lower() for ln in lines):
            continue
        scenes = v.scenes(vid["id"])
        if not scenes:
            continue
        for s in scenes:
            names = {x["tag"] for x in s["tags"] if x["status"] in statuses}
            if want and not set(want) <= names:
                continue
            if person and person not in s["people"]:
                continue
            line = None
            if ql:
                line = next((ln["text"] for ln in lines if s["start"] <= ln["start"] < s["end"] and ql in ln["text"].lower()), None)
                if line is None:
                    continue
            if not (want or person or ql):
                continue
            hits.append(v.hit({**t, "name": _display_name(t)}, vid["id"], s, line))
    per_page = max(1, min(per_page, 500))
    page = max(1, page)
    return {"total": len(hits), "page": page, "items": hits[(page - 1) * per_page: page * per_page]}


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
    url = c.pipeline.photo_source(p["photo"] or "")
    if not url:
        raise NotFoundError("no photo")
    path = fetch_image(url, "people")
    if path is None:
        raise NotFoundError("no photo")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})


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
