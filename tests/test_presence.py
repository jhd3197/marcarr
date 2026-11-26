"""How a character is in a scene: seen, heard speaking, or only named."""

from __future__ import annotations

from types import SimpleNamespace


def _tag_with_fake_model(core, vid, monkeypatch, *, said, seen) -> None:
    from marcarr import config as cfgmod
    from marcarr.stages import label

    core.save_config(cfgmod.merge_update(core.cfg, {"ai": {"enabled": True, "model": "fake/model"}}))
    first = core.store.result(vid, "scenes")["scenes"][0]

    def read(cfg, doc, title, tags, cast, cancel=None, progress=None):
        return [{"start": first["start"], "end": first["end"], "tags": ["christmas"], "people": said,
                 "why": "they say Merry Christmas", "confidence": 0.6}]

    def look(cfg, sheet, title, cand, tags, cast, signals=None):
        return SimpleNamespace(match=True, tags=["christmas"], seen=["Christmas tree"], people=seen,
                               summary="Presents by the tree", confidence=0.6, first_tile=1, last_tile=6)

    monkeypatch.setattr(label, "read", read)
    monkeypatch.setattr(label, "look", look)
    monkeypatch.setattr("marcarr.stages.tagger.text_pass", lambda *a, **k: [])
    core.pipeline.submit(vid, ["tags"])
    core.worker.run_pending("heavy")


def test_the_tagger_keeps_seen_and_named_apart(core, client, analysed, monkeypatch) -> None:
    _tag_with_fake_model(core, analysed, monkeypatch, said=["Mira", "Tom"], seen=["Mira"])
    xmas = next(t for t in core.store.tags(video=analysed) if t["tag"] == "christmas")
    assert xmas["people"] == ["mira-vale"]
    assert xmas["mentioned"] == ["tom-reed"]
    s1 = client.get(f"/api/v1/videos/{analysed}/scenes").json()["items"][0]
    assert s1["seen"] == ["mira-vale"] == s1["people"]
    assert s1["mentioned"] == ["tom-reed"]
    assert s1["speakers"] == []


def test_someone_seen_is_never_also_mentioned(core, analysed) -> None:
    row = core.store.add_tag(analysed, "movie:tmdb:1", "snow", 0, 5, people=["mira-vale"],
                             mentioned=["mira-vale", "tom-reed"])
    assert row["mentioned"] == ["tom-reed"]
    row = core.store.update_tag(row["id"], people=["mira-vale", "tom-reed"])
    assert row["mentioned"] == []


def test_apps_report_a_speaker(client, analysed) -> None:
    base = f"/api/v1/videos/{analysed}"
    h = {"X-Marcarr-Client": "doblarr"}
    r = client.post(base + "/presence", headers=h,
                    json={"person": "tom-reed", "how": "speaker", "start": 1, "end": 4, "at": 2.5,
                          "status": "accepted"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["status"] == "proposed"  # an app proposes; a person decides
    assert p["source"] == "doblarr" and p["at"] == 2.5
    s1 = client.get(base + "/scenes").json()["items"][0]
    assert s1["speakers"] == ["tom-reed"]
    assert "tom-reed" not in s1["seen"]
    detail = client.get(base + "/scenes/1").json()
    assert [x["id"] for x in detail["presence"]] == [p["id"]]
    assert client.get(base + "/presence").json()["total"] == 1

    # dropped: no longer counted
    assert client.post(f"/api/v1/presence/{p['id']}/drop").json()["status"] == "rejected"
    assert client.get(base + "/scenes").json()["items"][0]["speakers"] == []
    assert client.delete(f"/api/v1/presence/{p['id']}").status_code == 204


def test_presence_is_checked(client, analysed) -> None:
    base = f"/api/v1/videos/{analysed}/presence"
    assert client.post(base, json={"person": "tom-reed", "how": "waved", "start": 1, "end": 2}).status_code == 400
    assert client.post(base, json={"person": "nobody", "how": "seen", "start": 1, "end": 2}).status_code == 404


def test_tag_evidence_can_carry_a_time(core, analysed) -> None:
    row = core.store.add_tag(analysed, "movie:tmdb:1", "snow", 0, 5, evidence={
        "heard": [{"text": "Look at the snow", "at": 8.4}, "snowing"],
        "seen": [{"text": "", "at": 3}, {"text": "snow at the window", "at": "x"}]})
    assert row["evidence"]["heard"] == [{"text": "Look at the snow", "at": 8.4}, "snowing"]
    assert row["evidence"]["seen"] == ["snow at the window"]
