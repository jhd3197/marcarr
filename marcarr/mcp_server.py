"""An MCP server that lets an AI client (Claude Code, Claude Desktop, ...) ask
Marcarr what is in a film and propose tags.

It talks to the running Marcarr over its REST API (so it can only do what the
API allows, and a key limits it further). The tools are plain functions turned
into Prompture tool definitions and served with ``prompture.mcp``.

Run it with ``marcarr mcp`` (stdio). ``MARCARR_URL`` / ``--url`` points it at
another Marcarr; ``MARCARR_KEY`` sends an API key (give it read and propose).
Every tag it adds is a proposal: a person keeps or drops it on the Review page.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:7470"
MAX_TEXT = 20_000
_client: httpx.Client | None = None


def base_url() -> str:
    return os.environ.get("MARCARR_URL", DEFAULT_URL).rstrip("/")


def _http() -> httpx.Client:
    global _client
    if _client is None:
        headers = {"X-Marcarr-Client": "mcp"}
        if os.environ.get("MARCARR_KEY"):
            headers["X-Api-Key"] = os.environ["MARCARR_KEY"]
        _client = httpx.Client(base_url=base_url() + "/api/v1", timeout=120, headers=headers)
    return _client


def use_client(client: httpx.Client) -> None:
    """Send requests through *client* (tests)."""
    global _client
    _client = client


def _call(method: str, path: str, **kw: Any) -> Any:
    r = _http().request(method, path, **kw)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text[:300]
        raise RuntimeError(f"Marcarr said {r.status_code}: {detail}")
    if r.status_code == 204 or not r.content:
        return None
    return r.json() if "json" in r.headers.get("content-type", "") else r


def _image(data: bytes) -> Any:
    import importlib

    try:
        mod = importlib.import_module("mcp.server.fastmcp")
    except ImportError:
        mod = importlib.import_module("mcp.server.mcpserver")
    return mod.Image(data=data, format="jpeg")


def _clock(t: float) -> str:
    s = int(round(t))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _cut(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "\n[cut: ask for less]"


def _scene_line(s: dict[str, Any], title: str = "") -> str:
    tags = ", ".join(f"{t['name']}{'?' if t['status'] == 'proposed' else ''}" for t in s["tags"])
    head = f"{title} " if title else ""
    return (f"{head}scene {s.get('scene', s.get('n'))} {_clock(s['start'])}-{_clock(s['end'])}"
            f" [{tags or 'no tags'}] {s.get('summary') or ''}").strip()


# -- tools ---------------------------------------------------------------------------
def list_titles(q: str = "") -> str:
    """Films and shows Marcarr knows, with their video id once analysed.

    Args:
        q: part of the name (empty for all).
    """
    data = _call("GET", "/titles", params={"q": q, "per_page": 200})
    rows = [f"{t['id']} | {t['name']} ({t['year'] or '?'}) | {t['state']['text']}"
            + (f" | video {t['video_id']}" if t.get("video_id") else "") for t in data["items"]]
    return "\n".join(rows) or "nothing found"


def find_scenes(tags: str = "", person: str = "", q: str = "", include_proposed: bool = False,
                signals: str = "") -> str:
    """Find scenes across the library by tags (all must match), a person, words said, or measured signals.

    Args:
        tags: comma-separated tag names, like "Christmas,Snow".
        person: a person id, like "ron-weasley".
        q: words in the dialogue.
        include_proposed: also count tags nobody has reviewed yet.
        signals: comma-separated measured signals, like "dark,fast-cutting"; each must cover half the scene.
    """
    data = _call("GET", "/search/scenes", params={
        "tags": tags, "person": person or None, "q": q, "signals": signals,
        "status": "proposed" if include_proposed else "accepted"})
    rows = [f"video {h['video']} " + _scene_line(h, h["title_name"]) + (f' "{h["line"]}"' if h.get("line") else "")
            for h in data["items"]]
    return _cut("\n".join(rows) or "no scene matches")


def list_collections() -> str:
    """The saved searches (a name for a combination of tags, a person, words and signals) with
    how many kept scenes match each now. Run one with find_scenes."""
    rows = []
    for c in _call("GET", "/collections")["items"]:
        parts = [f"tags {','.join(c['tags'])}" if c["tags"] else "", f"person {c['person']}" if c["person"] else "",
                 f'q "{c["q"]}"' if c["q"] else "", f"signals {','.join(c['signals'])}" if c["signals"] else ""]
        rows.append(f"{c['name']}: {'; '.join(p for p in parts if p)} ({c['scenes']} scenes)")
    return _cut("\n".join(rows) or "no saved searches")


def whats_at(video: str, seconds: float) -> str:
    """What is on screen at a time: scene, people, tags, place and measured signals.

    Args:
        video: the video id.
        seconds: time in the video.
    """
    d = _call("GET", f"/videos/{video}/at/{seconds}")
    tags = ", ".join(f"{t['name']}{'?' if t['status'] == 'proposed' else ''}" for t in d["tags"])
    return (f"{_clock(d['t'])}: scene {d['scene']}; people {', '.join(d['people']) or '-'}; tags {tags or '-'};"
            f" place {d['place'] or '-'}; signals {', '.join(d['signals']) or '-'}")


def get_scene(video: str, scene: int) -> str:
    """One scene: who is seen, heard or only named, its tags (and why, with the
    moment each was seen or heard), and its dialogue. The same text as the title
    page's Copy brief, with ids added.

    Args:
        video: the video id.
        scene: the scene number.
    """
    from .brief import scene_brief

    return _cut(scene_brief(_call("GET", f"/videos/{video}/scenes/{scene}"), ids=True))


def who_is_with(title: str, person: str = "", through: int = 0) -> str:
    """Who is seen with whom in a film or episode, from the scenes they share.

    Args:
        title: the title id (from list_titles).
        person: a person id to list only their scene partners; empty for everyone.
        through: stop at this scene number so nothing later is given away; 0 for the whole story.
    """
    from urllib.parse import quote

    g = _call("GET", f"/titles/{quote(title, safe='')}/graph", params={"through": through or None})
    names = {p["id"]: p["name"] for p in g["people"]}
    if person:
        p = next((x for x in g["people"] if x["id"] == person), None)
        if p is None:
            return f"{person} is not seen in these scenes"
        out = [f"{p['name']}: seen in {len(p['scenes'])} scenes"
               + (f", first in scene {p['first']['n']} at {_clock(p['first']['start'])}" if p["first"] else "")]
        if p["gap"]:
            out.append(f"longest absence: scene {p['gap']['from']} to {p['gap']['to']} ({_clock(p['gap']['seconds'])})")
        pairs = [e for e in g["pairs"] if person in (e["a"], e["b"])]
    else:
        out = [f"{len(g['people'])} people in {g['scenes']} scenes"]
        pairs = g["pairs"][:30]
    for e in pairs:
        out.append(f"  {names.get(e['a'], e['a'])} + {names.get(e['b'], e['b'])}: "
                   f"scenes {', '.join(str(n) for n in e['scenes'][:12])}")
    return _cut("\n".join(out))


def read_dialogue(video: str, start: float = 0, end: float = 0) -> str:
    """The subtitle lines of a video between two times (seconds; end 0 = to the end).

    Args:
        video: the video id.
        start: from (seconds).
        end: to (seconds), 0 for the end.
    """
    d = _call("GET", f"/videos/{video}/lines", params={"from": start, "to": end or None})
    return _cut("\n".join(f"{_clock(x['start'])} {x['text']}" for x in d["items"]) or "no lines")


def look(video: str, seconds: float) -> list[Any]:
    """A frame of the video at a time, to see what is there.

    Args:
        video: the video id.
        seconds: time in the video.
    """
    r = _call("GET", f"/videos/{video}/frame.jpg", params={"t": seconds, "h": 480})
    return [_image(r.content)]


def list_tags(family: str = "") -> str:
    """The tag list Marcarr uses (tags are named from it), with the person's own tags first.

    Args:
        family: only one family (Place, Action, Beat, Mood, Occasion, Weather, Time of day, People, Creature, Content, Element).
    """
    d = _call("GET", "/tags", params={"family": family or None})
    rows = [f"[{f['name']}] " + ", ".join(t["name"] for t in f["tags"]) for f in d["families"]]
    mine = [t["name"] + (f" (only {t['scope']['name']})" if t.get("scope") else "")
            for t in d.get("mine") or [] if not t.get("retired")]
    if mine:
        rows.insert(0, "[My tags] " + ", ".join(mine))
    return "\n".join(rows)


def propose_tag(video: str, tag: str, start: float, end: float, seen: str = "", heard: str = "",
                people: str = "", mentioned: str = "") -> str:
    """Propose a tag over a stretch of a video; a person reviews it.

    Args:
        video: the video id.
        tag: a tag name from the tag list, like "Snow".
        start: where it starts (seconds).
        end: where it ends (seconds).
        seen: what you saw that shows it, comma-separated.
        heard: what was said that shows it, comma-separated.
        people: ids of the people you can see in it, comma-separated.
        mentioned: ids of people only named in the dialogue, not on screen, comma-separated.
    """
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    t = _call("POST", f"/videos/{video}/tags", json={
        "tag": tag, "start": start, "end": end, "status": "proposed",
        "evidence": {"seen": split(seen), "heard": split(heard)}, "people": split(people),
        "mentioned": split(mentioned)})
    return f"proposed {t['id']} {t['name']} {_clock(t['start'])}-{_clock(t['end'])}: waiting for review"


def film_cuts(title: str) -> str:
    """A film's versions (Extended, Theatrical...) and the footage one cut has that another lacks.

    Args:
        title: the title id (from list_titles), like movie:tmdb:672.
    """
    d = _call("GET", f"/titles/{title}/cuts")
    out = [f"{v['id']} {v['edition'] or 'unnamed'}{' (guessed)' if v['guessed'] else ''}"
           f" {(v['duration'] or 0) / 60:.0f} min{'' if v['in_plex'] else ' (gone)'}" for v in d["versions"]]
    for r in d["ranges"]:
        if r["status"] == "rejected":
            continue
        where = (f"{_clock(r['start'])}-{_clock(r['end'])} on {r['video_id']}" if r["start"] is not None
                 and r["end"] is not None and r["video_id"] else "time unknown")
        out.append(f"  {r['kind']} only in {r['edition']}: {where}"
                   f"{' (rough, published)' if r['rough'] else ''} [{r['status']}] {r['note']}")
    return _cut("\n".join(out) or "no versions")


def time_in_version(video: str, seconds: float, other: str) -> str:
    """Move a time from one version of a film to another (say a tag made on the Extended
    to the Theatrical), once the two were compared.

    Args:
        video: the video id the time is on.
        seconds: the time.
        other: the other version's video id.
    """
    d = _call("GET", f"/videos/{video}/to/{other}", params={"t": seconds})
    if d["at"] is None:
        return f"{_clock(seconds)} is footage the other version does not have"
    return f"{_clock(seconds)} on {video} is {_clock(d['at'])} on {other}"


TOOLS = [list_titles, find_scenes, list_collections, whats_at, get_scene, who_is_with, read_dialogue, look,
         list_tags, propose_tag, film_cuts, time_in_version]


def tool_definitions() -> list[Any]:
    from prompture.agents.tools_schema import tool_from_function

    return [tool_from_function(fn, name=fn.__name__, metadata={
        "category": "marcarr", **({"structured_output": False} if fn is look else {})}) for fn in TOOLS]


def serve(url: str | None = None) -> None:
    """Run the MCP server on stdio (blocking)."""
    if url:
        os.environ["MARCARR_URL"] = url
    from prompture.mcp.server import serve as prompture_serve

    prompture_serve(name="marcarr", tools=tool_definitions(), transport="stdio")
