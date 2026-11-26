"""Reads and writes over the database: titles, videos, steps, results, tags,
faces, people, places. No HTTP and no media here; views.py shapes rows for
the API and pipeline.py runs the steps."""

from __future__ import annotations

import datetime as _dt
import json
import re
import unicodedata
import uuid
from typing import Any

from .db import Database, dumps
from .errors import MarcarrError, NotFoundError
from .stages import vocab

STEPS = ("shots", "subtitles", "scenes", "signals", "cast", "faces", "tags")
STATUSES = ("proposed", "accepted", "rejected")
CUT_KINDS = ("added", "longer", "removed")
MAX_SUMMARY = 500
MAX_CUES = 12  # per kind, on a custom tag
MAX_CUE = 60
MAX_HINT = 300


def now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def month_start() -> str:
    d = _dt.date.today().replace(day=1)
    return d.isoformat()


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def clean_range(start: Any, end: Any, duration: float | None = None) -> tuple[float, float]:
    try:
        a, b = float(start), float(end)
    except (TypeError, ValueError) as exc:
        raise MarcarrError("start and end must be seconds") from exc
    if a < 0 or b <= a:
        raise MarcarrError("end must be after start, both from 0")
    if duration and b > duration + 5:
        raise MarcarrError(f"end {b:.1f}s is past the video's end ({duration:.1f}s)")
    return round(a, 3), round(b, 3)


def clean_cues(raw: Any) -> list[str]:
    """ "a, b" or ["a", "b"] -> the cue words, trimmed, once each."""
    if raw is None:
        return []
    if not isinstance(raw, (str, list, tuple)):
        raise MarcarrError("cues are a list of words, or words separated by commas")
    parts = raw.split(",") if isinstance(raw, str) else list(raw)
    words = [" ".join(str(x).split())[:MAX_CUE] for x in parts]
    return list(dict.fromkeys(w for w in words if w))[:MAX_CUES]


class Store:
    def __init__(self, db: Database):
        self.db = db
        self._custom: list[dict[str, Any]] | None = None  # custom tags, read once per change

    # -- key/value ---------------------------------------------------------------------
    def kv(self, key: str, default: Any = None) -> Any:
        row = self.db.one("SELECT value FROM kv WHERE key = ?", (key,))
        return json.loads(row["value"]) if row else default

    def set_kv(self, key: str, value: Any) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, dumps(value)))

    # -- titles ------------------------------------------------------------------------
    def upsert_title(self, t: dict[str, Any]) -> None:
        cur = self.db.one("SELECT id FROM titles WHERE id = ?", (t["id"],))
        stamp = now()
        cols = ("type", "name", "sort_name", "year", "parent_id", "season", "episode", "plex_key",
                "plex_section", "tmdb_id", "tvdb_id", "imdb_id", "collection", "summary", "poster",
                "duration", "file")
        vals = [t.get(c) for c in cols]
        vals = [v if v is not None or c in ("year", "parent_id", "season", "episode", "plex_key",
                                            "plex_section", "tmdb_id", "tvdb_id", "imdb_id",
                                            "collection", "duration") else "" for c, v in zip(cols, vals, strict=True)]
        if cur is None:
            self.db.execute(
                f"INSERT INTO titles (id, {', '.join(cols)}, gone, added_at, updated_at)"  # noqa: S608
                f" VALUES (?, {', '.join('?' * len(cols))}, 0, ?, ?)",
                (t["id"], *vals, stamp, stamp))
        else:
            self.db.execute(
                f"UPDATE titles SET {', '.join(c + ' = ?' for c in cols)}, gone = 0,"  # noqa: S608
                " updated_at = ? WHERE id = ?", (*vals, stamp, t["id"]))

    def title(self, tid: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM titles WHERE id = ?", (tid,))
        if row is None:
            raise NotFoundError(f"title {tid} not found")
        return dict(row)

    def title_or_none(self, tid: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT * FROM titles WHERE id = ?", (tid,))
        return dict(row) if row else None

    def titles(self, where: str = "1=1", args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            f"SELECT * FROM titles WHERE gone = 0 AND {where}"  # noqa: S608
            " ORDER BY sort_name, year", args)]

    def mark_gone(self, seen: set[str], sections: list[str]) -> int:
        """Titles of the scanned sections that Plex no longer lists."""
        if not sections:
            return 0
        rows = self.db.query(
            f"SELECT id FROM titles WHERE gone = 0 AND plex_section IN"  # noqa: S608
            f" ({','.join('?' * len(sections))})", sections)
        gone = [r["id"] for r in rows if r["id"] not in seen]
        for tid in gone:
            self.db.execute("UPDATE titles SET gone = 1 WHERE id = ?", (tid,))
        return len(gone)

    # -- videos ------------------------------------------------------------------------
    def video_at(self, path: str, size: int, mtime: float) -> dict[str, Any] | None:
        row = self.db.one("SELECT * FROM videos WHERE path = ? AND size = ? AND mtime = ?",
                          (path, size, mtime))
        return dict(row) if row else None

    def upsert_video(self, title_id: str, path: str, ident: dict[str, Any], edition: str,
                     *, main: bool = True) -> str:
        """Add or update a video. *main*: it becomes the title's current video and the
        title's other videos stop being current; another version leaves them alone."""
        from .identity import video_id

        stamp = now()
        key = ident["content_key"]
        row = self.db.one("SELECT id, title_id FROM videos WHERE content_key = ?", (key,))
        with self.db.transaction():
            if main:
                self.db.execute("UPDATE videos SET current = 0 WHERE title_id = ? AND content_key != ?",
                                (title_id, key))
            if row is None:
                vid = video_id(key)
                while self.db.one("SELECT 1 FROM videos WHERE id = ?", (vid,)):
                    vid = uuid.uuid4().hex[:8]
                self.db.execute(
                    "INSERT INTO videos (id, content_key, title_id, path, edition, size, duration,"
                    " width, height, streams, mtime, current, first_seen, last_seen)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (vid, key, title_id, path, edition, ident.get("size"), ident.get("duration"),
                     ident.get("width"), ident.get("height"), dumps(ident.get("streams") or []),
                     ident.get("mtime"), 1 if main else 0, stamp, stamp))
                return vid
            self.db.execute(
                "UPDATE videos SET title_id = ?, path = ?, mtime = ?, last_seen = ?, in_plex = 1,"
                " edition = CASE WHEN ? != '' THEN ? ELSE edition END"
                + (", current = 1" if main else "") + " WHERE id = ?",
                (title_id, path, ident.get("mtime"), stamp, edition, edition, row["id"]))
            return str(row["id"])

    def touch_video(self, vid: str, title_id: str, *, main: bool = True) -> None:
        with self.db.transaction():
            if main:
                self.db.execute("UPDATE videos SET current = 0 WHERE title_id = ? AND id != ?",
                                (title_id, vid))
            self.db.execute("UPDATE videos SET title_id = ?, last_seen = ?, in_plex = 1"
                            + (", current = 1" if main else "") + " WHERE id = ?",
                            (title_id, now(), vid))

    def set_present(self, title_id: str, ids: list[str]) -> None:
        """The title's videos Plex lists now are *ids*; the others are marked gone."""
        marks = ",".join("?" * len(ids))
        self.db.execute(f"UPDATE videos SET in_plex = CASE WHEN id IN ({marks}) THEN 1 ELSE 0 END"
                        " WHERE title_id = ?", (*ids, title_id))

    def video(self, vid: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM videos WHERE id = ?", (vid,))
        if row is None:
            raise NotFoundError(f"video {vid} not found")
        d = dict(row)
        d["streams"] = json.loads(d["streams"] or "[]")
        return d

    def videos_of(self, title_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT * FROM videos WHERE title_id = ? ORDER BY current DESC, last_seen DESC",
            (title_id,))]

    def current_video(self, title_id: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT * FROM videos WHERE title_id = ? AND current = 1"
                          " ORDER BY last_seen DESC LIMIT 1", (title_id,))
        return dict(row) if row else None

    def current_videos(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT v.* FROM videos v JOIN titles t ON t.id = v.title_id"
            " WHERE v.current = 1 AND t.gone = 0 ORDER BY t.sort_name, t.season, t.episode")]

    # -- steps -------------------------------------------------------------------------
    def step_rows(self, vid: str) -> dict[str, dict[str, Any]]:
        out = {}
        for r in self.db.query("SELECT * FROM steps WHERE video_id = ?", (vid,)):
            d = dict(r)
            d["inputs"] = json.loads(d["inputs"] or "{}")
            out[d["step"]] = d
        return out

    def all_step_rows(self) -> dict[str, dict[str, dict[str, Any]]]:
        out: dict[str, dict[str, dict[str, Any]]] = {}
        for r in self.db.query("SELECT * FROM steps"):
            d = dict(r)
            d["inputs"] = json.loads(d["inputs"] or "{}")
            out.setdefault(d["video_id"], {})[d["step"]] = d
        return out

    def set_step(self, vid: str, step: str, **fields: Any) -> None:
        if "inputs" in fields:
            fields["inputs"] = dumps(fields["inputs"])
        cur = self.db.one("SELECT 1 FROM steps WHERE video_id = ? AND step = ?", (vid, step))
        if cur is None:
            fields.setdefault("state", "notrun")
            cols = ["video_id", "step", *fields]
            self.db.execute(
                f"INSERT INTO steps ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",  # noqa: S608
                (vid, step, *fields.values()))
        elif fields:
            self.db.execute(
                f"UPDATE steps SET {', '.join(k + ' = ?' for k in fields)}"  # noqa: S608
                " WHERE video_id = ? AND step = ?", (*fields.values(), vid, step))

    # -- results -----------------------------------------------------------------------
    def result(self, vid: str, step: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT doc FROM results WHERE video_id = ? AND step = ?", (vid, step))
        return json.loads(row["doc"]) if row else None

    def save_result(self, vid: str, step: str, doc: dict[str, Any]) -> None:
        self.db.execute("INSERT OR REPLACE INTO results (video_id, step, doc, updated_at)"
                        " VALUES (?,?,?,?)", (vid, step, dumps(doc), now()))

    def scene_edits(self, vid: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT kind, at FROM scene_edits WHERE video_id = ? ORDER BY at", (vid,))]

    def add_scene_edit(self, vid: str, kind: str, at: float) -> None:
        self.db.execute("INSERT OR REPLACE INTO scene_edits (video_id, kind, at, created_at)"
                        " VALUES (?,?,?,?)", (vid, kind, round(at, 3), now()))

    def drop_scene_edits_near(self, vid: str, at: float, within: float = 0.05) -> None:
        self.db.execute("DELETE FROM scene_edits WHERE video_id = ? AND abs(at - ?) <= ?",
                        (vid, at, within))

    # -- cast and people ---------------------------------------------------------------
    def cast(self, title_id: str) -> list[dict[str, Any]]:
        row = self.db.one("SELECT doc FROM casts WHERE title_id = ?", (title_id,))
        return json.loads(row["doc"]) if row else []

    def save_cast(self, title_id: str, source: str, cast: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Store a title's cast and make sure each member is a person; returns the
        entries with their person ids."""
        out = []
        stamp = now()
        for c in cast:
            pid = slug(c.get("character") or "") or slug(c.get("name") or "")
            if not pid:
                continue
            row = self.db.one("SELECT * FROM people WHERE id = ?", (pid,))
            if row is None:
                self.db.execute("INSERT INTO people (id, actor, character, photo, updated_at)"
                                " VALUES (?,?,?,?,?)",
                                (pid, c.get("name") or "", c.get("character") or "",
                                 c.get("photo") or "", stamp))
            elif not row["photo"] and c.get("photo"):
                self.db.execute("UPDATE people SET photo = ? WHERE id = ?", (c["photo"], pid))
            out.append({"person": pid, "actor": c.get("name") or "",
                        "character": c.get("character") or "", "photo": c.get("photo") or "",
                        "order": c.get("order", len(out))})
        self.db.execute("INSERT OR REPLACE INTO casts (title_id, source, doc, updated_at)"
                        " VALUES (?,?,?,?)", (title_id, source, dumps(out), stamp))
        return out

    def person(self, pid: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM people WHERE id = ?", (pid,))
        if row is None:
            raise NotFoundError(f"person {pid} not found")
        return dict(row)

    def people(self, ids: list[str] | None = None) -> dict[str, dict[str, Any]]:
        if ids is not None:
            if not ids:
                return {}
            rows = self.db.query(f"SELECT * FROM people WHERE id IN ({','.join('?' * len(ids))})",  # noqa: S608
                                 ids)
        else:
            rows = self.db.query("SELECT * FROM people ORDER BY character, actor")
        return {r["id"]: dict(r) for r in rows}

    def titles_with_person(self, pid: str) -> list[str]:
        out = []
        for r in self.db.query("SELECT title_id, doc FROM casts"):
            if any(c.get("person") == pid for c in json.loads(r["doc"])):
                out.append(r["title_id"])
        return out

    # -- tags --------------------------------------------------------------------------
    @staticmethod
    def _tag(r: Any) -> dict[str, Any]:
        d = dict(r)
        d["people"] = json.loads(d["people"] or "[]")
        ev = json.loads(d["evidence"] or "{}")
        d["evidence"] = {"heard": list(ev.get("heard") or []), "seen": list(ev.get("seen") or [])}
        return d

    def add_tag(self, vid: str, title_id: str, tag: str, start: float, end: float, *,
                status: str = "proposed", source: str = "person", confidence: float | None = None,
                people: list[str] | None = None, evidence: dict[str, list[str]] | None = None,
                summary: str = "") -> dict[str, Any]:
        if status not in STATUSES:
            raise MarcarrError(f"status must be one of {', '.join(STATUSES)}")
        tid = "tag_" + uuid.uuid4().hex[:10]
        stamp = now()
        ev = evidence or {}
        self.db.execute(
            "INSERT INTO tags (id, video_id, title_id, tag, start, end, status, source, confidence,"
            " people, evidence, summary, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, vid, title_id, tag, start, end, status, source[:80], confidence,
             dumps(list(dict.fromkeys(people or []))[:40]),
             dumps({"heard": [str(x)[:60] for x in ev.get("heard") or []][:12],
                    "seen": [str(x)[:60] for x in ev.get("seen") or []][:12]}),
             (summary or "")[:MAX_SUMMARY], stamp, stamp))
        return self.tag(tid)

    def tag(self, tid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM tags WHERE id = ?", (tid,))
        if r is None:
            raise NotFoundError(f"tag {tid} not found")
        return self._tag(r)

    def update_tag(self, tid: str, **fields: Any) -> dict[str, Any]:
        self.tag(tid)
        if "people" in fields:
            fields["people"] = dumps(fields["people"])
        if "evidence" in fields:
            fields["evidence"] = dumps(fields["evidence"])
        if "status" in fields and fields["status"] not in STATUSES:
            raise MarcarrError(f"status must be one of {', '.join(STATUSES)}")
        fields["updated_at"] = now()
        self.db.execute(f"UPDATE tags SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",  # noqa: S608
                        (*fields.values(), tid))
        return self.tag(tid)

    def delete_tag(self, tid: str) -> None:
        self.tag(tid)
        self.db.execute("DELETE FROM tags WHERE id = ?", (tid,))

    def tags(self, *, video: str | None = None, videos: list[str] | None = None,
             title: str | None = None, status: str | list[str] | None = None,
             tag: str | list[str] | None = None, source: str | None = None,
             start: float | None = None, end: float | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM tags WHERE 1=1", []
        if video:
            sql += " AND video_id = ?"
            args.append(video)
        if videos is not None:
            if not videos:
                return []
            sql += f" AND video_id IN ({','.join('?' * len(videos))})"
            args += videos
        if title:
            sql += " AND title_id = ?"
            args.append(title)
        if status:
            sts = [status] if isinstance(status, str) else status
            sql += f" AND status IN ({','.join('?' * len(sts))})"
            args += sts
        if tag:
            tgs = [tag] if isinstance(tag, str) else tag
            sql += f" AND tag IN ({','.join('?' * len(tgs))})"
            args += tgs
        if source:
            if source == "ai":
                sql += " AND source LIKE 'ai:%'"
            else:
                sql += " AND source = ?"
                args.append(source)
        if start is not None:
            sql += " AND end > ?"
            args.append(start)
        if end is not None:
            sql += " AND start < ?"
            args.append(end)
        return [self._tag(r) for r in self.db.query(sql + " ORDER BY video_id, start", args)]

    def overlapping(self, vid: str, start: float, end: float, tag: str) -> dict[str, Any] | None:
        """A tag of the same kind over this range, rejected ones included (a dropped
        tag must not come back on a rerun)."""
        r = self.db.one("SELECT * FROM tags WHERE video_id = ? AND tag = ? AND start < ? AND end > ?"
                        " LIMIT 1", (vid, tag, end, start))
        return self._tag(r) if r else None

    def drop_ai_proposals(self, vid: str) -> int:
        n = self.db.one("SELECT COUNT(*) AS n FROM tags WHERE video_id = ? AND status = 'proposed'"
                        " AND source LIKE 'ai:%'", (vid,))
        self.db.execute("DELETE FROM tags WHERE video_id = ? AND status = 'proposed'"
                        " AND source LIKE 'ai:%'", (vid,))
        return int(n["n"]) if n else 0

    def review_count(self) -> int:
        r = self.db.one("SELECT COUNT(*) AS n FROM tags t JOIN videos v ON v.id = t.video_id"
                        " WHERE t.status = 'proposed' AND v.current = 1")
        return int(r["n"]) if r else 0

    def review_counts(self) -> dict[str, int]:
        return {r["video_id"]: r["n"] for r in self.db.query(
            "SELECT video_id, COUNT(*) AS n FROM tags WHERE status = 'proposed' GROUP BY video_id")}

    def tag_counts(self) -> dict[str, dict[str, int]]:
        """Tagged time ranges per tag and status, in the videos the library shows.
        One range can cover several scenes: the tag list counts scenes instead
        (routes/review.py) and takes only the dropped ranges from here."""
        out: dict[str, dict[str, int]] = {}
        for r in self.db.query(
                "SELECT g.tag, g.status, COUNT(*) AS n FROM tags g JOIN videos v ON v.id = g.video_id"
                " JOIN titles t ON t.id = v.title_id WHERE v.current = 1 AND t.gone = 0"
                " GROUP BY g.tag, g.status"):
            out.setdefault(r["tag"], {"accepted": 0, "proposed": 0, "rejected": 0})[r["status"]] = r["n"]
        return out

    def steps_done(self, step: str) -> int:
        """How many of the library's videos have finished a step."""
        r = self.db.one(
            "SELECT COUNT(*) AS n FROM steps s JOIN videos v ON v.id = s.video_id"
            " JOIN titles t ON t.id = v.title_id"
            " WHERE s.step = ? AND s.state = 'done' AND v.current = 1 AND t.gone = 0", (step,))
        return int(r["n"]) if r else 0

    # -- faces -------------------------------------------------------------------------
    @staticmethod
    def _face(r: Any) -> dict[str, Any]:
        d = dict(r)
        d["box"] = json.loads(d["box"]) if d.get("box") else None
        return d

    def replace_faces(self, vid: str, faces: list[dict[str, Any]]) -> int:
        """New faces for a video; faces a person already confirmed or rejected stay."""
        stamp = now()
        with self.db.transaction():
            self.db.execute("DELETE FROM faces WHERE video_id = ? AND confirmed IS NULL", (vid,))
            for f in faces:
                self.db.execute(
                    "INSERT INTO faces (id, video_id, person_id, at, score, box, confirmed, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    ("face_" + uuid.uuid4().hex[:10], vid, f.get("person"), f["at"], f["score"],
                     dumps(f.get("box")) if f.get("box") else None, f.get("confirmed"), stamp))
        return len(faces)

    def faces(self, *, video: str | None = None, person: str | None = None,
              confirmed: bool | None = None, start: float | None = None, end: float | None = None,
              limit: int | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM faces WHERE 1=1", []
        if video:
            sql += " AND video_id = ?"
            args.append(video)
        if person:
            sql += " AND person_id = ?"
            args.append(person)
        if confirmed is True:
            sql += " AND confirmed = 1"
        elif confirmed is False:
            sql += " AND confirmed IS NULL AND person_id IS NOT NULL"
        if start is not None:
            sql += " AND at >= ?"
            args.append(start)
        if end is not None:
            sql += " AND at < ?"
            args.append(end)
        sql += " ORDER BY video_id, at"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [self._face(r) for r in self.db.query(sql, args)]

    def face(self, fid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM faces WHERE id = ?", (fid,))
        if r is None:
            raise NotFoundError(f"face {fid} not found")
        return self._face(r)

    def set_face(self, fid: str, **fields: Any) -> dict[str, Any]:
        self.face(fid)
        self.db.execute(f"UPDATE faces SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",  # noqa: S608
                        (*fields.values(), fid))
        return self.face(fid)

    # -- places ------------------------------------------------------------------------
    @staticmethod
    def _place(r: Any) -> dict[str, Any]:
        d = dict(r)
        d["implies"] = json.loads(d["implies"] or "[]")
        return d

    def places(self, franchise: str | None = None) -> list[dict[str, Any]]:
        if franchise:
            rows = self.db.query("SELECT * FROM places WHERE franchise = ? ORDER BY name", (franchise,))
        else:
            rows = self.db.query("SELECT * FROM places ORDER BY franchise, name")
        return [self._place(r) for r in rows]

    def place(self, pid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM places WHERE id = ?", (pid,))
        if r is None:
            raise NotFoundError(f"place {pid} not found")
        return self._place(r)

    def add_place(self, name: str, parent: str | None, franchise: str, implies: list[str],
                  status: str = "accepted", source: str = "person") -> dict[str, Any]:
        base = slug(name)
        if not base:
            raise MarcarrError("give the place a name")
        if parent:
            par = self.place(parent)
            franchise = franchise or par["franchise"]
            base = f"{parent}/{base}"
        pid = base
        n = 2
        while self.db.one("SELECT 1 FROM places WHERE id = ?", (pid,)):
            pid = f"{base}-{n}"
            n += 1
        self.db.execute(
            "INSERT INTO places (id, name, parent_id, franchise, implies, status, source, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (pid, name.strip()[:120], parent, franchise.strip()[:120], dumps(implies), status,
             source, now()))
        return self.place(pid)

    def update_place(self, pid: str, **fields: Any) -> dict[str, Any]:
        self.place(pid)
        if "implies" in fields:
            fields["implies"] = dumps(fields["implies"])
        if fields:
            self.db.execute(f"UPDATE places SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",  # noqa: S608
                            (*fields.values(), pid))
        return self.place(pid)

    def delete_place(self, pid: str) -> None:
        self.place(pid)
        self.db.execute("DELETE FROM places WHERE id = ? OR id LIKE ?", (pid, pid + "/%"))

    # -- custom tags ("My tags") -------------------------------------------------------
    def custom_tags(self) -> list[dict[str, Any]]:
        """Every custom tag, retired ones too, oldest first, shaped like a tag of the
        bundled list (id, name, family, hint, cues) plus ``custom``, ``title_id`` (its
        scope: None for the whole library), ``retired`` and ``created_at``.

        Kept in memory and read again only after a change made here, so name and
        family lookups (stages/vocab.py) cost no query. Treat the rows as read-only."""
        rows = self._custom
        if rows is None:
            rows = self._custom = [
                {"id": r["id"], "name": r["name"], "family": r["family"], "hint": r["hint"],
                 "cues": {"see": json.loads(r["see"] or "[]"), "hear": json.loads(r["hear"] or "[]")},
                 "custom": True, "title_id": r["title_id"], "retired": bool(r["retired"]),
                 "created_at": r["created_at"]}
                for r in self.db.query("SELECT * FROM custom_tags ORDER BY rowid")]
        return rows

    def custom_tag(self, tag: str) -> dict[str, Any]:
        row = next((t for t in self.custom_tags() if t["id"] == tag), None)
        if row is None:
            raise NotFoundError(f"custom tag {tag} not found")
        return row

    def custom_tags_for(self, title: dict[str, Any]) -> list[dict[str, Any]]:
        """The custom tags to propose on a title: library-wide ones and the ones scoped
        to it (a movie) or to its show (an episode). Retired ones are left out."""
        scope = {title["id"], title.get("parent_id")}
        return [t for t in self.custom_tags()
                if not t["retired"] and (t["title_id"] is None or t["title_id"] in scope)]

    def _custom_name(self, name: Any, but: str = "") -> str:
        name = " ".join(str(name or "").split())[:60]
        if not name:
            raise MarcarrError("give the tag a name")
        if vocab.taken(name):
            raise MarcarrError(f"the tag list already has a tag named {name}")
        if any(t["id"] != but and name.lower() in (t["name"].lower(), t["id"]) for t in self.custom_tags()):
            raise MarcarrError(f"there is already a custom tag named {name}")
        return name

    def _custom_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Checked column values for the given fields (family, hint, see, hear, title_id)."""
        out: dict[str, Any] = {}
        if "family" in fields:
            fam = str(fields["family"] or "").strip().lower()
            if fam in ("", "none"):
                out["family"] = None
            elif fam in vocab.families():
                out["family"] = fam
            else:
                raise MarcarrError(f"family must be one of {', '.join(vocab.families())}, or none")
        if "hint" in fields:
            out["hint"] = " ".join(str(fields["hint"] or "").split())[:MAX_HINT]
        for kind in ("see", "hear"):
            if kind in fields:
                out[kind] = dumps(clean_cues(fields[kind]))
        if "title_id" in fields:
            tid = str(fields["title_id"] or "").strip() or None
            if tid is not None:
                t = self.title_or_none(tid)
                if t is None:
                    raise MarcarrError(f"no title {tid} to limit the tag to")
                if t["type"] not in ("movie", "show"):
                    raise MarcarrError("a tag is for the whole library, one show or one movie (not one episode)")
            out["title_id"] = tid
        return out

    def add_custom_tag(self, name: Any, *, tag_id: Any = None, **fields: Any) -> dict[str, Any]:
        """A new custom tag. Its id is the name as a slug unless one is given; neither
        may be a bundled tag's id or name, and an id never starts with ``fc:``."""
        name = self._custom_name(name)
        tid = str(tag_id or "").strip().lower() or slug(name)
        if tid.startswith(vocab.SMART):
            raise MarcarrError(f"a tag id cannot start with {vocab.SMART} (those are Marcarr's own)")
        if not tid or tid != slug(tid):
            raise MarcarrError("a tag id is lowercase letters, digits and dashes, like running-gag")
        if vocab.taken(tid):
            raise MarcarrError(f"the tag list already has a tag with the id {tid}")
        if any(tid in (t["id"], t["name"].lower()) for t in self.custom_tags()):
            raise MarcarrError(f"there is already a custom tag with the id {tid}")
        cols = {"family": None, "hint": "", "see": "[]", "hear": "[]", "title_id": None,
                **self._custom_fields(fields)}
        self.db.execute(
            "INSERT INTO custom_tags (id, name, family, hint, see, hear, title_id, retired, created_at)"
            " VALUES (?,?,?,?,?,?,?,0,?)",
            (tid, name, cols["family"], cols["hint"], cols["see"], cols["hear"], cols["title_id"], now()))
        self._custom = None
        return self.custom_tag(tid)

    def update_custom_tag(self, tag: str, **fields: Any) -> dict[str, Any]:
        """Change name, family, hint, see, hear, title_id (scope) or retired. The id stays:
        the scenes that have the tag name it by id."""
        self.custom_tag(tag)
        cols = self._custom_fields(fields)
        if "name" in fields:
            cols["name"] = self._custom_name(fields["name"], tag)
        if "retired" in fields:
            cols["retired"] = 1 if fields["retired"] else 0
        if cols:
            self.db.execute(f"UPDATE custom_tags SET {', '.join(k + ' = ?' for k in cols)} WHERE id = ?",  # noqa: S608
                            (*cols.values(), tag))
            self._custom = None
        return self.custom_tag(tag)

    def tag_uses(self, tag: str) -> int:
        """Tagged ranges that name this tag, whatever their status or video."""
        r = self.db.one("SELECT COUNT(*) AS n FROM tags WHERE tag = ?", (tag,))
        return int(r["n"]) if r else 0

    def delete_custom_tag(self, tag: str) -> dict[str, Any] | None:
        """Remove a custom tag nothing uses; one that is on any scene is retired
        instead (returned), so those scenes keep it and its name."""
        self.custom_tag(tag)
        if self.tag_uses(tag):
            return self.update_custom_tag(tag, retired=True)
        self.db.execute("DELETE FROM custom_tags WHERE id = ?", (tag,))
        self._custom = None
        return None

    # -- collections (saved scene searches) --------------------------------------------
    @staticmethod
    def _collection(r: Any) -> dict[str, Any]:
        d = dict(r)
        d["tags"] = json.loads(d["tags"] or "[]")
        d["signals"] = json.loads(d["signals"] or "[]")
        return d

    def collections(self) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT * FROM collections ORDER BY name COLLATE NOCASE")
        return [self._collection(r) for r in rows]

    def collection(self, cid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM collections WHERE id = ?", (cid,))
        if r is None:
            raise NotFoundError(f"collection {cid} not found")
        return self._collection(r)

    def _collection_name(self, name: Any, but: str = "") -> str:
        name = " ".join(str(name or "").split())[:80]
        if not name:
            raise MarcarrError("give the collection a name")
        if self.db.one("SELECT 1 FROM collections WHERE name = ? COLLATE NOCASE AND id != ?", (name, but)):
            raise MarcarrError(f"there is already a collection named {name}")
        return name

    def add_collection(self, name: Any, tags: list[str], person: str | None, q: str,
                       signals: list[str]) -> dict[str, Any]:
        name = self._collection_name(name)
        if not (tags or person or q or signals):
            raise MarcarrError("a collection needs a tag, a person or words to search for")
        cid = "col_" + uuid.uuid4().hex[:10]
        self.db.execute(
            "INSERT INTO collections (id, name, tags, person, q, signals, created_at) VALUES (?,?,?,?,?,?,?)",
            (cid, name, dumps(tags), person or None, q, dumps(signals), now()))
        return self.collection(cid)

    def rename_collection(self, cid: str, name: Any) -> dict[str, Any]:
        self.collection(cid)
        self.db.execute("UPDATE collections SET name = ? WHERE id = ?", (self._collection_name(name, cid), cid))
        return self.collection(cid)

    def delete_collection(self, cid: str) -> None:
        self.collection(cid)
        self.db.execute("DELETE FROM collections WHERE id = ?", (cid,))

    def place_scenes(self, *, place: str | None = None, video: str | None = None,
                     with_children: bool = True) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM place_scenes WHERE status != 'rejected'", []
        if place:
            if with_children:
                sql += " AND (place_id = ? OR place_id LIKE ?)"
                args += [place, place + "/%"]
            else:
                sql += " AND place_id = ?"
                args.append(place)
        if video:
            sql += " AND video_id = ?"
            args.append(video)
        return [dict(r) for r in self.db.query(sql + " ORDER BY video_id, start", args)]

    def set_place_scene(self, vid: str, start: float, end: float, place: str | None,
                        source: str = "person") -> None:
        with self.db.transaction():
            self.db.execute("DELETE FROM place_scenes WHERE video_id = ? AND start < ? AND end > ?",
                            (vid, end - 0.5, start + 0.5))
            if place:
                self.place(place)
                self.db.execute(
                    "INSERT OR REPLACE INTO place_scenes (place_id, video_id, start, end, status,"
                    " source, created_at) VALUES (?,?,?,?,?,?,?)",
                    (place, vid, start, end, "accepted", source, now()))

    # -- AI spending -------------------------------------------------------------------
    def add_usage(self, vid: str | None, step: str, cost: float, tokens: int) -> None:
        if cost or tokens:
            self.db.execute("INSERT INTO ai_usage (at, video_id, step, cost, tokens) VALUES (?,?,?,?,?)",
                            (now(), vid, step, cost, tokens))

    def month_cost(self) -> float:
        r = self.db.one("SELECT COALESCE(SUM(cost), 0) AS c FROM ai_usage WHERE at >= ?",
                        (month_start(),))
        return float(r["c"]) if r else 0.0

    def month_seconds(self) -> float:
        r = self.db.one("SELECT COALESCE(SUM(seconds), 0) AS s FROM steps WHERE finished_at >= ?",
                        (month_start(),))
        return float(r["s"]) if r else 0.0

    # -- cuts: footage one cut has and another lacks ----------------------------------------
    @staticmethod
    def _cut(r: Any) -> dict[str, Any]:
        d = dict(r)
        d["evidence"] = json.loads(d["evidence"] or "[]")
        return d

    def add_cut_range(self, title_id: str, *, edition: str, base: str = "", kind: str = "added",
                      video_id: str | None = None, start: float | None = None,
                      end: float | None = None, extra: float | None = None,
                      status: str = "proposed", source: str = "person",
                      confidence: float | None = None, note: str = "",
                      evidence: list[str] | None = None) -> dict[str, Any]:
        if status not in STATUSES:
            raise MarcarrError(f"status must be one of {', '.join(STATUSES)}")
        if kind not in CUT_KINDS:
            raise MarcarrError(f"kind must be one of {', '.join(CUT_KINDS)}")
        edition = " ".join(str(edition or "").split())[:60]
        if not edition:
            raise MarcarrError("name the cut that has this footage (Extended, Director's Cut...)")
        if start is not None and end is not None:
            start, end = clean_range(start, end)
        cid = "cut_" + uuid.uuid4().hex[:10]
        stamp = now()
        self.db.execute(
            "INSERT INTO cut_ranges (id, title_id, edition, base, kind, video_id, start, end, extra,"
            " status, source, confidence, note, evidence, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, title_id, edition, " ".join(str(base or "").split())[:60], kind, video_id,
             start, end, None if extra is None else round(float(extra), 2), status, source[:80],
             confidence, (note or "")[:400], dumps([str(x)[:300] for x in evidence or []][:12]),
             stamp, stamp))
        return self.cut_range(cid)

    def cut_range(self, cid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM cut_ranges WHERE id = ?", (cid,))
        if r is None:
            raise NotFoundError(f"cut range {cid} not found")
        return self._cut(r)

    def cut_ranges(self, title_id: str, *, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM cut_ranges WHERE title_id = ?"
        args: list[Any] = [title_id]
        if status:
            sql += " AND status = ?"
            args.append(status)
        return [self._cut(r) for r in self.db.query(
            sql + " ORDER BY start IS NULL, start, created_at", tuple(args))]

    def update_cut_range(self, cid: str, **fields: Any) -> dict[str, Any]:
        cur = self.cut_range(cid)
        allowed = {"status", "start", "end", "note", "edition", "base", "kind", "video_id", "extra"}
        bad = set(fields) - allowed
        if bad:
            raise MarcarrError(f"cannot change {', '.join(sorted(bad))}")
        if "status" in fields and fields["status"] not in STATUSES:
            raise MarcarrError(f"status must be one of {', '.join(STATUSES)}")
        if "kind" in fields and fields["kind"] not in CUT_KINDS:
            raise MarcarrError(f"kind must be one of {', '.join(CUT_KINDS)}")
        if "start" in fields or "end" in fields:
            a = fields.get("start", cur["start"])
            b = fields.get("end", cur["end"])
            if a is not None and b is not None:
                fields["start"], fields["end"] = clean_range(a, b)
        if not fields:
            return cur
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(f"UPDATE cut_ranges SET {sets}, updated_at = ? WHERE id = ?",
                        (*fields.values(), now(), cid))
        return self.cut_range(cid)

    def delete_cut_range(self, cid: str) -> None:
        self.cut_range(cid)
        self.db.execute("DELETE FROM cut_ranges WHERE id = ?", (cid,))

    def drop_cut_proposals(self, title_id: str, source_prefix: str) -> int:
        """Remove the still-proposed ranges one source made, before it runs again."""
        where = "title_id = ? AND status = 'proposed' AND source LIKE ?"
        args = (title_id, source_prefix + "%")
        n = self.db.one(f"SELECT COUNT(*) AS n FROM cut_ranges WHERE {where}", args)
        self.db.execute(f"DELETE FROM cut_ranges WHERE {where}", args)
        return int(n["n"]) if n else 0

    def save_cut_map(self, base_id: str, other_id: str, doc: dict[str, Any]) -> None:
        self.db.execute("INSERT INTO cut_maps (base_id, other_id, doc, updated_at) VALUES (?,?,?,?)"
                        " ON CONFLICT (base_id, other_id) DO UPDATE SET doc = excluded.doc,"
                        " updated_at = excluded.updated_at", (base_id, other_id, dumps(doc), now()))

    def cut_map(self, base_id: str, other_id: str) -> dict[str, Any] | None:
        r = self.db.one("SELECT doc FROM cut_maps WHERE base_id = ? AND other_id = ?",
                        (base_id, other_id))
        return json.loads(r["doc"]) if r else None

    def add_research_run(self, title_id: str, topic: str, question: str, *, model: str,
                         answer: str, sources: list[dict[str, Any]], result: dict[str, Any],
                         cost: float) -> dict[str, Any]:
        rid = "rr_" + uuid.uuid4().hex[:10]
        self.db.execute(
            "INSERT INTO research_runs (id, title_id, topic, question, model, answer, sources,"
            " result, cost, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (rid, title_id, topic, question, model, answer, dumps(sources), dumps(result),
             float(cost or 0.0), now()))
        return self.research_run(rid)

    def research_run(self, rid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM research_runs WHERE id = ?", (rid,))
        if r is None:
            raise NotFoundError(f"research run {rid} not found")
        d = dict(r)
        d["sources"] = json.loads(d["sources"] or "[]")
        d["result"] = json.loads(d["result"] or "{}")
        return d

    def research_runs(self, title_id: str, topic: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT id FROM research_runs WHERE title_id = ?"
        args: list[Any] = [title_id]
        if topic:
            sql += " AND topic = ?"
            args.append(topic)
        return [self.research_run(r["id"]) for r in self.db.query(
            sql + " ORDER BY created_at DESC", tuple(args))]
