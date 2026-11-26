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

    def look(cfg, sheet, title, cand, tags, cast, signals=None):
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


# -- the tag list ----------------------------------------------------------------------
def test_families_of_the_tag_list() -> None:
    from marcarr import config as cfgmod
    from marcarr import views
    from marcarr.stages import vocab

    data = vocab.load()
    fams = vocab.families()
    assert data["version"] == 2
    assert fams[:3] == ["occasion", "weather", "time"] and len(fams) == 11
    assert tuple(fams) == cfgmod.FAMILIES
    assert set(views.FAMILY_NAMES) == set(fams)
    assert views.FAMILY_NAMES["time"] == "Time of day"
    assert {t["family"] for t in data["tags"]} == set(fams)
    family = {t["id"]: t["family"] for t in data["tags"]}
    assert len(family) == len(data["tags"]) == 137  # ids are unique
    assert {family[x] for x in ("night", "sunrise", "sunset", "full-moon")} == {"time"}
    assert family["magic"] == "element"
    assert vocab.name("chase") == "Foot or animal chase"
    assert family["car"] == family["living-room"] == "place"
    assert {"phone-call", "argument", "apology", "crying", "concert"} <= set(family)
    cfgmod.TagsCfg(families_off=["time"])  # the settings accept the new family


def test_cues_of_the_tag_list() -> None:
    """Objective tags say what to look for; a tag with see cues is only kept when one is seen."""
    from marcarr.stages import label, vocab

    for t in vocab.content_tags():
        cues = t.get("cues") or {}
        see, hear = cues.get("see") or [], cues.get("hear") or []
        if t["family"] == "mood":
            assert not cues, t["id"]
            continue
        if t["id"] != "montage":
            assert hear, t["id"]
        assert all(w and w == w.strip() for w in [*see, *hear]), t["id"]
        # strong language is heard, not seen: see cues would make it impossible to keep
        visible = t["family"] in {"weather", "time", "place", "creature", "action", "content"}
        if visible and t["id"] != "strong-language":
            assert len(see) >= 4, t["id"]
        if not see:
            assert label.cue_seen(t, [])
            continue
        for cue in see:  # the model names a cue in the list's words, or wraps it in its own
            assert label.cue_seen(t, [cue]), (t["id"], cue)
            assert label.cue_seen(t, [f"{cue} in the background"]), (t["id"], cue)
        assert not label.cue_seen(t, []), t["id"]
        assert not label.cue_seen(t, ["a plain grey wall", "end credits"]), t["id"]
    rain = vocab.get("rain")
    assert label.cue_seen(rain, ["rain"]) and label.cue_seen(rain, ["people under umbrellas"])
    assert not label.cue_seen(rain, ["two people talking in a kitchen"])
    doc = {"lines": [{"start": 5.0, "end": 7.0, "text": "I'm so sorry, it was my fault."}]}
    assert set(label.cue_hits(doc, vocab.content_tags())) == {"apology"}


def test_keyword_tags() -> None:
    from marcarr.stages import label, vocab

    words = ["Christmas", "boarding school", "full moon"]
    assert label.keyword_tags(words, vocab.content_tags()) == ["christmas", "full-moon"]


def test_measured_signals_line() -> None:
    from marcarr.stages import label, vocab

    signals = {"signals": {"dark": [[0, 40]], "loud": [[50, 53]], "still": [[58, 60]],
                           "dialogue": [[200, 300]]}}
    assert label.measured(signals, 0, 60) == ["loud", "dark"]  # still: 2 s of 60 is not enough
    assert label.measured(signals, 100, 160) == []
    assert label.measured(None, 0, 60) == []
    sheet = SimpleNamespace(legend=lambda: "1 0:00:05")
    cand = {"start": 0, "end": 60, "tags": ["night"], "why": "they whisper"}
    tags = [vocab.get("night")]
    assert "Measured: loud, dark\n" in label.look_prompt(sheet, "Film", cand, tags, [], signals)
    assert "Measured" not in label.look_prompt(sheet, "Film", cand, tags, [], None)
    assert "Measured" in label.LOOK_SYSTEM and "never" in label.LOOK_SYSTEM


def _fake_tagging(core, analysed, monkeypatch, look_tags, seen, keywords=None, sent=None):
    """Run the tags step with the models replaced; returns the look calls and TMDB calls.
    *sent* collects the tag list each dialogue read was given."""
    from marcarr import config as cfgmod
    from marcarr.stages import cast, label

    update = {"ai": {"enabled": True, "model": "fake/model", "auto_accept": 0.5},
              "tags": {"search_closely": []}}
    if keywords is not None:
        update["catalogues"] = {"tmdb_api_key": "test-key"}
    core.save_config(cfgmod.merge_update(core.cfg, update))
    first = core.store.result(analysed, "scenes")["scenes"][0]
    looks = []
    fetched = []

    def read(cfg, doc, title, tags, cast, cancel=None, progress=None):
        if sent is not None:
            sent.append(list(tags))
        return [{"start": first["start"], "end": first["end"], "tags": look_tags[:1], "people": [],
                 "why": "", "confidence": 0.9}]

    def look(cfg, sheet, title, cand, tags, cast, signals=None):
        ids = [t["id"] for t in tags]
        looks.append({"cand": cand, "ids": ids})
        return SimpleNamespace(match=True, tags=[t for t in look_tags if t in ids], seen=seen,
                               people=[], summary="", confidence=0.9, first_tile=1, last_tile=6)

    def fetch_keywords(key, tmdb_id, session=None):
        fetched.append((key, tmdb_id))
        return list(keywords or [])

    monkeypatch.setattr(label, "read", read)
    monkeypatch.setattr(label, "look", look)
    monkeypatch.setattr(cast, "fetch_keywords", fetch_keywords)
    monkeypatch.setattr("marcarr.stages.tagger.text_pass", lambda *a, **k: [])
    core.pipeline.submit(analysed, ["tags"])
    core.worker.run_pending("heavy")
    rows = core.store.step_rows(analysed)
    assert rows["tags"]["state"] == "done", rows["tags"]["detail"]
    return looks, fetched


def test_subjective_tags_are_never_auto_accepted(core, analysed, monkeypatch) -> None:
    _fake_tagging(core, analysed, monkeypatch, ["snow", "happy", "goodbye"], ["snow on the ground"])
    status = {t["tag"]: t["status"] for t in core.store.tags(video=analysed)}
    assert status["snow"] == "accepted"  # 0.9 sure, auto_accept 0.5
    assert status["happy"] == "proposed"  # mood
    assert status["goodbye"] == "proposed"  # beat


def test_a_tag_with_see_cues_needs_one_seen(core, analysed, monkeypatch) -> None:
    _fake_tagging(core, analysed, monkeypatch, ["rain", "happy"], ["two people talking"])
    assert {t["tag"] for t in core.store.tags(video=analysed)} == {"happy"}


def test_tmdb_keywords_join_the_close_search(core, analysed, monkeypatch) -> None:
    looks, fetched = _fake_tagging(core, analysed, monkeypatch, ["snow"], ["snow on the ground"],
                                   keywords=["halloween", "boarding school"])
    assert fetched == [("test-key", 1)]
    assert core.store.kv("keywords:movie:tmdb:1") == ["halloween", "boarding school"]
    # every scene the pass didn't tag halloween is looked at for it
    close = [c for c in looks if c["cand"].get("look_for")]
    assert close and all(c["ids"] == ["halloween"] for c in close)
    # a rerun reads the kept keywords instead of asking TMDB again
    core.pipeline.submit(analysed, ["tags"])
    core.worker.run_pending("heavy")
    assert len(fetched) == 1


# -- custom tags in the tags step ------------------------------------------------------
def test_custom_tags_reach_the_model(core, analysed, monkeypatch) -> None:
    """The model's tag list holds the custom tags that apply to the title; one it
    proposes lands as a proposal however sure the model is."""
    from marcarr import config as cfgmod
    from marcarr import tagging
    from marcarr.stages import label

    store = core.store
    store.upsert_title({"id": "movie:tmdb:2", "type": "movie", "name": "Other Film", "sort_name": "other film"})
    store.add_custom_tag("Catchphrase", hint="Someone says the line", hear="merry christmas")
    store.add_custom_tag("Red scarf", family="place", see=["red scarf"], title_id="movie:tmdb:1")
    store.add_custom_tag("Elsewhere", title_id="movie:tmdb:2")
    store.add_custom_tag("Moody", family="mood")
    store.add_custom_tag("Gone", hear="snow")
    store.update_custom_tag("gone", retired=True)
    core.save_config(cfgmod.merge_update(core.cfg, {"tags": {"families_off": ["mood"]}}))

    film = store.title("movie:tmdb:1")
    listed = {t["id"]: t["family"] for t in tagging.custom_tags(core, film)}
    # library-wide and this film's; not another film's, a family that is off, or a retired one
    assert listed == {"catchphrase": "custom", "red-scarf": "place"}
    store.upsert_title({"id": "show:tvdb:9", "type": "show", "name": "Night Shift", "sort_name": "night shift"})
    episode = {"id": "episode:tvdb:9:s01e01", "parent_id": "show:tvdb:9"}
    store.add_custom_tag("Show gag", title_id="show:tvdb:9")
    assert "show-gag" in {t["id"] for t in tagging.custom_tags(core, episode)}  # an episode of its show
    assert "show-gag" not in {t["id"] for t in tagging.custom_tags(core, film)}

    sent: list[list[dict]] = []
    looks, _ = _fake_tagging(core, analysed, monkeypatch, ["catchphrase", "red-scarf", "snow", "elsewhere"],
                             ["snow on the ground"], sent=sent)
    ids = [t["id"] for t in sent[0]]
    assert "catchphrase" in ids and "red-scarf" in ids and "snow" in ids
    assert not {"elsewhere", "moody", "gone", "show-gag", "happy"} & set(ids)
    # the reply schema accepts the custom ids and the list groups them for the model
    moments, _ = label.schemas(ids)
    assert moments(moments=[{"window": 0, "start": "0:00:01", "end": "0:00:05", "tags": ["catchphrase"]}])
    text = label.list_text(sent[0])
    assert "[custom]\ncatchphrase: Someone says the line (hear: merry christmas)" in text
    assert "red-scarf: " in text.split("[place]")[1].split("[")[0]
    assert all("elsewhere" not in c["ids"] for c in looks)

    rows = {t["tag"]: t for t in store.tags(video=analysed)}
    assert rows["snow"]["status"] == "accepted"  # 0.9 sure, auto_accept 0.5
    assert rows["catchphrase"]["status"] == "proposed"  # a custom tag is never auto-accepted
    assert "Merry Christmas" in rows["catchphrase"]["evidence"]["heard"]  # its hear cue, like a bundled one
    assert "red-scarf" not in rows and "elsewhere" not in rows  # a see cue nobody saw; not this film's


def test_a_custom_tag_with_a_family_is_never_auto_accepted(core, analysed, monkeypatch) -> None:
    core.store.add_custom_tag("Red scarf", family="place", see=["red scarf"])
    _fake_tagging(core, analysed, monkeypatch, ["red-scarf", "snow"], ["a red scarf", "snow on the ground"])
    status = {t["tag"]: t["status"] for t in core.store.tags(video=analysed)}
    assert status == {"red-scarf": "proposed", "snow": "accepted"}

