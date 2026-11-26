"""A scene as plain text: what the title page's Copy brief puts on the clipboard and
what the MCP get_scene tool returns, so a person and an AI read the same thing.

It names the edition, the time range, who is seen, heard or only named, the tags
with their evidence (and the moment each was seen or heard), the dialogue, and a
link back to the same moment.
"""

from __future__ import annotations

from typing import Any

MAX_LINES = 60


def clock(t: float) -> str:
    t = max(0, int(t))
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def evidence_text(x: Any) -> str:
    """One piece of evidence: "snow" or {"text": "snow", "at": 12} -> "snow (0:12)"."""
    if isinstance(x, dict):
        at = x.get("at")
        return f"{x.get('text', '')} ({clock(at)})" if at is not None else str(x.get("text", ""))
    return str(x)


def scene_brief(d: dict[str, Any], *, link: str = "", ids: bool = False) -> str:
    """The brief of one scene from its detail (Views.scene_detail). `ids` adds the
    person and tag ids an app or AI needs to act on them."""
    names = {c["id"]: c.get("character") or c.get("actor") or c["id"] for c in d.get("cast") or []}

    def who(pids: list[str]) -> str:
        return ", ".join(f"{names.get(p, p)} ({p})" if ids else names.get(p, p) for p in pids)

    t = d["title"]
    head = t["name"] + (f" ({t['year']})" if t.get("year") else "")
    if d.get("edition"):
        head += f", {d['edition']}"
    out = [f"{head}: scene {d['n']}, {clock(d['start'])} to {clock(d['end'])}"]
    if ids:
        out.append(f"video: {d['video']}")
    if d.get("summary"):
        out.append(f"What happens: {d['summary']}")
    if d.get("place_name"):
        out.append(f"Place: {d['place_name']}")
    seen = d.get("seen", d.get("people")) or []
    out.append(f"Seen: {who(seen) or 'nobody recognised'}")
    if d.get("speakers"):
        out.append(f"Heard speaking, not seen: {who(d['speakers'])}")
    if d.get("mentioned"):
        out.append(f"Only named: {who(d['mentioned'])}")
    tags = [x for x in d.get("all_tags") or [] if x["status"] != "rejected" or ids]
    if tags:
        out.append("Tags:")
        for x in sorted(tags, key=lambda x: (x["status"] != "accepted", x["name"])):
            state = {"accepted": "kept", "proposed": "to review", "rejected": "dropped"}[x["status"]]
            line = f"  {x['name']} ({state}" + (f", {x['id']}, {x['source']}" if ids else "") + ")"
            ev = [f"{k}: " + "; ".join(evidence_text(e) for e in v) for k, v in (x.get("evidence") or {}).items() if v]
            out.append(line + (": " + " | ".join(ev) if ev else ""))
    lines = d.get("lines") or []
    if lines:
        out.append("Dialogue:")
        out += [f"  {clock(ln['start'])} {ln['text']}" for ln in lines[:MAX_LINES]]
        if len(lines) > MAX_LINES:
            out.append(f"  ... {len(lines) - MAX_LINES} more lines")
    if link:
        out.append(f"Link: {link}")
    return "\n".join(out)
