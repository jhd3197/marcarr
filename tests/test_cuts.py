"""Versions and cuts: every Plex version is a video, and what an Extended adds."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Any

import pytest

from marcarr import ai, identity
from marcarr import research as research_mod
from marcarr.cuts import align, edition_labels, map_time


# -- naming ------------------------------------------------------------------------------
@pytest.mark.parametrize(("name", "want"), [
    ("Harry Potter and the Chamber of Secrets 2002 PROPER EXTENDED 1080p BluRay x265.mkv", "Extended"),
    ("The Two Towers (2002) - Extended Latino.mkv", "Extended"),
    ("Alien (1979) {edition-Director's Cut}.mkv", "Director's Cut"),
    ("Kingdom.of.Heaven.2005.Directors.Cut.mkv", "Director's Cut"),
    ("Spotlight (2015).mkv", ""),
])
def test_edition_from_the_file_name(name: str, want: str) -> None:
    assert identity.edition_of(name) == want


def test_plex_edition_wins() -> None:
    assert identity.edition_of("Movie Extended.mkv", "Ultimate Cut") == "Ultimate Cut"


def test_an_unnamed_shorter_version_is_guessed_theatrical() -> None:
    vids = [{"id": "a", "edition": "Extended", "duration": 174 * 60},
            {"id": "b", "edition": "", "duration": 161 * 60}]
    labels = edition_labels(vids)
    assert labels["a"] == {"name": "Extended", "guessed": False}
    assert labels["b"] == {"name": "Theatrical", "guessed": True}


def test_published_runtimes_name_a_version() -> None:
    vids = [{"id": "a", "edition": "", "duration": 228.5 * 60}]
    labels = edition_labels(vids, [("Theatrical", 178), ("Extended Edition", 228)])
    assert labels["a"] == {"name": "Extended Edition", "guessed": True}
    assert edition_labels(vids, [("Theatrical", 200)])["a"]["name"] == ""


# -- lining two versions up ----------------------------------------------------------------
def _film(lengths: list[float], speed: float, rng: random.Random, false: int) -> tuple[list[list[float]], float]:
    t, cuts = 0.0, []
    for x in lengths:
        cuts.append(t)
        t += x * speed
    cuts = [c + rng.uniform(-0.04, 0.04) if c else c for c in cuts]
    for _ in range(false):  # cuts one encode's detector saw and the other did not
        k = rng.randrange(1, len(cuts) - 1)
        cuts.insert(k, (cuts[k - 1] + cuts[k]) / 2)
    cuts.sort()
    return [[a, b] for a, b in zip(cuts, [*cuts[1:], t], strict=False)], t


@pytest.mark.parametrize(("seed", "speed"), [(1, 1.0), (2, 1.0), (5, 23.976 / 25), (6, 25 / 23.976)])
def test_align_finds_an_added_scene_exactly(seed: int, speed: float) -> None:
    rng = random.Random(seed)
    base = [rng.uniform(0.8, 9) for _ in range(1200)]
    scene = [rng.uniform(0.8, 6) for _ in range(30)]
    longer = base[:300] + scene + base[300:]
    sa, da = _film(base, 1.0, rng, false=10)
    sb, db = _film(longer, speed, rng, false=10)
    doc = align(sa, da, sb, db)
    assert doc["same_film"]
    assert doc["speed"] == pytest.approx(speed, rel=1e-4)
    big = [g for g in doc["gaps"] if g["extra"] > 30]
    assert len(big) == 1
    start, end = sum(base[:300]) * speed, (sum(base[:300]) + sum(scene)) * speed
    assert big[0]["in"] == "b"
    assert big[0]["start"] == pytest.approx(start, abs=0.2)
    assert big[0]["end"] == pytest.approx(end, abs=0.2)
    assert big[0]["extra"] == pytest.approx(sum(scene) * speed, abs=0.3)
    # a moment after the scene, moved from the shorter version to the longer one
    assert map_time(doc, 3000) == pytest.approx((3000 + sum(scene)) * speed, abs=0.15)


def test_align_edges_across_many_films() -> None:
    """An added scene and a removed stretch in each of 30 films, with noisy cuts and
    a PAL speed-up half the time. Most edges are exact; when the shot next to an
    edge runs as long in both readings, cut times alone cannot tell, and the edge
    lands one shot off (never more)."""
    exact = total = 0
    for seed in range(30):
        rng = random.Random(seed)
        base = [rng.uniform(0.8, 9) for _ in range(1500)]
        scene = [rng.uniform(0.8, 6) for _ in range(30)]
        other = base[:300] + scene + base[300:1200] + base[1210:]
        speed = rng.choice((1.0, 23.976 / 25))
        sa, da = _film(base, 1.0, rng, 15)
        sb, db = _film(other, speed, rng, 15)
        doc = align(sa, da, sb, db)
        added = [g for g in doc["gaps"] if g["in"] == "b"]
        removed = [g for g in doc["gaps"] if g["in"] == "a"]
        assert len(added) == 1 and len(removed) == 1
        want = [(added[0]["start"], sum(base[:300]) * speed),
                (added[0]["end"], (sum(base[:300]) + sum(scene)) * speed),
                (removed[0]["start"], sum(base[:1200])), (removed[0]["end"], sum(base[:1210]))]
        for got, true in want:
            total += 1
            exact += abs(got - true) < 0.2
            assert abs(got - true) < 9.5  # at most one shot
        assert map_time(doc, 2000) == pytest.approx((2000 + sum(scene)) * speed, abs=0.2)
    assert exact / total >= 0.9


def test_align_says_when_files_are_different_films() -> None:
    rng = random.Random(3)
    a, da = _film([rng.uniform(0.8, 9) for _ in range(400)], 1.0, rng, 0)
    b, db = _film([rng.uniform(0.8, 9) for _ in range(400)], 1.0, rng, 0)
    assert not align(a, da, b, db)["same_film"]


# -- scanning versions -----------------------------------------------------------------------
def _versions_item(paths: list[Path]) -> dict[str, Any]:
    return {"type": "movie", "title": "Chamber", "ratingKey": "9", "editionTitle": "",
            "Media": [{"Part": [{"file": str(p)}]} for p in paths]}


def test_every_plex_version_is_a_video(core, tmp_path: Path, monkeypatch) -> None:
    ext = tmp_path / "Chamber 2002 EXTENDED.mkv"
    th = tmp_path / "Chamber 2002 - Latino.mkv"
    for p, n in ((ext, 1), (th, 2)):
        p.write_bytes(b"x" * n)
    durations = {ext.name: 174 * 60.0, th.name: 161 * 60.0}

    def fake_identity(p: Any, _probe: str = "") -> dict[str, Any]:
        p = Path(p)
        return {"content_key": "c" + hashlib.sha256(p.name.encode()).hexdigest()[:24], "size": p.stat().st_size,
                "mtime": p.stat().st_mtime, "method": "test", "duration": durations[p.name],
                "streams": [{"type": "audio", "language": "spa" if "Latino" in p.name else "eng"}]}

    monkeypatch.setattr(identity, "content_identity", fake_identity)
    core.store.upsert_title({"id": "movie:tmdb:672", "type": "movie", "name": "Chamber",
                             "sort_name": "chamber", "tmdb_id": 672})
    stats = {"videos": 0, "unreadable": 0}
    new: list[str] = []
    core.library._file("movie:tmdb:672", _versions_item([ext, th]), stats, new)
    vids = core.store.videos_of("movie:tmdb:672")
    assert len(vids) == 2 and stats["videos"] == 2
    assert len(new) == 1  # only the main version is queued for analysis
    main = core.store.current_video("movie:tmdb:672")
    assert main is not None and main["edition"] == "Extended"
    # a second scan keeps the main version current and the other listed
    core.library._file("movie:tmdb:672", _versions_item([ext, th]), stats, [])
    assert core.store.current_video("movie:tmdb:672")["id"] == main["id"]
    assert all(v["in_plex"] for v in core.store.videos_of("movie:tmdb:672"))
    # the other version leaves Plex
    core.library._file("movie:tmdb:672", _versions_item([ext]), stats, [])
    gone = [v for v in core.store.videos_of("movie:tmdb:672") if not v["in_plex"]]
    assert len(gone) == 1 and gone[0]["path"].endswith("Latino.mkv")


# -- the API, compare and research jobs --------------------------------------------------------
def _two_versions(core) -> tuple[str, str, list[float]]:
    rng = random.Random(11)
    base = [rng.uniform(0.8, 9) for _ in range(900)]
    scene = [rng.uniform(0.8, 6) for _ in range(50)]
    sa, da = _film(base, 1.0, rng, 5)
    sb, db = _film(base[:200] + scene + base[200:], 1.0, rng, 5)
    core.store.upsert_title({"id": "movie:tmdb:5", "type": "movie", "name": "Two Cuts",
                             "sort_name": "two cuts", "year": 2002, "tmdb_id": 5})
    a = core.store.upsert_video("movie:tmdb:5", "/m/a.mkv", {"content_key": "caaaa", "duration": da}, "")
    b = core.store.upsert_video("movie:tmdb:5", "/m/b.mkv", {"content_key": "cbbbb", "duration": db},
                                "Extended", main=False)
    core.store.save_result(a, "shots", {"version": 1, "duration": da, "shots": sa})
    core.store.save_result(b, "shots", {"version": 1, "duration": db, "shots": sb})
    return a, b, [sum(base[:200]), sum(base[:200]) + sum(scene)]


def test_compare_job_proposes_the_added_scene(core, client) -> None:
    a, b, (start, end) = _two_versions(core)
    page = client.get("/api/v1/titles/movie:tmdb:5/cuts").json()
    assert [v["edition"] for v in page["versions"]] == ["Theatrical", "Extended"]
    assert page["versions"][0]["guessed"] is True
    assert page["can"]["compare"] is None
    job = client.post("/api/v1/titles/movie:tmdb:5/cuts/compare", json={}).json()
    assert job["kind"] == "compare"
    core.worker.run_pending()
    page = client.get("/api/v1/titles/movie:tmdb:5/cuts").json()
    added = [r for r in page["ranges"] if r["extra"] and r["extra"] > 30]
    assert len(added) == 1
    r = added[0]
    assert (r["edition"], r["base"], r["kind"], r["video_id"]) == ("Extended", "Theatrical", "added", b)
    assert r["status"] == "proposed" and r["source"] == "compare"
    assert r["start"] == pytest.approx(start, abs=0.2) and r["end"] == pytest.approx(end, abs=0.2)
    assert page["compare"]["same_film"] is True
    # a time moves between the two versions, both ways
    later = client.get(f"/api/v1/videos/{a}/to/{b}", params={"t": start + 600}).json()["at"]
    assert later == pytest.approx(start + 600 + (end - start), abs=0.2)
    back = client.get(f"/api/v1/videos/{b}/to/{a}", params={"t": later}).json()["at"]
    assert back == pytest.approx(start + 600, abs=0.2)
    assert client.get(f"/api/v1/videos/{b}/to/{a}", params={"t": start + 5}).json()["at"] is None
    # keep them all, then a new compare only replaces what is still proposed
    assert client.post("/api/v1/titles/movie:tmdb:5/cuts/keep", json={"source": "compare"}).json()["kept"] >= 1
    core.cuts.submit("movie:tmdb:5")
    core.worker.run_pending()
    assert len([x for x in core.store.cut_ranges("movie:tmdb:5") if x["status"] == "accepted"]) >= 1


def test_a_person_marks_a_range_and_an_app_proposes_one(core, client) -> None:
    _a, b, _ = _two_versions(core)
    mine = client.post("/api/v1/titles/movie:tmdb:5/cuts", json={
        "edition": "Extended", "base": "Theatrical", "video": b, "start": 60, "end": 125,
        "note": "Dobby at the window runs longer"}).json()
    assert mine["status"] == "accepted" and mine["source"] == "person"
    app = client.post("/api/v1/titles/movie:tmdb:5/cuts", headers={"X-Marcarr-Client": "fanscut"},
                      json={"edition": "Extended", "start": 300, "end": 330, "status": "accepted"}).json()
    assert app["status"] == "proposed" and app["source"] == "fanscut"
    changed = client.patch(f"/api/v1/cuts/{app['id']}", json={"status": "rejected"}).json()
    assert changed["status"] == "rejected"
    assert client.post("/api/v1/titles/movie:tmdb:5/cuts", json={"edition": "", "start": 1, "end": 2}).status_code == 400
    assert client.delete(f"/api/v1/cuts/{mine['id']}").json() == {"deleted": mine["id"]}


def test_research_is_off_until_switched_on(core, client) -> None:
    _two_versions(core)
    page = client.get("/api/v1/titles/movie:tmdb:5/cuts").json()
    assert "off" in page["can"]["research"]
    assert client.post("/api/v1/titles/movie:tmdb:5/cuts/research").status_code == 400


class _Report:
    def to_dict(self) -> dict[str, Any]:
        return {"answer": "The Extended Edition runs 174 minutes [1]; the theatrical cut 161 [1]. "
                          "At 1:02:10 a 65-second scene of Dobby at the window is added [1].",
                "sources": [{"n": 1, "url": "https://example.org/compare", "title": "Comparison",
                             "opened": True, "cited": True}],
                "cost": 0.02, "model": "fake/model", "synthesis": "llm", "usage": {"total_tokens": 900}}


def test_research_lands_rough_ranges_for_review(core, client, monkeypatch) -> None:
    _a, b, _ = _two_versions(core)
    core.cfg.research.enabled = True
    core.cfg.ai.enabled = True
    core.cfg.ai.model = "fake/model"
    asked: list[str] = []

    def fake_ask(self, question: str, ctx: Any) -> _Report:
        asked.append(question)
        return _Report()

    def fake_json(cfg: Any, schema: Any, system: str, prompt: str, **kw: Any) -> Any:
        assert "https://example.org/compare" in prompt
        return schema.model_validate({
            "editions": [{"name": "Theatrical", "runtime_minutes": 161, "cited": [1]},
                         {"name": "Extended Edition", "runtime_minutes": 174, "cited": [1]}],
            "differences": [
                {"edition": "Extended Edition", "base": "Theatrical", "kind": "added", "at": "1:02:10",
                 "length_seconds": 65, "description": "Dobby at the window", "cited": [1]},
                {"edition": "Extended Edition", "kind": "longer", "description": "The feast runs longer",
                 "cited": [1]}]})

    monkeypatch.setattr(research_mod.Research, "_ask", fake_ask)
    monkeypatch.setattr(ai, "ask_json", fake_json)
    job = client.post("/api/v1/titles/movie:tmdb:5/cuts/research").json()
    assert job["kind"] == "research"
    core.worker.run_pending()
    assert asked and '"Two Cuts" (2002)' in asked[0] and "Extended" in asked[0]
    page = client.get("/api/v1/titles/movie:tmdb:5/cuts").json()
    rows = [r for r in page["ranges"] if r["source_kind"] == "research"]
    assert len(rows) == 2
    timed = next(r for r in rows if r["start"] is not None)
    assert timed["rough"] and timed["status"] == "proposed" and timed["video_id"] == b
    assert (timed["start"], timed["end"]) == (3730.0, 3795.0)
    assert timed["evidence"] == ["https://example.org/compare"]
    untimed = next(r for r in rows if r["start"] is None)
    assert untimed["note"] == "The feast runs longer"
    assert page["research"][0]["editions"][1]["runtime_minutes"] == 174
    run = client.get(f"/api/v1/research/{page['research'][0]['id']}").json()
    assert "Dobby" in run["answer"]


def test_mcp_tools_read_cuts_and_move_times(core, client) -> None:
    from marcarr import mcp_server

    a, b, (start, end) = _two_versions(core)
    core.cuts.submit("movie:tmdb:5")
    core.worker.run_pending()
    client.base_url = client.base_url.join("/api/v1/")
    mcp_server.use_client(client)
    text = mcp_server.film_cuts("movie:tmdb:5")
    assert "Extended" in text and "Theatrical (guessed)" in text and "added only in Extended" in text
    assert "is footage the other version does not have" in mcp_server.time_in_version(b, start + 5, a)
    assert mcp_server.time_in_version(a, start + 600, b).endswith(f"on {b}")
    mcp_server.use_client(None)  # type: ignore[arg-type]
