"""The steps on a real (generated) video, states and staleness."""

from __future__ import annotations

from types import SimpleNamespace

from marcarr import states as stmod
from marcarr.pipeline import apply_edits, merge_flashes


def test_merge_flashes() -> None:
    assert merge_flashes([(0, 5), (5, 5.2), (5.2, 9)]) == [(0, 5.2), (5.2, 9)]
    assert merge_flashes([(0, 0.1), (0.1, 4)]) == [(0, 4)]


def test_apply_edits_cut_and_join() -> None:
    scenes = [{"start": 0, "end": 10, "shots": 2}, {"start": 10, "end": 20, "shots": 1}]
    out = apply_edits(scenes, [{"kind": "join", "at": 10}, {"kind": "cut", "at": 15}])
    assert [(s["start"], s["end"]) for s in out] == [(0, 15), (15, 20)]
    assert out[0]["manual"]


def test_steps_on_a_real_video(core, analysed) -> None:
    info = stmod.step_info(core.store.step_rows(analysed), core.cfg, core.caps())
    assert info["shots"]["state"] == "done"
    assert info["subtitles"]["state"] == "done"
    assert info["scenes"]["state"] == "done"
    assert info["signals"]["state"] == "done"
    assert info["tags"]["state"] == "off"  # no AI configured
    shots = core.store.result(analysed, "shots")["shots"]
    assert len(shots) == 3  # three sources, two cuts
    lines = core.store.result(analysed, "subtitles")["lines"]
    assert [ln["text"] for ln in lines][0].startswith("Merry Christmas")


def test_rerunning_an_input_makes_dependents_stale(core, analysed) -> None:
    core.pipeline.submit(analysed, ["subtitles"])
    # scenes and signals read subtitles: they were queued along with it
    rows = core.store.step_rows(analysed)
    assert rows["scenes"]["state"] == "queued"
    core.worker.run_pending("heavy")
    info = stmod.step_info(core.store.step_rows(analysed), core.cfg, core.caps())
    assert info["scenes"]["state"] == "done"
    # rerun only subtitles by hand: scenes becomes stale
    core.store.set_step(analysed, "subtitles", finished_at="2099-01-01T00:00:00")
    info = stmod.step_info(core.store.step_rows(analysed), core.cfg, core.caps())
    assert info["scenes"]["state"] == "rerun"


def test_same_file_is_the_same_video(core, analysed, film) -> None:
    again = core.library.add_file("movie:tmdb:1", str(film))
    assert again == analysed


def test_tagging_with_a_fake_model(core, analysed, monkeypatch) -> None:
    """The tags step end to end with the model calls replaced."""
    from marcarr import config as cfgmod
    from marcarr.stages import label

    core.save_config(cfgmod.merge_update(core.cfg, {"ai": {"enabled": True, "model": "fake/model"}}))
    scenes = core.store.result(analysed, "scenes")["scenes"]
    first = scenes[0]

    def read(cfg, doc, title, tags, cast, cancel=None, progress=None):
        return [{"start": first["start"], "end": first["end"], "tags": ["christmas"], "people": ["Mira"],
                 "why": "they say Merry Christmas", "confidence": 0.6}]

    def look(cfg, sheet, title, cand, tags, cast):
        return SimpleNamespace(match=True, tags=["christmas", "snow"], seen=["Christmas tree", "snow"],
                               people=["Mira"], summary="Presents by the tree", confidence=0.8,
                               first_tile=1, last_tile=6)

    monkeypatch.setattr(label, "read", read)
    monkeypatch.setattr(label, "look", look)
    monkeypatch.setattr("marcarr.stages.tagger.text_pass", lambda *a, **k: [])
    core.pipeline.submit(analysed, ["tags"])
    core.worker.run_pending("heavy")
    rows = core.store.step_rows(analysed)
    assert rows["tags"]["state"] == "done", rows["tags"]["detail"]
    tags = core.store.tags(video=analysed)
    names = {t["tag"] for t in tags}
    assert "christmas" in names
    xmas = next(t for t in tags if t["tag"] == "christmas")
    assert xmas["status"] == "proposed"
    assert xmas["people"] == ["mira-vale"]
    assert "Merry Christmas" in xmas["evidence"]["heard"][0]
    # a dropped tag is not proposed again on a rerun
    core.store.update_tag(xmas["id"], status="rejected")
    core.pipeline.submit(analysed, ["tags"])
    core.worker.run_pending("heavy")
    again = [t for t in core.store.tags(video=analysed) if t["tag"] == "christmas"]
    assert [t["status"] for t in again] == ["rejected"]


def test_one_job_per_video_at_a_time(core, analysed) -> None:
    first = core.pipeline.submit(analysed, ["signals"])
    core.jobs.update(first["job"], status="running")
    core.pipeline.submit(analysed, ["cast"])
    assert core.jobs.next_queued("heavy") is None  # waits for the running one
    core.jobs.update(first["job"], status="done")
    assert core.jobs.next_queued("heavy") is not None
