"""Status, settings, setup, activity, connected apps, webhooks, backup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from .. import __version__
from .. import config as cfgmod
from .. import states as stmod
from ..clients.plex import PlexClient
from ..errors import MarcarrError
from ..events import EVENTS
from ..store import STEPS, now
from .common import READ, RUN, UI, core, views

router = APIRouter()


# -- status ----------------------------------------------------------------------------
@router.get("/status", dependencies=[READ])
def status() -> dict[str, Any]:
    c = core()
    depth = c.jobs.depth()
    return {
        "version": __version__,
        "queue": {"running": depth.get("running", 0), "waiting": depth.get("queued", 0)},
        "ai": {"enabled": c.cfg.ai.enabled, "month_cost": round(c.store.month_cost(), 4),
               "month_limit": c.cfg.ai.monthly_limit},
        "plex": c.plex_state(),
        "review": c.store.review_count(),
        "setup_done": c.cfg.setup_done,
        "paused": c.worker.paused.is_set(),
    }


# -- settings --------------------------------------------------------------------------
def _settings_view() -> dict[str, Any]:
    c = core()
    d = cfgmod.masked(c.cfg)
    d["faces"]["models"] = stmod.models_present(c.data_dir)
    d["server"] = {"require_key": c.cfg.server.require_key, "data_dir": str(c.data_dir.resolve()),
                   "public_url": c.cfg.server.public_url}
    d["plex"]["path_map"] = [{"from": m.from_, "to": m.to} for m in c.cfg.plex.path_map]
    for k in ("catalogues", "ffmpeg", "setup_done"):
        d.pop(k, None)
    d["catalogues"] = {"tmdb_api_key": cfgmod.MASK if c.cfg.catalogues.tmdb_api_key else ""}
    return d


@router.get("/settings", dependencies=[UI])
def get_settings() -> dict[str, Any]:
    return _settings_view()


@router.put("/settings", dependencies=[UI])
def put_settings(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    c = core()
    body = json.loads(json.dumps(body))
    faces = body.get("faces")
    if isinstance(faces, dict):
        faces.pop("models", None)
    server = body.get("server")
    if isinstance(server, dict):
        server.pop("data_dir", None)
    body.pop("places", None)  # not stored yet: places come from people for now
    at_once_before = c.cfg.analysis.at_once
    c.save_config(cfgmod.merge_update(c.cfg, body))
    if c.cfg.analysis.at_once != at_once_before:
        c.worker.set_heavy(int(c.cfg.analysis.at_once))
    return _settings_view()


@router.post("/settings/plex/test", dependencies=[UI])
def test_plex(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    c = core()
    url = str(body.get("url") or c.cfg.plex.url).strip()
    token = str(body.get("token") or "")
    if not token or token == cfgmod.MASK:
        token = c.cfg.plex.token
    if not url or not token:
        return {"ok": False, "name": "", "libraries": [], "error": "Give the server address and a token"}
    plex = PlexClient(url, token, timeout=10)
    try:
        ident = plex.identity()
        libs = []
        for s in plex.sections():
            if s["type"] in ("movie", "show"):
                try:
                    n = plex.section_count(s["key"])
                except MarcarrError:
                    n = None
                libs.append({**s, "count": n})
    except MarcarrError as exc:
        return {"ok": False, "name": "", "libraries": [], "error": str(exc)}
    return {"ok": True, "name": ident.get("friendlyName", ""), "libraries": libs}


class _Reply(BaseModel):
    answer: str


@router.post("/settings/ai/test", dependencies=[UI])
def test_ai() -> dict[str, Any]:
    """One short question to the saved text model and one tiny picture to the vision
    model. Costs a fraction of a cent; counted in this month's AI spending."""
    import io
    import time

    from PIL import Image

    from .. import ai

    c = core()
    if not c.cfg.ai.model.strip():
        raise MarcarrError("Pick a text model first")

    def check(images: list[bytes] | None) -> dict[str, Any]:
        model = (c.cfg.ai.vision_model if images and c.cfg.ai.vision_model else c.cfg.ai.model)
        t0 = time.monotonic()
        with ai.metered() as m:
            try:
                prompt = ("What colour is this picture? One word." if images
                          else "Reply with the word ok.")
                ai.ask_json(c.cfg.ai, _Reply, "Answer in JSON.", prompt, images=images,
                            retries=0, max_tokens=300)
                ok, err = True, ""
            except Exception as exc:  # noqa: BLE001 - shown to the person, not raised
                ok, err = False, str(exc)[:300]
        c.store.add_usage(None, "test", m.cost, m.tokens)
        return {"ok": ok, "model": model, "seconds": round(time.monotonic() - t0, 2),
                "cost": round(m.cost, 5), "error": err}

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (220, 30, 30)).save(buf, "PNG")
    return {"text": check(None), "vision": check([buf.getvalue()])}


@router.get("/plex/libraries", dependencies=[UI])
def plex_libraries() -> list[dict[str, Any]]:
    return core().library.sections()


@router.post("/library/scan", dependencies=[RUN])
def scan() -> dict[str, Any]:
    job = core().library.submit_scan()
    return {"queued": True, "job": job["id"]}


@router.post("/setup/done", dependencies=[UI])
def setup_done() -> dict[str, Any]:
    c = core()
    c.save_config(cfgmod.merge_update(c.cfg, {"setup_done": True}))
    return status()


@router.post("/faces/models/download", dependencies=[UI])
def download_models() -> dict[str, Any]:
    job = core().worker.submit("face_models", "Download the face models", {})
    return {"queued": True, "job": job["id"]}


@router.post("/plex/labels", dependencies=[UI])
def write_labels() -> dict[str, Any]:
    job = core().worker.submit("labels", "Write labels to Plex", {})
    return {"queued": True, "job": job["id"]}


# -- activity --------------------------------------------------------------------------
def _avg_seconds() -> dict[str, float]:
    out = {}
    for r in core().db.query("SELECT step, AVG(seconds) AS s FROM steps WHERE state = 'done'"
                             " AND seconds IS NOT NULL GROUP BY step"):
        out[r["step"]] = float(r["s"] or 0)
    return out


@router.get("/activity", dependencies=[READ])
def activity(filter: str = "all") -> dict[str, Any]:
    c, v = core(), views()
    all_rows = c.store.all_step_rows()
    avg = _avg_seconds()
    rows = []
    running = None
    left_videos = 0
    left_eta = 0.0
    idle = 0
    for vid in c.store.current_videos():
        t = c.store.title_or_none(vid["title_id"])
        if t is None:
            continue
        rows_of = all_rows.get(vid["id"], {})
        if not rows_of:
            idle += 1  # never touched: counted, not listed (a library has thousands)
            continue
        info = v.info(vid["id"], rows_of)
        line = stmod.state_line(info)
        name = t["name"]
        if t["type"] == "episode" and t["parent_id"]:
            show = c.store.title_or_none(t["parent_id"])
            name = f"{show['name'] if show else ''} S{t['season'] or 0:02d}E{t['episode'] or 0:02d}"
        meta = " · ".join(x for x in (str(t["year"] or ""), length(vid["duration"])) if x)
        rows.append({
            "video": vid["id"], "title": t["id"], "title_name": name, "meta": meta,
            "steps": {s: i["state"] for s, i in info.items()}, "step_info": info,
            "seconds": round(sum(i["seconds"] or 0 for i in info.values()), 1),
            "ai_cost": round(sum(i["ai_cost"] or 0 for i in info.values()), 4), "state": line,
        })
        todo = [s for s, i in info.items() if i["state"] in ("queued", "run")]
        if todo:
            left_videos += 1
            left_eta += sum(avg.get(s, 0) * (1 - (info[s]["progress"] or 0)) for s in todo)
        if running is None and line["kind"] == "run":
            step = next(s for s in STEPS if info[s]["state"] == "run")
            p = info[step]["progress"]
            eta = avg.get(step) * (1 - (p or 0)) if avg.get(step) else None
            running = {"video": vid["id"], "title_name": name, "step": step,
                       "step_index": STEPS.index(step) + 1, "progress": p, "eta_seconds": eta}
    kinds = {"all": lambda r: True, "running": lambda r: r["state"]["kind"] == "run",
             "waiting": lambda r: r["state"]["kind"] in ("queued", "notrun", "rerun"),
             "failed": lambda r: r["state"]["kind"] == "failed",
             "done": lambda r: r["state"]["kind"] == "done"}
    counts = {k: sum(1 for r in rows if f(r)) for k, f in kinds.items()}
    counts["not_analysed"] = idle
    order = {"run": 0, "queued": 1, "failed": 2, "rerun": 3, "notrun": 4, "done": 5}
    rows.sort(key=lambda r: order.get(r["state"]["kind"], 9))
    shown = [r for r in rows if kinds.get(filter, kinds["all"])(r)]
    films = c.db.one("SELECT COUNT(DISTINCT video_id) AS n FROM steps WHERE finished_at >= ?",
                     (_month(),))
    nfilms = int(films["n"]) if films else 0
    secs = c.store.month_seconds()
    cost = c.store.month_cost()
    return {
        "paused": c.worker.paused.is_set(), "running": running,
        "left": {"videos": left_videos, "eta_seconds": round(left_eta) if left_eta else None},
        "month": {"seconds": round(secs), "ai_cost": round(cost, 4), "ai_limit": c.cfg.ai.monthly_limit,
                  "per_film_seconds": round(secs / nfilms) if nfilms else None,
                  "per_film_cost": round(cost / nfilms, 4) if nfilms else None},
        "rows": shown, "counts": counts,
    }


def length(s: float | None) -> str:
    if not s:
        return ""
    h, m = int(s // 3600), round((s % 3600) / 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _month() -> str:
    from ..store import month_start

    return month_start()


@router.post("/activity/analyse", dependencies=[RUN])
def analyse_left() -> dict[str, Any]:
    return {"queued": core().pipeline.submit_left()}


@router.post("/activity/pause", dependencies=[RUN])
def pause() -> dict[str, Any]:
    c = core()
    c.worker.pause()
    c.store.set_kv("paused", True)
    return activity()


@router.post("/activity/resume", dependencies=[RUN])
def resume() -> dict[str, Any]:
    c = core()
    c.worker.resume()
    c.store.set_kv("paused", False)
    return activity()


@router.get("/jobs", dependencies=[READ])
def jobs(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return core().jobs.list(limit=max(1, min(limit, 500)), status=status)


@router.post("/jobs/{jid}/cancel", dependencies=[RUN])
def cancel_job(jid: str) -> dict[str, Any]:
    return core().worker.cancel(jid)


# -- connected apps --------------------------------------------------------------------
@router.get("/keys", dependencies=[UI])
def keys() -> list[dict[str, Any]]:
    return core().keys.list()


@router.post("/keys", dependencies=[UI])
def add_key(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    return core().keys.add(str(body.get("name") or ""), list(body.get("scopes") or ["read"]))


@router.post("/keys/{kid}/renew", dependencies=[UI])
def renew_key(kid: str) -> dict[str, Any]:
    return core().keys.renew(kid)


@router.delete("/keys/{kid}", status_code=204, dependencies=[UI])
def delete_key(kid: str) -> Response:
    core().keys.delete(kid)
    return Response(status_code=204)


# -- webhooks --------------------------------------------------------------------------
@router.get("/webhooks", dependencies=[UI])
def webhooks() -> list[dict[str, Any]]:
    ev = core().events
    return [ev.public(h) for h in ev.hooks()]


@router.post("/webhooks", dependencies=[UI])
def add_webhook(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    ev = core().events
    return ev.public(ev.add_hook(str(body.get("url") or ""), list(body.get("events") or [])))


@router.patch("/webhooks/{hid}", dependencies=[UI])
def edit_webhook(hid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    ev = core().events
    return ev.public(ev.edit_hook(hid, body.get("url"), body.get("events"), body.get("enabled")))


@router.delete("/webhooks/{hid}", status_code=204, dependencies=[UI])
def delete_webhook(hid: str) -> Response:
    core().events.delete_hook(hid)
    return Response(status_code=204)


@router.post("/webhooks/{hid}/test", dependencies=[UI])
def test_webhook(hid: str) -> dict[str, Any]:
    return core().events.test(hid)


@router.get("/webhooks/calls", dependencies=[UI])
def webhook_calls() -> list[dict[str, Any]]:
    return core().events.calls()


@router.post("/webhooks/calls/{cid}/resend", dependencies=[UI])
def resend(cid: str) -> dict[str, Any]:
    return core().events.resend(cid)


@router.get("/events", dependencies=[READ])
def events() -> list[dict[str, Any]]:
    return [{"name": k, "what": v, "example": {"event": k}} for k, v in EVENTS.items()]


# -- backup ----------------------------------------------------------------------------
@router.get("/backup/export", dependencies=[UI])
def export() -> Response:
    """What a person decided: kept and dropped tags, confirmed faces, named places,
    scene corrections. Analysis results are left out: they can be made again."""
    c = core()
    db = c.db
    tags = [dict(r) for r in db.query(
        "SELECT t.*, v.content_key FROM tags t JOIN videos v ON v.id = t.video_id"
        " WHERE t.status != 'proposed' OR t.source NOT LIKE 'ai:%'")]
    faces = [dict(r) for r in db.query(
        "SELECT f.*, v.content_key FROM faces f JOIN videos v ON v.id = f.video_id WHERE f.confirmed IS NOT NULL")]
    edits = [dict(r) for r in db.query(
        "SELECT e.*, v.content_key FROM scene_edits e JOIN videos v ON v.id = e.video_id")]
    doc = {"format": "marcarr-backup/1", "made_at": now(), "tags": tags, "faces": faces,
           "scene_edits": edits, "places": [dict(r) for r in db.query("SELECT * FROM places")],
           "place_scenes": [dict(r) for r in db.query(
               "SELECT p.*, v.content_key FROM place_scenes p JOIN videos v ON v.id = p.video_id")]}
    return JSONResponse(doc, headers={"Content-Disposition": 'attachment; filename="marcarr-backup.json"'})


@router.post("/backup/import", dependencies=[UI])
def import_backup(doc: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    if doc.get("format") != "marcarr-backup/1":
        raise MarcarrError("not a Marcarr backup file")
    c = core()
    db = c.db
    vids = {r["content_key"]: r["id"] for r in db.query("SELECT id, content_key FROM videos")}
    n = {"tags": 0, "faces": 0, "scene_edits": 0, "places": 0, "skipped": 0}
    with db.transaction():
        for p in sorted(doc.get("places") or [], key=lambda p: p["id"].count("/")):
            db.execute("INSERT OR IGNORE INTO places (id, name, parent_id, franchise, implies, status, source, created_at)"
                       " VALUES (?,?,?,?,?,?,?,?)", (p["id"], p["name"], p["parent_id"], p["franchise"],
                                                     p["implies"], p["status"], p["source"], p["created_at"]))
            n["places"] += 1
        for kind, cols in (("tags", ("id", "video_id", "title_id", "tag", "start", "end", "status", "source",
                                     "confidence", "people", "evidence", "summary", "created_at", "updated_at")),
                           ("faces", ("id", "video_id", "person_id", "at", "score", "box", "confirmed", "created_at")),
                           ("scene_edits", ("video_id", "kind", "at", "created_at")),
                           ("place_scenes", ("place_id", "video_id", "start", "end", "status", "source", "created_at"))):
            for r in doc.get(kind) or []:
                vid = vids.get(r.get("content_key"))
                if vid is None:
                    n["skipped"] += 1
                    continue
                r = {**r, "video_id": vid}
                db.execute(f"INSERT OR REPLACE INTO {kind} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",  # noqa: S608
                           tuple(r.get(k) for k in cols))
                if kind in n:
                    n[kind] += 1
    return {"imported": n}


@router.get("/logs", dependencies=[UI])
def logs() -> Response:
    path = core().data_dir / "marcarr.log"
    if not path.is_file():
        return Response("No log yet.\n", media_type="text/plain")
    return FileResponse(path, media_type="text/plain", filename="marcarr.log")


@router.post("/places/import", dependencies=[UI])
def import_places(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    raise MarcarrError("Importing places from a fan wiki comes in a later version")


__all__ = ["router", "Path"]
