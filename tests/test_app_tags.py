"""Tags an app owns (FansCut's cut tags, ``fc:``) and the tag list served as data."""

from __future__ import annotations

from marcarr.views import tag_id


def test_an_app_tag_keeps_its_prefix() -> None:
    assert tag_id("fc:filler") == "fc:filler"
    assert tag_id("fc:Made Up!") == "fc:made-up"
    assert tag_id("FC:Recap") == "fc:recap"
    assert tag_id("fc:") == ""
    assert tag_id("Christmas") == "christmas"  # a content tag still resolves by name
    assert tag_id("Great Hall") == "great-hall"


def test_cut_tags_are_stored_like_any_tag(client, analysed) -> None:
    url = f"/api/v1/videos/{analysed}/tags"
    made = client.post(url, json={"tags": ["fc:filler", "fc:spoiler"], "start": 1.0, "end": 9.0,
                                  "snap": False}).json()
    assert [(t["tag"], t["name"], t["family"]) for t in made] == [
        ("fc:filler", "Filler", None), ("fc:spoiler", "Spoiler", None)]
    assert made[0]["start"] == 1.0 and made[0]["end"] == 9.0  # not moved to a camera cut
    kept = client.post(f"/api/v1/tags/{made[0]['id']}/keep").json()
    assert kept["status"] == "accepted"
    rows = client.get(url, params={"status": "all"}).json()["items"]
    assert {(t["tag"], t["status"]) for t in rows} == {("fc:filler", "accepted"), ("fc:spoiler", "proposed")}
    # a kept cut tag is on its scene and found by scene search, like a content tag
    hits = client.get("/api/v1/search/scenes", params={"tags": "fc:filler"}).json()
    assert hits["total"] >= 1
    assert client.delete(f"/api/v1/tags/{made[1]['id']}").status_code == 204


def test_the_tag_list_as_data(client) -> None:
    v = client.get("/api/v1/tags/vocabulary").json()
    assert v["version"] >= 2 and "occasion" in v["families"]
    assert any(t["id"] == "christmas" and t["family"] == "occasion" for t in v["tags"])
    assert {t["id"] for t in v["cut_tags"]} >= {"fc:filler", "fc:spoiler", "fc:recap"}
    assert any(s["id"] == "dark" for s in v["signals"])
    assert v["mine"] == []
    client.post("/api/v1/tags/mine", json={"name": "Wand duel", "family": "action", "see": ["wands"]})
    mine = client.get("/api/v1/tags/vocabulary").json()["mine"]
    assert [(t["id"], t["name"], t["family"], t["cues"]["see"]) for t in mine] == [
        ("wand-duel", "Wand duel", "action", ["wands"])]
