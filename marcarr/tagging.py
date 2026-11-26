"""The tags step: read the dialogue once for the whole tag list, check each
stretch on a contact sheet, then search some tags closely (FansCut's
``label.py``; see stages/label.py for the prompts).

Each tag lands as its own row (one tag over one range), proposed unless the
model is at least ``ai.auto_accept`` sure. Mood and beat tags are a matter of
opinion and always land as proposed, and so do the person's own tags ("My
tags": the ones for the whole library and the ones for this film or this
episode's show join the list). A rerun drops the AI proposals
nobody looked at; tags a person kept or dropped stay, and a dropped tag is not
proposed again over the same stretch.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from . import views
from .errors import MarcarrError
from .stages import cast as cast_mod
from .stages import index as idx
from .stages import label as label_mod
from .stages import tagger

if TYPE_CHECKING:
    from .core import Core
    from .jobs import JobContext

log = logging.getLogger(__name__)
CUSTOM = "custom"  # the group a custom tag with no family is listed under


def cast_for_prompts(core: Core, title_id: str) -> list[dict[str, Any]]:
    """The cast in the shape the ported prompts read ({name, character})."""
    return [{"name": c["actor"], "character": c["character"], "person": c["id"]}
            for c in views.Views(core).cast_people(title_id)]


def people_ids(cast: list[dict[str, Any]], said: list[str]) -> list[str]:
    out = []
    for name in said:
        hit = cast_mod.match_person(cast, name)
        if hit and hit.get("person"):
            out.append(hit["person"])
    return list(dict.fromkeys(out))


def title_keywords(core: Core, t: dict[str, Any]) -> list[str]:
    """A film's TMDB keywords ("christmas", "boarding school"): fetched once when a
    TMDB key is set, then kept (kv ``keywords:<title id>``). Films only: TMDB lists
    keywords per film or show, not per episode."""
    if t["type"] != "movie" or not t.get("tmdb_id"):
        return []
    slot = f"keywords:{t['id']}"
    kept = core.store.kv(slot)
    if kept is not None:
        return list(kept)
    key = core.cfg.catalogues.tmdb_api_key
    if not key:
        return []
    try:
        words = cast_mod.fetch_keywords(key, int(t["tmdb_id"]), core.session)
    except MarcarrError as exc:
        log.warning("TMDB keywords of %s: %s", t["id"], exc)
        return []
    core.store.set_kv(slot, words)
    return words


def custom_tags(core: Core, t: dict[str, Any]) -> list[dict[str, Any]]:
    """The person's own tags to propose on this title, shaped like the bundled ones:
    library-wide tags plus the ones scoped to this film or this episode's show. A
    tag of a family that is off in Settings is left out; one with no family is
    always in, listed to the model under "custom"."""
    off = set(core.cfg.tags.families_off)
    return [{**x, "family": x["family"] or CUSTOM} for x in core.store.custom_tags_for(t)
            if x["family"] not in off]


def run_tagging(core: Core, vid: str, progress: Any, ctx: JobContext) -> str:
    from prompture.media.understand import contact_sheet, sample_times

    store = core.store
    cfg = core.cfg
    v = store.video(vid)
    t = store.title(v["title_id"])
    doc = core.pipeline.index_doc(vid)
    if not doc["scenes"]:
        raise MarcarrError("Needs the scenes step first")
    title = f"{t['name']} ({t['year']})" if t["year"] else t["name"]
    if t["type"] == "episode" and t["parent_id"]:
        show = store.title_or_none(t["parent_id"])
        if show:
            title = f"{show['name']}, season {t['season']} episode {t['episode']}: {t['name']}"
    cast = cast_for_prompts(core, t["id"])
    families = [f for f in label_mod.vocab.families() if f not in cfg.tags.families_off]
    tags = label_mod.tag_list(families) if families else []
    tags += [x for x in custom_tags(core, t) if x["id"] not in {b["id"] for b in tags}]
    if not tags:
        raise MarcarrError("Every tag family is off in Settings")
    by_id = {x["id"]: x for x in tags}
    model = cfg.ai.vision_model or cfg.ai.model
    source = f"ai:{model}"
    dropped_before = store.drop_ai_proposals(vid)
    stats = {"candidates": 0, "proposed": 0, "kept": 0, "turned_down": 0, "looks": 0}
    hear = label_mod.cue_hits(doc, tags)
    signals = store.result(vid, "signals")

    def look_and_propose(c: dict[str, Any], allowed: list[dict[str, Any]]) -> None:
        cols, rows, tile_h = tagger.sheet_shape(c["end"] - c["start"])
        times = sample_times(c["start"], c["end"], cols * rows)
        sheet = contact_sheet(v["path"], times=times, cols=cols, rows=rows, tile_height=tile_h)
        stats["looks"] += 1
        check = label_mod.look(cfg.ai, sheet, title, c, allowed, cast, signals)
        keep = list(dict.fromkeys(check.tags))[: label_mod.MAX_KEEP]
        keep = [x for x in keep if x not in by_id or label_mod.cue_seen(by_id[x], check.seen)]
        if not check.match or not keep:
            stats["turned_down"] += 1
            return
        a, b = tagger.refine(c, check, times)
        a, b = idx.quiet_start(doc, a), idx.quiet_end(doc, b)
        if b - a < label_mod.MIN_LEN:
            stats["turned_down"] += 1
            return
        conf = round((c["confidence"] + check.confidence) / 2, 2)
        people = people_ids(cast, list(dict.fromkeys([*check.people, *c["people"]])))
        for tag in keep:
            if store.overlapping(vid, a, b, tag):
                continue
            heard = [w for when, w in hear.get(tag, []) if a <= when < b]
            # a matter of opinion, or the person's own tag: a person decides
            decides = by_id[tag]["family"] in views.SUBJECTIVE or by_id[tag].get("custom")
            sure = conf >= cfg.ai.auto_accept and not decides
            status = "accepted" if sure else "proposed"
            row = store.add_tag(vid, t["id"], tag, a, b, status=status, source=source,
                                confidence=conf, people=people,
                                evidence={"heard": list(dict.fromkeys(heard)),
                                          "seen": list(dict.fromkeys(check.seen))},
                                summary=check.summary or c.get("why") or "")
            stats["proposed" if status == "proposed" else "kept"] += 1
            if status == "proposed":
                core.events.emit("tag.proposed", {"tag": views.Views(core).tag_view(row)})

    progress(0.0, "reading the dialogue")
    cands = label_mod.read(cfg.ai, doc, title, tags, cast, ctx.cancel,
                           lambda p, msg: progress(0.3 * p, msg))
    cands += label_mod.sweep(doc, cands, signals)
    cands = label_mod.merge(cands)
    stats["candidates"] = len(cands)
    for i, c in enumerate(cands):
        ctx.check()
        progress(0.3 + 0.45 * i / max(1, len(cands)), f"looking {i + 1} of {len(cands)}")
        look_and_propose(c, tags)

    # Searching closely: tags picked in Settings, tags the film's TMDB keywords name,
    # and occasions someone names aloud.
    occasions = [x for x in tags if x["family"] == "occasion"]
    hits = label_mod.cue_hits(doc, occasions)
    named = label_mod.keyword_tags(title_keywords(core, t), tags)
    picked = list(dict.fromkeys([*[x for x in cfg.tags.search_closely if x in by_id], *named]))
    focus = list(dict.fromkeys([*picked, *hits]))
    for n, tag in enumerate(focus):
        ctx.check()
        x = by_id[tag]
        progress(0.75 + 0.15 * n / max(1, len(focus)), f"searching for {x['name']}")
        found = tagger.text_pass(cfg.ai, doc, title, tag, label_mod.focus_text(x), cast)
        found = [{**c, "tags": [tag]} for c in found]
        found += label_mod.around_hits(doc, hits.get(tag, []), tag)
        for c in label_mod.merge(found):
            ctx.check()
            if store.overlapping(vid, c["start"], c["end"], tag):
                continue
            look_and_propose(c, [x])
    if picked:
        rows = [{"start": r["start"], "end": r["end"], "tags": [r["tag"]]}
                for r in store.tags(video=vid, status=["proposed", "accepted"])]
        scenes = label_mod.scenes_to_look(doc, picked, rows)
        for i, c in enumerate(scenes):
            ctx.check()
            progress(0.9 + 0.1 * i / max(1, len(scenes)), f"looking closely {i + 1} of {len(scenes)}")
            look_and_propose(c, [by_id[x] for x in c["look_for"]])
    progress(1.0, "done")
    total = stats["proposed"] + stats["kept"]
    out = f"{total:,} tags ({stats['proposed']:,} to review)"
    if dropped_before:
        out += f", {dropped_before} old proposals replaced"
    return out
