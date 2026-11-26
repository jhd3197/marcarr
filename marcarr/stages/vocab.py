"""The shared tag list (``tags_v1.json``, see docs/markers.md).

Content tags have plain ids (``christmas``); FansCut's own cut tags carry
``fc:`` (``fc:filler``). The app shows names only, never the prefix.
``signals`` are what FansCut measures (faces, shots, brightness, sound): they
are not tags and are never shown as tags.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import cache
from importlib import resources
from typing import Any

SMART = "fc:"


@cache
def load() -> dict[str, Any]:
    raw = resources.files("marcarr.stages").joinpath("tags_v1.json").read_text(encoding="utf-8")
    return json.loads(raw)


def families() -> list[str]:
    return list(load()["families"])


def content_tags(families_off: list[str] | tuple[str, ...] = ()) -> list[dict[str, Any]]:
    off = set(families_off)
    return [t for t in load()["tags"] if t["family"] not in off and not t.get("retired")]


def cut_tags(detect: str | None = None) -> list[dict[str, Any]]:
    return [t for t in load()["cut_tags"] if detect is None or t["detect"] == detect]


@cache
def _by_id() -> dict[str, dict[str, Any]]:
    data = load()
    return {t["id"]: t for t in [*data["tags"], *data["cut_tags"]]}


# -- custom tags ("My tags") -----------------------------------------------------------
# The bundled list above is a file, read once. A person's own tags live in the
# database; the running Core registers where to read them (Store.custom_tags, which
# keeps them in memory and re-reads after a change), so every lookup below sees
# both without a query per call. A bundled tag wins over a custom one.
_custom_source: Callable[[], list[dict[str, Any]]] | None = None


def use_custom(source: Callable[[], list[dict[str, Any]]] | None) -> None:
    global _custom_source
    _custom_source = source


def custom_tags() -> list[dict[str, Any]]:
    """Every custom tag, retired ones too, in the bundled tags' shape plus
    ``custom``, ``title_id`` (its scope), ``retired`` and ``created_at``."""
    return _custom_source() if _custom_source is not None else []


def custom(tag: str) -> dict[str, Any] | None:
    return next((t for t in custom_tags() if t["id"] == tag), None)


def get(tag: str) -> dict[str, Any] | None:
    """A tag of the bundled list, else a custom one."""
    return _by_id().get(tag) or custom(tag)


def family(tag: str) -> str | None:
    """A content tag's family (None for cut tags, custom tags without one, unknown ids)."""
    t = get(tag)
    return t.get("family") if t else None


def find(name_or_id: str) -> str | None:
    """The id a name or id means ("Christmas" -> "christmas"), bundled content tags
    first, then custom ones; None when no tag is called that."""
    low = str(name_or_id or "").strip().lower()
    if not low:
        return None
    for tags in (load()["tags"], custom_tags()):
        for t in tags:
            if t["id"] == low:
                return str(t["id"])
        for t in tags:
            if t["name"].lower() == low:
                return str(t["id"])
    return None


def taken(name_or_id: str) -> bool:
    """Whether a bundled tag (content or cut) already has this id or name."""
    low = str(name_or_id or "").strip().lower()
    data = load()
    return any(low in (t["id"].lower(), t["name"].lower()) for t in [*data["tags"], *data["cut_tags"]])


def is_smart(tag: str) -> bool:
    return tag.startswith(SMART)


def name(tag: str) -> str:
    """Display name: the list's name, else the id without ``fc:`` and dashes."""
    t = get(tag)
    if t:
        return str(t["name"])
    plain = tag.removeprefix(SMART).replace("-", " ")
    return plain[:1].upper() + plain[1:]


def public() -> dict[str, Any]:
    """What ``GET /api/scenes/vocab`` returns."""
    data = load()
    return {
        "version": data["version"],
        "families": data["families"],
        "tags": data["tags"],
        "cut_tags": data["cut_tags"],
        "signals": data.get("signals", []),
    }
