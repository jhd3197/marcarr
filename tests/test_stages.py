"""The analysis stages on their own: subtitles, scenes, cast, the AI passes, faces, signals.

Ported from FansCut's scene tests when FansCut started embedding Marcarr.
"""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest
from pydantic import ValidationError

from marcarr import ai
from marcarr.config import FAMILIES, AICfg
from marcarr.stages import cast as cast_mod
from marcarr.stages import faces, label, subs, tagger, vocab
from marcarr.stages import index as idx
from marcarr.stages import signals as smart

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")

SRT = """1
00:00:01,000 --> 00:00:03,500
<i>Happy Christmas, Harry.</i>

2
00:00:04,000 --> 00:00:06,000
- You've got presents!
- Me?

3
00:00:21,000 --> 00:00:24,000
{\\an8}Quidditch practice tonight.
"""

CAST = [{"name": "Daniel Radcliffe", "character": "Harry Potter", "photo": "h.jpg"},
        {"name": "Rupert Grint", "character": "Ron Weasley", "photo": "r.jpg"},
        {"name": "Richard Harris", "character": "Albus Dumbledore", "photo": ""}]


# -- subtitles ---------------------------------------------------------------------
def test_parse_srt_strips_tags_and_joins_rows():
    lines = subs.parse_srt(SRT)
    assert [(ln.start, ln.end) for ln in lines] == [(1.0, 3.5), (4.0, 6.0), (21.0, 24.0)]
    assert lines[0].text == "Happy Christmas, Harry."
    assert lines[1].text == "- You've got presents! - Me?"
    assert lines[2].text == "Quidditch practice tonight."


def test_sidecars_prefer_the_language_and_skip_forced(tmp_path):
    (tmp_path / "film.mkv").write_bytes(b"")
    for n in ("film.en.forced.srt", "film.fr.srt", "film.en.srt", "other.en.srt"):
        (tmp_path / n).write_text(SRT)
    assert [p.name for p in subs.sidecars(str(tmp_path / "film.mkv"))] == \
        ["film.en.srt", "film.en.forced.srt", "film.fr.srt"]


def test_pick_stream_prefers_full_dialogue_in_the_language():
    streams = [{"index": 0, "language": "en", "title": "Forced", "forced": True},
               {"index": 1, "language": "es", "title": "", "forced": False},
               {"index": 2, "language": "en", "title": "SDH", "forced": False},
               {"index": 3, "language": "en", "title": "English", "forced": False}]
    assert subs.pick_stream(streams)["index"] == 3
    assert subs.pick_stream(streams, "es")["index"] == 1
    assert subs.pick_stream([]) is None


@needs_ffmpeg
def test_subtitles_borrowed_from_a_same_length_copy(tmp_path):
    def clip(path, seconds):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color=c=red:s=64x48:r=5:d={seconds}", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(path)], check=True, timeout=120)

    clip(tmp_path / "film.mp4", 6)
    clip(tmp_path / "Film (2001).mkv", 6)
    (tmp_path / "Film (2001).en.srt").write_text(SRT, encoding="utf-8")
    lines, src = subs.load(str(tmp_path / "film.mp4"))
    assert len(lines) == 3 and src["kind"] == "sidecar (from Film (2001).mkv)"

    clip(tmp_path / "Film (2001).mkv", 9)  # a different cut lends nothing
    assert subs.load(str(tmp_path / "film.mp4")) == ([], {"kind": "none"})


# -- scenes ------------------------------------------------------------------------
def test_group_scenes_cuts_only_where_nobody_talks():
    shots = [(0, 10), (10, 22), (22, 30), (30, 45), (45, 50)]
    lines = [subs.Line(21.0, 23.0, "talking across the 22s cut")]
    scenes = idx.group_scenes(shots, lines, min_len=20)
    # 10s: too short; 22s: someone talks across it; 30s: quiet and long enough
    assert [(s["start"], s["end"], s["shots"]) for s in scenes] == [(0, 30, 3), (30, 50, 2)]


def test_group_scenes_forces_a_cut_past_max_len():
    shots = [(float(i), float(i + 1)) for i in range(0, 100)]
    lines = [subs.Line(0, 100, "nonstop")]
    scenes = idx.group_scenes(shots, lines, max_len=30)
    assert all(s["end"] - s["start"] <= 30 for s in scenes)
    assert scenes[-1]["end"] == 100


def test_snap_moves_to_the_nearest_cut_within_reach():
    doc = {"shots": [[0, 10.2], [10.2, 30]]}
    assert idx.snap(doc, 9.0) == 10.2
    assert idx.snap(doc, 20.0) == 20.0


def test_edges_wait_for_the_dialogue():
    doc = {"shots": [[0, 10], [10, 20], [20, 30], [30, 60]],
           "lines": [{"start": 18.0, "end": 22.0, "text": "a line across the 20 s cut"},
                     {"start": 9.0, "end": 11.0, "text": "a line across the 10 s cut"}]}
    assert idx.quiet_end(doc, 19.0) == 30  # 20 s has someone talking; 30 s is quiet
    # nothing quiet in reach: the pause after the line ends (22.3), not mid-line at 20
    assert idx.quiet_end(doc, 19.0, reach=5) == 22.3
    talky = {"shots": [[0, 10], [10, 40]],
             "lines": [{"start": 5, "end": 12, "text": "a"}, {"start": 12, "end": 16, "text": "b"},
                       {"start": 18, "end": 25, "text": "c"}]}
    assert idx.quiet_end(talky, 9.0, reach=10) == 16.3  # after "b", in the 16-18 s pause
    assert idx.quiet_start(talky, 20.0, reach=10) == 17.7  # before "c"
    assert idx.quiet_end({"shots": [[0, 10], [10, 30]], "lines": [{"start": 0, "end": 30, "text": "x"}]},
                         9.0) == 10  # no pause at all: nearest cut
    assert idx.quiet_start(doc, 19.0) == 0  # 20 and 10 are talked across
    assert idx.quiet_end(doc, 29.0) == 30  # a quiet cut in snapping distance wins
    assert idx.quiet_start(doc, 35.0) == 30


# -- the tag list --------------------------------------------------------------------
def test_vocab_ships_with_the_package():
    data = vocab.load()
    # v2: 137 tags in 11 families ("time" was added; "magic" joined "element")
    assert data["version"] == 2 and len(data["tags"]) == 137
    assert len(vocab.families()) == 11 and "time" in vocab.families()
    assert {t["id"] for t in vocab.content_tags() if t["family"] == "element"} == {"fire", "water", "magic"}
    assert list(FAMILIES) == vocab.families()  # Settings validates against the same list
    assert {t["family"] for t in vocab.content_tags(["mood", "content"])} == \
        set(vocab.families()) - {"mood", "content"}
    assert all(vocab.is_smart(t["id"]) for t in vocab.cut_tags())
    assert vocab.name("fc:filler") == "Filler" and vocab.name("fc:made-up") == "Made up"
    signals = {t["id"] for t in vocab.public()["signals"]}
    assert {"no-face", "dialogue", "long-take"} <= signals  # measured: not tags
    assert not any(t["id"].removeprefix("fc:") in signals for t in vocab.cut_tags())
    assert vocab.name("great-hall") == "Great hall"
    assert {t["id"] for t in vocab.cut_tags("person")} == {"fc:filler", "fc:spoiler"}
    assert {t["detect"] for t in vocab.cut_tags()} == {"auto", "ai", "person"}
    assert vocab.family("christmas") == "occasion" and vocab.family("fc:filler") is None


# -- cast --------------------------------------------------------------------------
def test_cast_from_plex_and_tmdb():
    plex = {"Role": [{"tag": "Daniel Radcliffe", "role": "Harry Potter", "thumb": "http://x/1.jpg"}, {"role": "?"}]}
    assert cast_mod.from_plex(plex) == [{"name": "Daniel Radcliffe", "character": "Harry Potter",
                                         "photo": "http://x/1.jpg", "order": 0}]
    tmdb = {"cast": [{"name": "B", "character": "Ron", "order": 1, "id": 2, "profile_path": None},
                     {"name": "A", "character": "Harry", "order": 0, "id": 1, "profile_path": "/a.jpg"}]}
    out = cast_mod.from_tmdb(tmdb)
    assert [c["name"] for c in out] == ["A", "B"]
    assert out[0]["photo"].endswith("/w185/a.jpg") and out[1]["photo"] == ""


def test_people_resolve_to_the_cast():
    assert cast_mod.match_person(CAST, "Harry")["name"] == "Daniel Radcliffe"
    assert cast_mod.match_person(CAST, "Professor Dumbledore")["name"] == "Richard Harris"
    assert cast_mod.match_person(CAST, "Rupert Grint")["character"] == "Ron Weasley"
    assert cast_mod.match_person(CAST, "Hagrid") is None
    people = cast_mod.resolve_people(CAST, [{"character": "Harry"}, {"character": "harry potter"},
                                            {"character": "Hagrid"}])
    assert people == [{"name": "Daniel Radcliffe", "character": "Harry Potter"}, {"character": "Hagrid"}]


# -- the single-tag AI pass, pure parts ------------------------------------------------
def _doc():
    scenes = [{"id": f"s{i}", "start": i * 100.0, "end": (i + 1) * 100.0, "shots": 3} for i in range(7)]
    lines = [{"start": 105, "end": 108, "text": "Happy Christmas!"},
             {"start": 450, "end": 452, "text": "Catch the snitch!"}]
    return {"scenes": scenes, "lines": lines, "shots": [[s["start"], s["end"]] for s in scenes]}


def test_windows_and_text():
    doc = _doc()
    assert tagger.windows(doc, 300) == [(0.0, 300.0), (300.0, 600.0), (600.0, 700.0)]
    assert tagger.window_text(doc, (0, 300)) == "[0:01:45] Happy Christmas!"
    assert tagger.batches(doc, tagger.windows(doc, 300)) == [[0, 1, 2]]


def test_text_pass_turns_hits_into_ranges(monkeypatch):
    cfg = AICfg(model="ollama/x")
    seen = {}

    def fake(cfg_, schema, system, prompt, **kw):
        seen["prompt"] = prompt
        return tagger.WindowHits(matches=[
            tagger.WindowHit(window=0, start="1:40", end="3:00", why="presents", people=["Harry"],
                             confidence=0.9),
            tagger.WindowHit(window=9, start="0:10", end="0:20")])  # unknown window: ignored

    monkeypatch.setattr(ai, "ask_json", fake)
    out = tagger.text_pass(cfg, _doc(), "HP1", "christmas", "Christmas at Hogwarts", CAST)
    assert out == [{"start": 100.0, "end": 180.0, "why": "presents", "people": ["Harry"], "confidence": 0.9}]
    assert "Window 0" in seen["prompt"] and "Harry Potter (Daniel Radcliffe)" in seen["prompt"]


def test_refine_merge_and_sweep():
    c = {"start": 0.0, "end": 60.0}
    check = tagger.SheetCheck(match=True, first_tile=2, last_tile=3)
    times = [5.0, 15.0, 25.0, 35.0, 45.0, 55.0]
    assert tagger.refine(c, check, times) == (10.0, 30.0)
    merged = tagger.merge([{"start": 0, "end": 10, "people": ["A"], "confidence": 0.2, "why": ""},
                           {"start": 15, "end": 30, "people": ["B"], "confidence": 0.8, "why": "x"},
                           {"start": 100, "end": 110, "people": [], "confidence": 0.1, "why": ""}])
    assert [(m["start"], m["end"], m["people"], m["confidence"]) for m in merged] == \
        [(0, 30, ["A", "B"], 0.8), (100, 110, [], 0.1)]
    assert [s["start"] for s in tagger.sweep_candidates(_doc(), max_lines=0)] == [0.0, 200.0, 300.0, 500.0, 600.0]


def test_grid_grows_with_the_range():
    assert tagger.sheet_shape(45) == (3, 2, 240)
    assert tagger.sheet_shape(77) == (3, 3, 240)
    assert tagger.sheet_shape(180) == (3, 3, 240)
    cols, rows, h = tagger.sheet_shape(400)
    assert (cols, rows) == (4, 3) and cols * (h * 16 // 9) + 12 <= 1568


def test_edge_pass_times():
    times = [2.5, 7.5, 12.5, 17.5, 22.5, 27.5]  # 30 s window, 5 s apart
    assert tagger.edge_time(times, tagger.EdgeCheck(first_tile=3, last_tile=6), "start") == 10.0
    assert tagger.edge_time(times, tagger.EdgeCheck(first_tile=1, last_tile=4), "end") == 20.0
    assert tagger.edge_time(times, tagger.EdgeCheck(first_tile=5, last_tile=2), "end") is None
    assert tagger.edge_time(times, tagger.EdgeCheck(first_tile=0, last_tile=9), "start") is None
    assert tagger.edge_window(5, 100) == (0.0, 20.0)
    assert tagger.edge_window(95, 100) == (80.0, 100)


# -- faces -------------------------------------------------------------------------
def test_face_names_need_a_looser_match_for_people_in_the_moment():
    scores = [(0.35, "Rupert Grint"), (0.33, "Daniel Radcliffe")]
    assert faces.pick(scores, set()) is None
    assert faces.pick(scores, {"Daniel Radcliffe"}) == ("Daniel Radcliffe", 0.33)
    assert faces.pick([(0.45, "Tom Felton")], set()) == ("Tom Felton", 0.45)

    class Engine:  # two faces: one matches Harry, one nobody
        def detect(self, img):
            return [[10, 20, 50, 60, *[0] * 10, 0.9], [200, 20, 40, 40, *[0] * 10, 0.8]]

        def feature(self, img, f):
            return f[0]

        def match(self, a, b):
            return 0.38 if a == 10 and b == "h" else 0.1

    class Img:
        shape = (100, 400, 3)

    refs = {"Daniel Radcliffe": {"character": "Harry Potter", "photo": "h.jpg", "feature": "h"}}
    got = faces.name_faces(Engine(), Img(), refs, {"Daniel Radcliffe"})
    assert got[0]["name"] == "Daniel Radcliffe" and got[0]["character"] == "Harry Potter"
    assert got[0]["sure"] is False and got[0]["match"] == 0.38  # below SURE: "Harry Potter?"
    assert got[0]["box"] == [0.025, 0.2, 0.125, 0.6]
    assert got[1]["name"] is None

    class Twins(Engine):  # both faces look like Hermione: only the closer one is her
        def match(self, a, b):
            return {10: 0.6, 200: 0.5}[a]

    refs = {"Emma Watson": {"character": "Hermione Granger", "photo": "", "feature": "e"}}
    got = faces.name_faces(Twins(), Img(), refs, set())
    assert [g["name"] for g in got] == ["Emma Watson", None]


def test_face_models_download_once(tmp_path):
    class Resp:
        content = b"onnx"

        def raise_for_status(self):
            pass

    calls = []

    class Session:
        def get(self, url, timeout):
            calls.append(url)
            return Resp()

    d, r = faces.ensure_models(tmp_path, Session())
    assert d.name == "face_detection_yunet_2023mar.onnx" and r.read_bytes() == b"onnx"
    faces.ensure_models(tmp_path, Session())
    assert len(calls) == 2


# -- signals (measured, never tags) ----------------------------------------------------
def test_signals_from_numbers():
    shots = [[0, 10], [10, 11], [11, 12], [12, 13], [13, 14], [14, 15], [15, 16], [16, 40]]
    lines = [{"start": 16.0, "end": 19.0, "text": "Happy Christmas."},
             {"start": 20.0, "end": 24.0, "text": "Me?"},
             {"start": 30.0, "end": 31.0, "text": "[CAT MEOWS]"}]
    doc = {"duration": 40.0, "shots": shots, "lines": lines}
    flat = np.zeros((36, 64), np.float32)
    samples = []
    for t in range(40):
        if t < 10:  # a dark, still, empty opening
            samples.append(smart.Sample(t, 13.0, flat, 0, 0.0))
        elif t < 16:  # quick shots with a crowd
            samples.append(smart.Sample(t, 120.0, flat + t * 10, 4, 0.2))
        else:  # a long close-up
            samples.append(smart.Sample(t, 120.0, flat + (t % 2) * 40, 1, 0.5))
    loud = np.full(80, -30.0, np.float32)
    loud[0:10] = -70  # silent first 5 s
    loud[50] = -5  # one bang at 25 s
    got = smart.label(doc, samples, loud)
    assert got["no-face"] == [(0.0, 10.0)]
    assert got["dark"] == [(0.0, 10.0)] and got["still"] == [(0.0, 10.0)]
    assert got["group"] == [(10.0, 16.0)]
    assert got["close-up"] == [(16.0, 40.0)]
    assert got["long-take"] == [(16.0, 40.0)]
    assert got["fast-cutting"] and got["fast-cutting"][0][0] <= 11
    assert got["dialogue"] == [(16.0, 24.0)]  # the cat isn't dialogue
    assert got["silence"] == [(0.0, 5.0)]
    assert got["loud"] == [(23.5, 27.0)]
    assert smart.speech("- Me?") and not smart.speech("♪ Hedwig's theme ♪")


# -- one-pass labelling ----------------------------------------------------------------
def test_label_fits_stretches_to_their_dialogue():
    doc = {"scenes": [{"start": 0, "end": 60}, {"start": 60, "end": 140}, {"start": 140, "end": 300}],
           "lines": [{"start": 78, "end": 80, "text": "Professor McGonagall."},
                     {"start": 150, "end": 152, "text": "Up. Get up!"},
                     {"start": 200, "end": 202, "text": "[OWL HOOTS]"}]}
    # the model gave the window's start (a studio logo): the stretch moves to the first line's scene
    assert label.fit(doc, 0, 60, 300) == (60, 140)
    # a stretch spilling over is cut back to the scenes its lines sit in
    assert label.fit(doc, 30, 280, 300) == (60, 280)
    # no speech at all in reach (a sound description isn't speech): left alone
    assert label.fit(doc, 190, 230, 240) == (190, 230)


def test_label_sweep_covers_gaps_and_faceless_stretches():
    doc = {"scenes": [{"start": 0, "end": 30}, {"start": 30, "end": 40}, {"start": 40, "end": 100}],
           "lines": [{"start": t, "end": t + 1, "text": "Talk."} for t in (1, 20, 31, 34, 41, 80)]}
    cands = [{"start": 40, "end": 100, "tags": ["snow"], "people": [], "why": "", "confidence": 0.5}]
    sig = {"signals": {"no-face": [[33.0, 39.0], [90.0, 95.0]]}}
    got = [(c["start"], c["end"]) for c in label.sweep(doc, cands, sig)]
    assert (0, 30) in got and (30, 40) not in got  # uncovered scenes of 15 s or more
    assert (33.0, 39.0) in got  # a long enough no-face stretch nobody covers
    assert (90.0, 95.0) not in got  # covered by the dialogue pass
    assert all(c["tags"] == [] for c in label.sweep(doc, cands, None))


def test_label_schemas_only_take_listed_ids():
    moments, look = label.schemas(["snow"])
    assert look.model_validate({"match": False, "tags": []}).match is False  # can turn a stretch down
    with pytest.raises(ValidationError):
        moments.model_validate({"moments": [{"window": 0, "start": "0", "end": "1",
                                             "tags": ["quidditch"]}]})


def test_cues_mark_what_is_said_and_seen():
    halloween = vocab.get("halloween")
    assert "pumpkins" in halloween["cues"]["see"] and "trick or treat" in halloween["cues"]["hear"]
    occasions = [t for t in vocab.content_tags() if t["family"] == "occasion"]
    assert all(t.get("cues", {}).get("see") and t["cues"].get("hear") for t in occasions)
    doc = {"lines": [{"start": 10, "end": 12, "text": "Happy Halloween, everyone!"},
                     {"start": 50, "end": 52, "text": "Make a wish, Harry."},
                     {"start": 90, "end": 92, "text": "Halloweens past were dull."}]}
    hits = label.cue_hits(doc, occasions)
    assert [t for t, _ in hits["halloween"]] == [10]  # whole words only
    assert hits["birthday"] == [(50, "Make a wish")]
    assert label.heard_in(hits, 0, 60) == "halloween ('Halloween'), birthday ('Make a wish')"
    assert "see: pumpkins" in label.list_text([halloween])
    assert label.keyword_tags(["christmas", "boarding school"], occasions) == ["christmas"]
    scenes = {"scenes": [{"start": 0, "end": 5}, {"start": 5, "end": 40}, {"start": 40, "end": 90}]}
    got = label.scenes_to_look(scenes, ["halloween", "snow"],
                               [{"start": 50, "end": 60, "tags": ["halloween", "snow"]},
                                {"start": 10, "end": 20, "tags": ["christmas", "halloween"]}])
    # a scene tagged halloween is still looked at for snow; a scene with both is done
    assert [(c["start"], c["end"], c["look_for"]) for c in got] == [(5, 40, ["snow"])]
    assert label.cue_seen(halloween, ["carved pumpkins on the tables"])
    assert not label.cue_seen(halloween, ["Halloween feast", "night"])
    # v2 gave place tags cues too, so a cue-less tag is a mood one
    mood = next(t for t in vocab.content_tags() if t["family"] == "mood")
    assert not mood.get("cues", {}).get("see") and label.cue_seen(mood, [])  # no cues: nothing to prove
    assert not label.cue_seen(vocab.get("castle"), [])  # castle has see cues now: it must be seen
