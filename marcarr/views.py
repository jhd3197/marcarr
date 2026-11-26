"""Rows -> the shapes of the API (ui/src/api/types.ts is the contract)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from . import states as stmod
from .errors import NotFoundError
from .stages import vocab

if TYPE_CHECKING:
    from .core import Core

API = "/api/v1"
SPOILER_TAGS = {"death", "sacrifice", "betrayal", "revelation"}
FAMILY_NAMES = {"place": "Place", "action": "Action", "beat": "Beat", "mood": "Mood",
                "occasion": "Occasion", "weather": "Weather", "time": "Time of day",
                "people": "People",
                "creature": "Creature", "content": "Content", "element": "Element"}
SUBJECTIVE = {"mood", "beat"}


# Names, families and ids all come from stages/vocab.py: the bundled list first,
# then the person's own tags ("My tags").
def tag_name(tag: str) -> str:
    return vocab.name(tag)


def tag_family(tag: str) -> str | None:
    return vocab.family(tag)


def tag_id(name_or_id: str) -> str:
    """ "Christmas" or "christmas" -> "christmas" (names from the tag list map to ids)."""
    from .store import slug

    return vocab.find(name_or_id) or slug(str(name_or_id or "").strip())


def source_kind(source: str) -> str:
    return "ai" if source.startswith("ai:") else source


def title_url(tid: str) -> str:
    return quote(tid, safe=":")


class Views:
    def __init__(self, core: Core):
        self.core = core
        self.store = core.store

    # -- steps -------------------------------------------------------------------------
    def info(self, vid: str, rows: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        rows = rows if rows is not None else self.store.step_rows(vid)
        return stmod.step_info(rows, self.core.cfg, self.core.caps())

    # -- titles ------------------------------------------------------------------------
    def poster_url(self, t: dict[str, Any]) -> str | None:
        return f"{API}/titles/{title_url(t['id'])}/poster" if t.get("poster") else None

    def title_summary(self, t: dict[str, Any], *, video: dict[str, Any] | None = None,
                      rows: dict[str, Any] | None = None, review: dict[str, int] | None = None,
                      nvideos: int | None = None, episodes: dict[str, Any] | None = None,
                      top_tags: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        review = review if review is not None else self.store.review_counts()
        out: dict[str, Any] = {
            "id": t["id"], "type": t["type"], "name": t["name"], "year": t["year"],
            "duration": t["duration"], "poster": self.poster_url(t), "collection": t["collection"],
            "season": t.get("season"), "episode": t.get("episode"),
        }
        if t["type"] == "show":
            eps = episodes or self.show_counts(t["id"])
            out.update(videos=eps["videos"], analysed=eps["total"] > 0 and eps["analysed"] == eps["total"],
                       to_review=eps["review"], steps=None, state=eps["state"],
                       episodes={"total": eps["total"], "analysed": eps["analysed"],
                                 "seasons": eps["seasons"]})
            return out
        if video is None:
            video = self.store.current_video(t["id"])
        if video is None:
            out.update(videos=0, analysed=False, to_review=0, steps=None,
                       state={"kind": "notrun", "text": "No file found yet", "progress": None})
            return out
        info = self.info(video["id"], rows)
        line = stmod.state_line(info)
        if out["duration"] is None:
            out["duration"] = video.get("duration")
        out.update(videos=nvideos if nvideos is not None else len(self.store.videos_of(t["id"])),
                   analysed=line["kind"] == "done", to_review=review.get(video["id"], 0),
                   steps={s: i["state"] for s, i in info.items()}, state=line,
                   video_id=video["id"])
        if top_tags is not None:
            out["tags"] = top_tags
        return out

    def show_counts(self, show_id: str) -> dict[str, Any]:
        eps = self.store.titles("parent_id = ?", (show_id,))
        review = self.store.review_counts()
        all_rows = self.store.all_step_rows()
        total = analysed = rv = videos = 0
        seasons: set[int] = set()
        running: dict[str, Any] | None = None
        for e in eps:
            total += 1
            if e["season"] is not None:
                seasons.add(e["season"])
            v = self.store.current_video(e["id"])
            if v is None:
                continue
            videos += 1
            info = self.info(v["id"], all_rows.get(v["id"], {}))
            line = stmod.state_line(info)
            if line["kind"] == "done":
                analysed += 1
            if line["kind"] == "run" and running is None:
                running = {"kind": "run", "progress": analysed / max(1, total),
                           "text": f"Analysing season {e['season']}, episode {e['episode']}"}
            rv += review.get(v["id"], 0)
        state = running or {
            "kind": "done" if total and analysed == total else "notrun",
            "text": f"{analysed} of {total} episodes analysed", "progress": None}
        return {"total": total, "analysed": analysed, "review": rv, "videos": videos,
                "seasons": len(seasons), "state": state}

    def title_detail(self, tid: str) -> dict[str, Any]:
        t = self.store.title(tid)
        out = self.title_summary(t)
        video = self.store.current_video(tid) if t["type"] != "show" else None
        parent = None
        if t["parent_id"]:
            p = self.store.title_or_none(t["parent_id"])
            if p:
                parent = {"id": p["id"], "name": p["name"]}
        cast = self.cast_people(tid)
        out.update(
            summary=t["summary"], parent=parent, season=t["season"], episode=t["episode"],
            plex_key=t["plex_key"], tmdb_id=t["tmdb_id"], tvdb_id=t["tvdb_id"],
            plex_url=self.plex_url(t), video=self.video_view(video) if video else None,
            all_videos=[{"id": v["id"], "edition": v["edition"], "duration": v["duration"],
                         "steps_done": sum(1 for i in self.info(v["id"]).values() if i["state"] == "done"),
                         "current": bool(v["current"]), "path": v["path"]}
                        for v in self.store.videos_of(tid)],
            cast=cast,
        )
        if t["type"] == "show":
            seasons: dict[int, dict[str, int]] = {}
            all_rows = self.store.all_step_rows()
            for e in self.store.titles("parent_id = ?", (tid,)):
                s = seasons.setdefault(e["season"] or 0, {"season": e["season"] or 0, "episodes": 0, "analysed": 0})
                s["episodes"] += 1
                v = self.store.current_video(e["id"])
                if v and stmod.state_line(self.info(v["id"], all_rows.get(v["id"], {})))["kind"] == "done":
                    s["analysed"] += 1
            out["seasons"] = [seasons[k] for k in sorted(seasons)]
        return out

    def plex_url(self, t: dict[str, Any]) -> str | None:
        if not t.get("plex_key"):
            return None
        machine = self.store.kv("plex_machine")
        if not machine:
            return None
        return (f"https://app.plex.tv/desktop/#!/server/{machine}/details?key="
                f"{quote('/library/metadata/' + str(t['plex_key']), safe='')}")

    def cast_people(self, tid: str) -> list[dict[str, Any]]:
        t = self.store.title_or_none(tid)
        cast = self.store.cast(tid)
        if not cast and t and t.get("parent_id"):
            cast = self.store.cast(t["parent_id"])
        return [{"id": c["person"], "actor": c["actor"], "character": c["character"],
                 "photo": self.photo_url(c["person"]) if c.get("photo") else None}
                for c in cast]

    def photo_url(self, pid: str) -> str:
        return f"{API}/people/{quote(pid)}/photo"

    # -- videos ------------------------------------------------------------------------
    def video_view(self, v: dict[str, Any]) -> dict[str, Any]:
        rows = self.store.step_rows(v["id"])
        info = self.info(v["id"], rows)
        scenes = self.store.result(v["id"], "scenes") or {}
        shots = self.store.result(v["id"], "shots") or {}
        subs = self.store.result(v["id"], "subtitles") or {}
        t = self.store.title_or_none(v["title_id"]) or {"name": "", "id": v["title_id"]}
        return {
            "id": v["id"], "title": v["title_id"], "title_name": t["name"], "edition": v["edition"],
            "path": v["path"], "duration": v["duration"], "width": v["width"], "height": v["height"],
            "size": v["size"], "steps": {s: i["state"] for s, i in info.items()}, "step_info": info,
            "scenes": len(scenes.get("scenes") or []), "shots": len(shots.get("shots") or []),
            "lines": len(subs.get("lines") or []),
            "seconds_spent": round(sum((i["seconds"] or 0) for i in info.values()), 1),
            "ai_cost": round(sum(i["ai_cost"] or 0 for i in info.values()), 4),
            "to_review": self.store.review_counts().get(v["id"], 0),
            "state": stmod.state_line(info),
            "subtitles": ({"kind": subs.get("source", {}).get("kind", ""),
                           "detail": info["subtitles"]["detail"]} if subs else None),
        }

    # -- tags --------------------------------------------------------------------------
    def tag_ref(self, r: dict[str, Any]) -> dict[str, Any]:
        return {"id": r["id"], "tag": r["tag"], "name": tag_name(r["tag"]),
                "family": tag_family(r["tag"]), "status": r["status"]}

    def tag_view(self, r: dict[str, Any]) -> dict[str, Any]:
        return {
            **self.tag_ref(r), "video": r["video_id"], "title": r["title_id"], "start": r["start"],
            "end": r["end"], "source": source_kind(r["source"]), "source_detail": r["source"],
            "confidence": r["confidence"], "people": r["people"], "mentioned": r.get("mentioned") or [],
            "evidence": r["evidence"],
            "summary": r["summary"], "created_at": r["created_at"], "updated_at": r["updated_at"],
        }

    # -- scenes ------------------------------------------------------------------------
    def scene_rows(self, vid: str) -> list[dict[str, Any]]:
        doc = self.store.result(vid, "scenes")
        if not doc:
            return []
        return doc.get("scenes") or []

    def scenes(self, vid: str, tags: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Every scene of a video with its tags, people, place and summary."""
        rows = self.scene_rows(vid)
        if not rows:
            return []
        tags = tags if tags is not None else self.store.tags(video=vid, status=["proposed", "accepted"])
        faces = self.store.faces(video=vid)
        pres = self.store.presence(video=vid, status=["proposed", "accepted"])
        places = self.store.place_scenes(video=vid)
        place_names = {p["id"]: p for p in self.store.places()} if places else {}
        sure = self.core.cfg.faces.sure
        out = []
        for i, s in enumerate(rows):
            a, b = s["start"], s["end"]
            here = [t for t in tags if t["start"] < b - 0.5 and t["end"] > a + 0.5
                    and _overlap(t, a, b) >= 0.5 * min(b - a, t["end"] - t["start"])]
            refs: dict[str, dict[str, Any]] = {}
            for t in sorted(here, key=lambda t: t["status"] != "accepted"):
                refs.setdefault(t["tag"], self.tag_ref(t))
            # How each character is in the scene. Seen: a face match, or a tag that saw
            # them. Mentioned: only named in the dialogue. Speaker: an app heard them talk.
            seen: list[str] = []
            for f in faces:
                if a <= f["at"] < b and f["person_id"] and f["confirmed"] != 0 and (
                        f["confirmed"] == 1 or f["score"] >= sure):
                    seen.append(f["person_id"])
            for t in here:
                seen += t["people"]
            mentioned = [p for t in here for p in t.get("mentioned") or []]
            speakers: list[str] = []
            for p in pres:
                if p["start"] < b and p["end"] > a:
                    {"seen": seen, "mentioned": mentioned, "speaker": speakers}[p["how"]].append(p["person_id"])
            seen = list(dict.fromkeys(seen))
            speakers = [p for p in dict.fromkeys(speakers) if p not in seen]
            mentioned = [p for p in dict.fromkeys(mentioned) if p not in seen and p not in speakers]
            summary = ""
            best = 0.0
            for t in here:
                ov = _overlap(t, a, b)
                if t["summary"] and ov > best:
                    summary, best = t["summary"], ov
            place = next((p for p in places if p["start"] < b and p["end"] > a), None)
            pid = place["place_id"] if place else None
            out.append({
                "n": i + 1, "start": a, "end": b, "shots": s.get("shots", 0),
                "people": seen, "seen": seen, "speakers": speakers, "mentioned": mentioned,
                "tags": list(refs.values()),
                "place": pid, "place_name": self.place_path_name(pid, place_names) if pid else None,
                "summary": summary, "still": f"{API}/videos/{vid}/scenes/{i + 1}/still.jpg",
                "spoiler": any(r["tag"] in SPOILER_TAGS for r in refs.values()),
                "uncertain": bool(s.get("uncertain")),
                "to_review": sum(1 for r in refs.values() if r["status"] == "proposed"),
            })
        return out

    def place_path_name(self, pid: str, names: dict[str, dict[str, Any]]) -> str:
        parts = []
        cur: str | None = pid
        while cur:
            p = names.get(cur)
            if not p:
                break
            parts.append(p["name"])
            cur = p["parent_id"]
        return " › ".join(reversed(parts))

    def scene_at(self, vid: str, t: float) -> int | None:
        for i, s in enumerate(self.scene_rows(vid)):
            if s["start"] <= t < s["end"]:
                return i + 1
        return None

    def scene_detail(self, vid: str, n: int) -> dict[str, Any]:
        v = self.store.video(vid)
        scenes = self.scenes(vid)
        if not 1 <= n <= len(scenes):
            raise NotFoundError(f"scene {n} not found")
        s = scenes[n - 1]
        a, b = s["start"], s["end"]
        t = self.store.title(v["title_id"])
        all_tags = [self.tag_view(x) for x in self.store.tags(video=vid, start=a, end=b)
                    if _overlap(x, a, b) >= 0.5 * min(b - a, x["end"] - x["start"])]
        subs = self.store.result(vid, "subtitles") or {}
        lines = [ln for ln in subs.get("lines") or [] if ln["end"] > a and ln["start"] < b]
        shots = self.store.result(vid, "shots") or {}
        cuts = sorted({e for sh in shots.get("shots") or [] for e in sh if a - 30 <= e <= b + 30})
        k = 6 if b - a > 30 else 4
        frames = [{"t": round(a + (b - a) * (i + 0.5) / k, 2)} for i in range(k)]
        for f in frames:
            f["url"] = f"{API}/videos/{vid}/frame.jpg?t={f['t']:.2f}&h=240"
        faces = [self.face_view(f) for f in self.store.faces(video=vid, start=a, end=b)]
        presence = [self.presence_view(p) for p in self.store.presence(video=vid, start=a, end=b)]
        return {
            **s, "video": vid, "title": {"id": t["id"], "name": t["name"], "year": t["year"]},
            "duration": v["duration"], "all_tags": all_tags, "lines": lines, "shot_cuts": cuts,
            "frames": frames, "faces": faces, "presence": presence, "cast": self.cast_people(t["id"]),
            "prev": n - 1 if n > 1 else None, "next": n + 1 if n < len(scenes) else None,
        }

    # -- faces and people --------------------------------------------------------------
    def face_view(self, f: dict[str, Any]) -> dict[str, Any]:
        conf = f["confirmed"]
        return {"id": f["id"], "video": f["video_id"], "person": f["person_id"], "at": f["at"],
                "score": round(f["score"], 2), "box": f["box"],
                "confirmed": None if conf is None else bool(conf),
                "still": f"{API}/faces/{f['id']}/crop.jpg"}

    @staticmethod
    def presence_view(p: dict[str, Any]) -> dict[str, Any]:
        return {"id": p["id"], "video": p["video_id"], "person": p["person_id"], "how": p["how"],
                "start": p["start"], "end": p["end"], "at": p["at"], "source": source_kind(p["source"]),
                "source_detail": p["source"], "status": p["status"], "note": p["note"]}

    def person_view(self, p: dict[str, Any], titles: int | None = None) -> dict[str, Any]:
        out = {"id": p["id"], "actor": p["actor"], "character": p["character"],
               "photo": self.photo_url(p["id"]) if p.get("photo") else None}
        if titles is not None:
            out["titles"] = titles
        return out

    # -- search hits -------------------------------------------------------------------
    def hit(self, t: dict[str, Any], vid: str, s: dict[str, Any], line: str | None = None) -> dict[str, Any]:
        return {"title": t["id"], "title_name": t["name"], "year": t["year"], "video": vid,
                "scene": s["n"], "start": s["start"], "end": s["end"], "tags": s["tags"],
                "summary": s["summary"], "still": s["still"], "spoiler": s["spoiler"], "line": line}


def _overlap(t: dict[str, Any], a: float, b: float) -> float:
    return max(0.0, min(t["end"], b) - max(t["start"], a))
