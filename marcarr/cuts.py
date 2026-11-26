"""Cuts of a film: which version is which, and what footage one has that another lacks.

Three ways to know where an Extended differs from a Theatrical:

* **A person marks it** (a range on the title page).
* **Compare two local versions.** Two encodes of a film cut the camera at the
  same moments, so the lengths of consecutive shots form the same rhythm in
  both. Lining those rhythms up gives a map from one version's time to the
  other's; where the map jumps, one version has footage the other lacks. It
  works across languages, encodes and a PAL speed-up, and needs no AI.
* **Look it up online** (:mod:`marcarr.research`): rough times from people who
  compared the cuts, for when only one version is on disk.

Everything found is a *proposed* range a person keeps or drops.
"""

from __future__ import annotations

import bisect
from typing import TYPE_CHECKING, Any

from .errors import MarcarrError

if TYPE_CHECKING:
    from .core import Core
    from .jobs import JobContext

WINDOW = 3          # consecutive shot lengths that must agree for a match
TOLERANCE = 0.12    # seconds two shot lengths may differ (detection lands a frame apart)
MIN_WINDOW = 2.5    # a window this short is too common to trust
MIN_JUMP = 1.0      # seconds: a smaller change between versions is encode noise
MIN_COVERAGE = 0.25
REACH = 120.0      # seconds past a matched cut the edge walk may look
MAX_MISSES = 2     # stray cuts skipped while walking to the exact edge of a gap  # share of the shorter version's cuts that must line up
# Film run at 25 fps for PAL TV is 4.1% faster; try both ways and plain 1:1.
SPEEDS = (1.0, 25 / 23.976, 23.976 / 25, 24 / 23.976, 23.976 / 24)
LONGER_CUTS = ("extended", "director", "unrated", "uncut", "special", "final cut", "ultimate")


# -- naming ------------------------------------------------------------------------------
def is_longer_cut(name: str) -> bool:
    n = (name or "").lower()
    return any(w in n for w in LONGER_CUTS)


def edition_labels(videos: list[dict[str, Any]],
                   runtimes: list[tuple[str, float]] | None = None) -> dict[str, dict[str, Any]]:
    """{video id: {"name", "guessed"}} for a title's versions.

    A named version keeps its name. An unnamed one is called Theatrical when a
    sibling is a longer cut (Extended, Director's Cut...) at least two minutes
    longer; else it takes the name of a published cut (*runtimes*: name, minutes)
    whose runtime is within two and a half minutes of its own; else no name.
    """
    out: dict[str, dict[str, Any]] = {}
    for v in videos:
        name = (v.get("edition") or "").strip()
        if name:
            out[v["id"]] = {"name": name, "guessed": False}
            continue
        dur = v.get("duration") or 0
        longer = [o for o in videos if o["id"] != v["id"] and is_longer_cut(o.get("edition") or "")
                  and (o.get("duration") or 0) - dur >= 120]
        if longer and dur:
            out[v["id"]] = {"name": "Theatrical", "guessed": True}
            continue
        near = sorted((abs(m * 60 - dur), n) for n, m in runtimes or [] if dur and m)
        if near and near[0][0] <= 150 and (len(near) == 1 or near[1][0] - near[0][0] > 60):
            out[v["id"]] = {"name": near[0][1], "guessed": True}
            continue
        out[v["id"]] = {"name": "", "guessed": False}
    return out


# -- lining two versions up ----------------------------------------------------------------
def cut_times(shots: list[list[float]]) -> list[float]:
    """The cut times of a shots result: every shot start after the first."""
    return [float(a) for a, _b in shots[1:]]


def _lengths(cuts: list[float]) -> list[float]:
    return [b - a for a, b in zip(cuts, cuts[1:], strict=False)]


def _candidates(ca: list[float], cb: list[float], speed: float) -> list[tuple[int, int]]:
    """(i, j): cut i of A and cut j of B start the same run of WINDOW shots."""
    la = [x * speed for x in _lengths(ca)]
    lb = _lengths(cb)
    order = sorted(range(len(lb)), key=lb.__getitem__)
    keys = [lb[j] for j in order]
    out: list[tuple[int, int]] = []
    for i in range(len(la) - WINDOW + 1):
        if sum(la[i:i + WINDOW]) < MIN_WINDOW:
            continue
        lo = bisect.bisect_left(keys, la[i] - TOLERANCE)
        hi = bisect.bisect_right(keys, la[i] + TOLERANCE)
        hits = [order[k] for k in range(lo, hi)
                if order[k] + WINDOW <= len(lb)
                and all(abs(la[i + w] - lb[order[k] + w]) <= TOLERANCE for w in range(1, WINDOW))]
        if len(hits) == 1:  # a rhythm found twice in B says nothing
            out.append((i, hits[0]))
    return out


def _chain(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The longest run of pairs that moves forward in both versions."""
    pairs = sorted(pairs)
    tails: list[int] = []      # smallest j ending a chain of each length
    tail_at: list[int] = []    # index into pairs of that end
    prev = [-1] * len(pairs)
    for k, (_i, j) in enumerate(pairs):
        pos = bisect.bisect_left(tails, j)
        if pos == len(tails):
            tails.append(j)
            tail_at.append(k)
        else:
            tails[pos] = j
            tail_at[pos] = k
        prev[k] = tail_at[pos - 1] if pos else -1
    out: list[tuple[int, int]] = []
    k = tail_at[-1] if tail_at else -1
    while k >= 0:
        out.append(pairs[k])
        k = prev[k]
    out.reverse()
    return out


def _fit_speed(pts: list[tuple[float, float]], guess: float) -> float:
    """B seconds per A second, from the stretches both versions share.

    A straight line through every point would count added footage as a slower
    speed, so this is the median slope between matched cuts at least 20 s apart
    whose slope is within 1% of *guess* (a jump between them is footage, not speed).
    """
    slopes = []
    for (a0, b0), (a1, b1) in zip(pts, pts[1:], strict=False):
        if a1 - a0 >= 20:
            r = (b1 - b0) / (a1 - a0)
            if abs(r / guess - 1) < 0.01:
                slopes.append(r)
    if len(slopes) < 5:
        return guess
    slopes.sort()
    return slopes[len(slopes) // 2]


def _drop_strays(rows: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """Remove a matched cut whose offset disagrees with both neighbours while they agree."""
    out = []
    for k, r in enumerate(rows):
        if 0 < k < len(rows) - 1:
            prev, nxt = rows[k - 1][2], rows[k + 1][2]
            if (abs(r[2] - prev) >= MIN_JUMP and abs(r[2] - nxt) >= MIN_JUMP
                    and abs(prev - nxt) < MIN_JUMP):
                continue
        out.append(r)
    return out


def align(shots_a: list[list[float]], dur_a: float, shots_b: list[list[float]],
          dur_b: float) -> dict[str, Any]:
    """Line version B up against version A.

    Returns the speed (B seconds per A second), the matched cut pairs, the
    segments both share (with the offset of each) and the gaps: where one
    version has footage the other lacks. ``coverage`` is the share of A's cuts
    that found their twin in B.
    """
    ca, cb = cut_times(shots_a), cut_times(shots_b)
    if len(ca) < WINDOW + 2 or len(cb) < WINDOW + 2:
        raise MarcarrError("too few camera cuts to compare these versions")
    best: tuple[int, float, list[tuple[int, int]]] = (0, 1.0, [])
    for speed in SPEEDS:
        chain = _chain(_candidates(ca, cb, speed))
        if len(chain) > best[0]:
            best = (len(chain), speed, chain)
    _n, speed, chain = best
    coverage = len(chain) / max(1, len(ca))
    if coverage < MIN_COVERAGE:
        return {"same_film": False, "coverage": round(coverage, 3), "speed": speed,
                "pairs": [], "segments": [], "gaps": []}
    pts = [(ca[i], cb[j]) for i, j in chain]
    speed = _fit_speed(pts, speed)
    rows = _drop_strays([(a, b, b - a * speed) for a, b in pts])
    # Once the jumps are known, the speed is refit inside each shared stretch (the
    # jumps would otherwise lean on it), and the stretches are found again.
    speed = _pooled_speed(rows, speed)
    rows = [(a, b, b - a * speed) for a, b, _o in rows]
    return _segments(rows, ca, cb, dur_a, dur_b, speed, coverage)


def _pooled_speed(rows: list[tuple[float, float, float]], guess: float) -> float:
    """The slope of B over A within stretches of one offset, pooled."""
    groups: list[list[tuple[float, float]]] = [[]]
    for k, (a, b, o) in enumerate(rows):
        if k and abs(o - rows[k - 1][2]) >= MIN_JUMP:
            groups.append([])
        groups[-1].append((a, b))
    num = den = 0.0
    for g in groups:
        if len(g) < 3:
            continue
        ma = sum(a for a, _ in g) / len(g)
        mb = sum(b for _, b in g) / len(g)
        num += sum((a - ma) * (b - mb) for a, b in g)
        den += sum((a - ma) ** 2 for a, _ in g)
    return num / den if den > 0 else guess


def _run(ks: range, lands: Any, none: int) -> int:
    """The last index of *ks* still in a run of landing cuts. A cut one encode saw
    and the other did not breaks the run for a moment; after such a miss the run
    goes on only where two cuts in a row land (one lands by chance too often)."""
    out = none
    seq = list(ks)
    misses = 0
    for n, k in enumerate(seq):
        if lands(k) and (misses == 0 or (n + 1 < len(seq) and lands(seq[n + 1]))):
            out, misses = k, 0
            continue
        misses += 1
        if misses > MAX_MISSES:
            break
    return out


def _tighten(p: tuple[float, float, float], q: tuple[float, float, float], ca: list[float],
             cb: list[float], speed: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """The exact edges of the jump between two matched cuts p and q.

    Footage before the jump lines A's cuts up with B's at p's offset, footage after
    it at q's offset. Walking single cuts forward from p (and back from q) finds
    the last cut of each run. When the runs overlap, the first shot of new
    footage happens to be as long as the next shared one, and the cut times alone
    fit both readings; the reading whose cuts land closest wins (a true match is
    off by a frame or two, a chance one by anything up to the tolerance).
    Returns both edges as (a time, b time).
    """
    def hit(k: int, off: float) -> tuple[float, float] | None:
        """(how far off, B's cut) where A's cut k lands at *off*."""
        t = ca[k] * speed + off
        j = bisect.bisect_left(cb, t - TOLERANCE)
        return (abs(cb[j] - t), cb[j]) if j < len(cb) and abs(cb[j] - t) <= TOLERANCE else None

    first = bisect.bisect_right(ca, p[0])          # A's first cut after p
    last = bisect.bisect_left(ca, q[0] - 1e-6)     # q's own cut (len(ca): the film's end)
    reach_hi = bisect.bisect_right(ca, q[0] + REACH)
    reach_lo = bisect.bisect_left(ca, max(p[0] - REACH, 0.0))
    # the run at p's offset, forward
    run_l = _run(range(first, reach_hi), lambda k: hit(k, p[2]) is not None, first - 1)
    # the run at q's offset, backward from q
    start = last if last < len(ca) and hit(last, q[2]) is not None else last - 1
    run_r = _run(range(start, reach_lo - 1, -1), lambda k: hit(k, q[2]) is not None, last)
    if run_l < run_r:
        left = (ca[run_l], hit(run_l, p[2])[1]) if run_l >= first else (p[0], p[1])  # type: ignore[index]
        right = (ca[run_r], hit(run_r, q[2])[1]) if run_r < len(ca) else (q[0], q[1])  # type: ignore[index]
        return left, right
    # Overlap: pick the junction J (a cut that lands under both offsets) whose
    # reading has the smallest total miss: cuts up to J at p's offset, from J at q's.
    best: tuple[float, int] | None = None
    for j in range(run_r, run_l + 1):
        hp, hq = hit(j, p[2]), hit(j, q[2])
        if hp is None or hq is None:
            continue
        cost = 0.0
        for k in range(run_r, run_l + 1):
            h = hit(k, p[2]) if k < j else hit(k, q[2]) if k > j else (min(hp[0], hq[0]), 0.0)
            cost += h[0] if h is not None else TOLERANCE
        if best is None or cost < best[0]:
            best = (cost, j)
    if best is None:
        return (p[0], p[1]), (q[0], q[1])
    j = best[1]
    return (ca[j], hit(j, p[2])[1]), (ca[j], hit(j, q[2])[1])  # type: ignore[index]


def _segments(rows: list[tuple[float, float, float]], ca: list[float], cb: list[float],
              dur_a: float, dur_b: float, speed: float, coverage: float) -> dict[str, Any]:
    pts_all = [(0.0, 0.0, 0.0), *rows, (dur_a, dur_b, dur_b - dur_a * speed)]
    segments: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    seg_start = pts_all[0]
    for p, q in zip(pts_all, pts_all[1:], strict=False):
        jump = q[2] - p[2]
        if abs(jump) < MIN_JUMP:
            continue
        (la, lb), (ra, rb) = _tighten(p, q, ca, cb, speed)
        segments.append({"a": [round(seg_start[0], 3), round(la, 3)],
                         "b": [round(seg_start[1], 3), round(lb, 3)],
                         "offset": round(p[2], 3)})
        if jump > 0:   # B runs longer here
            span_a = (ra - la) * speed
            gaps.append({"in": "b", "start": round(lb, 3), "end": round(rb, 3),
                         "extra": round(jump, 2), "kind": "added" if span_a < MIN_JUMP else "longer",
                         "a_at": round(la, 3)})
        else:
            span_b = rb - lb
            gaps.append({"in": "a", "start": round(la, 3), "end": round(ra, 3),
                         "extra": round(-jump, 2), "kind": "added" if span_b < MIN_JUMP else "longer",
                         "b_at": round(lb, 3)})
        seg_start = (ra, rb, q[2])
    last = pts_all[-1]
    segments.append({"a": [round(seg_start[0], 3), round(last[0], 3)],
                     "b": [round(seg_start[1], 3), round(last[1], 3)],
                     "offset": round(seg_start[2], 3)})
    return {"same_film": True, "coverage": round(coverage, 3), "speed": round(speed, 6),
            "pairs": [[round(a, 3), round(b, 3)] for a, b, _o in rows],
            "segments": segments, "gaps": gaps}


def map_time(doc: dict[str, Any], t: float) -> float | None:
    """A time of version A in version B, using an align() result; None where A's
    footage is not in B."""
    speed = float(doc.get("speed") or 1.0)
    for s in doc.get("segments") or []:
        a0, a1 = s["a"]
        if a0 - 0.5 <= t <= a1 + 0.5:
            return round(t * speed + float(s["offset"]), 3)
    return None


# -- the compare job -----------------------------------------------------------------------
class Cuts:
    def __init__(self, core: Core):
        self.core = core
        self.store = core.store

    def pair(self, title_id: str, a: str | None = None, b: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        """The two versions to compare, shorter first. With no ids: the title's two
        versions Plex lists whose lengths differ most."""
        videos = [v for v in self.store.videos_of(title_id) if v.get("in_plex", 1)]
        if a and b:
            va, vb = self.store.video(a), self.store.video(b)
            if va["title_id"] != title_id or vb["title_id"] != title_id:
                raise MarcarrError("both videos must belong to this title")
        else:
            if len(videos) < 2:
                raise MarcarrError("this title has one version: there is nothing to compare it with")
            ranked = sorted(videos, key=lambda v: v.get("duration") or 0)
            va, vb = ranked[0], ranked[-1]
        if va["id"] == vb["id"]:
            raise MarcarrError("pick two different versions")
        if (va.get("duration") or 0) > (vb.get("duration") or 0):
            va, vb = vb, va
        return va, vb

    def submit(self, title_id: str, a: str | None = None, b: str | None = None) -> dict[str, Any]:
        va, vb = self.pair(title_id, a, b)
        t = self.store.title(title_id)
        return self.core.worker.submit("compare", f"Compare the versions of {t['name']}",
                                       {"title": title_id, "a": va["id"], "b": vb["id"]})

    def job_compare(self, payload: dict[str, Any], ctx: JobContext) -> dict[str, Any]:
        title_id = payload["title"]
        va, vb = self.pair(title_id, payload.get("a"), payload.get("b"))
        for k, v in enumerate((va, vb)):
            if self.store.result(v["id"], "shots") is None:
                ctx.phase(k + 1, 3, "shots", f"finding the camera cuts of {v['edition'] or v['id']}")
                self.core.pipeline.run_step(v["id"], "shots", ctx, k, 3)
                if self.store.result(v["id"], "shots") is None:
                    raise MarcarrError(f"could not find the camera cuts of video {v['id']}")
        ctx.phase(3, 3, "compare")
        sa, sb = self.store.result(va["id"], "shots") or {}, self.store.result(vb["id"], "shots") or {}
        doc = align(sa.get("shots") or [], float(sa.get("duration") or va["duration"] or 0),
                    sb.get("shots") or [], float(sb.get("duration") or vb["duration"] or 0))
        self.store.save_cut_map(va["id"], vb["id"], doc)
        if not doc["same_film"]:
            return {"message": f"These two files don't line up ({doc['coverage']:.0%} of cuts"
                               " matched): they may not be the same film", **_brief(doc)}
        labels = edition_labels([va, vb])
        name_a = labels[va["id"]]["name"] or "the shorter version"
        name_b = labels[vb["id"]]["name"] or "the longer version"
        self.store.drop_cut_proposals(title_id, "compare")
        made = 0
        for g in doc["gaps"]:
            longer, shorter, vid = ((name_b, name_a, vb["id"]) if g["in"] == "b"
                                    else (name_a, name_b, va["id"]))
            note = (f"{g['extra']:.0f} s only in {longer}" if g["kind"] == "added"
                    else f"{longer} runs {g['extra']:.0f} s longer somewhere in here")
            self.store.add_cut_range(
                title_id, edition=longer, base=shorter, kind=g["kind"], video_id=vid,
                start=g["start"], end=g["end"], extra=g["extra"], source="compare",
                confidence=round(min(1.0, doc["coverage"] + 0.2), 2), note=note,
                evidence=[va["id"], vb["id"]])
            made += 1
        extra = sum(g["extra"] for g in doc["gaps"] if g["in"] == "b")
        speed = "" if abs(doc["speed"] - 1) < 0.005 else f", played {doc['speed']:.3f}x"
        return {"message": f"{made} differences found: {name_b} has {extra / 60:.1f} min more"
                           f" ({doc['coverage']:.0%} of cuts matched{speed})", "ranges": made,
                **_brief(doc)}


def _brief(doc: dict[str, Any]) -> dict[str, Any]:
    return {"coverage": doc["coverage"], "speed": doc["speed"], "gaps": len(doc["gaps"])}
