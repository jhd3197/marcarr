"""Who shares the screen with whom, worked out from the scenes.

Marcarr stores no relationships between characters, so the graph is what the
scenes show: two people are linked when they are seen in the same scene, and the
link is as strong as the number of scenes they share. Only sightings count; a
name said in the dialogue never draws a link. `through` stops the story at a
scene, so nothing after it shows (the spoiler line of the title page).
"""

from __future__ import annotations

from typing import Any


def build(scenes: list[dict[str, Any]], cast: dict[str, dict[str, Any]],
          through: int | None = None) -> dict[str, Any]:
    """The graph of a video's scenes: people (nodes) and the pairs seen together."""
    shown = [s for s in scenes if through is None or s["n"] <= through]
    people: dict[str, dict[str, Any]] = {}
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for s in shown:
        length = max(0.0, s["end"] - s["start"])
        seen = list(dict.fromkeys(s.get("seen", s.get("people")) or []))
        for pid in seen:
            p = people.setdefault(pid, _node(pid, cast))
            p["seconds"] += length
            p["scenes"].append(s["n"])
            p["_runs"].append((s["n"], s["start"], s["end"]))
        for pid in [*(s.get("speakers") or []), *(s.get("mentioned") or [])]:
            if pid not in seen:
                people.setdefault(pid, _node(pid, cast))["named"] += 1
        for i, a in enumerate(seen):
            for b in seen[i + 1:]:
                key = (a, b) if a < b else (b, a)
                e = pairs.setdefault(key, {"a": key[0], "b": key[1], "scenes": [], "seconds": 0.0})
                e["scenes"].append(s["n"])
                e["seconds"] += length

    nodes = []
    for p in people.values():
        runs = p.pop("_runs")
        p["seconds"] = round(p["seconds"], 1)
        if runs:
            p["first"] = {"n": runs[0][0], "start": runs[0][1]}
            p["last"] = {"n": runs[-1][0], "start": runs[-1][1]}
            p["gap"] = _longest_gap(runs)
        nodes.append(p)
    nodes.sort(key=lambda p: (-p["seconds"], p["name"]))
    seen_ids = {p["id"] for p in nodes if p["scenes"]}
    partners: dict[str, list[dict[str, Any]]] = {}
    edges = sorted(pairs.values(), key=lambda e: (-len(e["scenes"]), e["a"], e["b"]))
    for e in edges:
        e["seconds"] = round(e["seconds"], 1)
        partners.setdefault(e["a"], []).append({"id": e["b"], "scenes": len(e["scenes"])})
        partners.setdefault(e["b"], []).append({"id": e["a"], "scenes": len(e["scenes"])})
    for p in nodes:
        p["partners"] = partners.get(p["id"], [])[:5]
    return {
        "through": through if through is not None and shown and through < len(scenes) else None,
        "scenes": len(shown),
        "people": [p for p in nodes if p["id"] in seen_ids or p["named"]],
        "pairs": edges,
    }


def _node(pid: str, cast: dict[str, dict[str, Any]]) -> dict[str, Any]:
    c = cast.get(pid) or {}
    return {"id": pid, "name": c.get("character") or c.get("actor") or pid, "actor": c.get("actor") or "",
            "photo": c.get("photo"), "seconds": 0.0, "scenes": [], "named": 0,
            "first": None, "last": None, "gap": None, "_runs": []}


def _longest_gap(runs: list[tuple[int, float, float]]) -> dict[str, Any] | None:
    """The longest stretch between two scenes a person is seen in (scenes that
    touch do not count as a gap)."""
    best: dict[str, Any] | None = None
    for (n1, _a1, b1), (n2, a2, _b2) in zip(runs, runs[1:], strict=False):
        gap = a2 - b1
        if gap > 1 and (best is None or gap > best["seconds"]):
            best = {"from": n1, "to": n2, "start": b1, "end": a2, "seconds": round(gap, 1)}
    return best
