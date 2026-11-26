"""The v1 API as the UI and other apps use it."""

from __future__ import annotations

from urllib.parse import quote


def test_empty_install(client) -> None:
    assert client.get("/api/v1/status").json()["review"] == 0
    assert client.get("/api/v1/titles").json()["total"] == 0
    tags = client.get("/api/v1/tags").json()
    assert sum(len(f["tags"]) for f in tags["families"]) == 137


def test_title_video_scenes(client, analysed) -> None:
    t = client.get("/api/v1/titles/" + quote("movie:tmdb:1")).json()
    assert t["video"]["id"] == analysed
    assert t["video"]["steps"]["scenes"] == "done"
    assert [c["id"] for c in t["cast"]] == ["mira-vale", "tom-reed"]
    scenes = client.get(f"/api/v1/videos/{analysed}/scenes").json()
    assert scenes["total"] >= 1
    s1 = client.get(f"/api/v1/videos/{analysed}/scenes/1").json()
    assert s1["lines"] and s1["frames"]
    assert client.get(s1["still"]).headers["content-type"] == "image/jpeg"
    doc = client.get(f"/api/v1/videos/{analysed}/analysis").json()
    assert doc["format"] == "marcarr-analysis/1" and len(doc["shots"]) == 3


def test_propose_keep_drop_and_search(client, analysed) -> None:
    r = client.post(f"/api/v1/videos/{analysed}/tags",
                    json={"tag": "Snow", "start": 1, "end": 7, "evidence": {"seen": ["snow"]}})
    tag = r.json()
    assert tag["tag"] == "snow" and tag["status"] == "proposed" and tag["family"] == "weather"
    assert client.get("/api/v1/status").json()["review"] == 1
    review = client.get("/api/v1/review").json()
    assert review["total"] == 1 and review["groups"][0]["items"][0]["scene"] == 1
    # accepted only by default: nothing yet
    assert client.get("/api/v1/search/scenes", params={"tags": "snow"}).json()["total"] == 0
    assert client.get("/api/v1/search/scenes", params={"tags": "snow", "status": "proposed"}).json()["total"] == 1
    assert client.post(f"/api/v1/tags/{tag['id']}/keep").json()["status"] == "accepted"
    hits = client.get("/api/v1/search/scenes", params={"tags": "Snow"}).json()
    assert hits["total"] == 1 and hits["items"][0]["video"] == analysed
    assert client.post(f"/api/v1/tags/{tag['id']}/drop").json()["status"] == "rejected"
    at = client.get(f"/api/v1/videos/{analysed}/at/3").json()
    assert at["scene"] == 1 and "dialogue" in at["signals"]


def test_words_search(client, analysed) -> None:
    hits = client.get("/api/v1/search/scenes", params={"q": "snow"}).json()
    assert hits["total"] == 1 and "snow" in hits["items"][0]["line"]


def test_move_a_scene_edge(client, core, analysed) -> None:
    scenes = client.get(f"/api/v1/videos/{analysed}/scenes").json()["items"]
    end = scenes[0]["end"]
    out = client.patch(f"/api/v1/videos/{analysed}/scenes/1", json={"end": end - 3}).json()
    assert abs(out["end"] - (end - 3)) < 0.01
    assert core.store.scene_edits(analysed)


def test_keys_and_scopes(client, analysed) -> None:
    key = client.post("/api/v1/keys", json={"name": "Doblarr", "scopes": ["read", "propose"]}).json()["key"]
    h = {"X-Api-Key": key}
    assert client.get("/api/v1/titles", headers=h).status_code == 200
    r = client.post(f"/api/v1/videos/{analysed}/tags", headers=h,
                    json={"tag": "rain", "start": 1, "end": 5, "status": "accepted"})
    assert r.json()["status"] == "proposed" and r.json()["source"] == "doblarr"
    assert client.post(f"/api/v1/tags/{r.json()['id']}/keep", headers=h).status_code == 403
    assert client.get("/api/v1/settings", headers=h).status_code == 403
    assert client.get("/api/v1/titles", headers={"X-Api-Key": "nope"}).status_code == 401


def test_settings_mask_secrets(client) -> None:
    client.put("/api/v1/settings", json={"plex": {"url": "http://plex:32400", "token": "secret-token"}})
    s = client.get("/api/v1/settings").json()
    assert s["plex"]["token"] == "••••"
    # sending the mask back keeps the token
    client.put("/api/v1/settings", json={"plex": {"token": "••••", "url": "http://plex:32400"}})
    from marcarr.routes.common import core

    assert core().cfg.plex.token == "secret-token"
    assert client.put("/api/v1/settings", json={"nope": 1}).status_code == 400


def test_places_and_people(client, core, analysed) -> None:
    top = client.post("/api/v1/places", json={"name": "Winter House", "franchise": "Winter"}).json()
    hall = client.post("/api/v1/places", json={"name": "Great Hall", "inside": top["id"]}).json()
    assert hall["id"] == "winter-house/great-hall"
    client.post(f"/api/v1/videos/{analysed}/scenes/1/place", json={"place": hall["id"]})
    p = client.get("/api/v1/places/winter-house").json()
    assert p["scenes"] == 1 and p["children"][0]["name"] == "Great Hall"
    assert client.get("/api/v1/places/winter-house/great-hall/scenes").json()["total"] == 1
    s1 = client.get(f"/api/v1/videos/{analysed}/scenes/1").json()
    assert s1["place_name"] == "Winter House › Great Hall"
    people = client.get("/api/v1/people").json()
    assert {p["id"] for p in people["items"]} == {"mira-vale", "tom-reed"}


def test_webhooks_record_calls(client) -> None:
    hook = client.post("/api/v1/webhooks", json={"url": "http://127.0.0.1:9/hook", "events": ["tag.kept"]}).json()
    call = client.post(f"/api/v1/webhooks/{hook['id']}/test").json()
    assert call["event"] == "tag.kept" and call["code"] is None and call["error"]
    assert client.get("/api/v1/webhooks").json()[0]["state"] == "failing"


def _tag(client, tag: str) -> dict:
    return next(t for f in client.get("/api/v1/tags").json()["families"] for t in f["tags"] if t["id"] == tag)


def test_tag_counts_are_the_scenes_search_shows(client, analysed) -> None:
    scenes = client.get(f"/api/v1/videos/{analysed}/scenes").json()["items"]
    end = scenes[-1]["end"]

    def found(status: str) -> int:
        return client.get("/api/v1/search/scenes", params={"tags": "snow", "status": status}).json()["total"]

    # one range over the whole film: one row, but every scene it covers counts
    whole = client.post(f"/api/v1/videos/{analysed}/tags", json={"tag": "snow", "start": 0, "end": end}).json()
    n = _tag(client, "snow")["counts"]
    assert n == {"accepted": 0, "proposed": len(scenes), "rejected": 0}
    assert found("review") == len(scenes) and found("accepted") == 0
    # a tag with only proposals is in use
    used = client.get("/api/v1/tags", params={"used": True}).json()
    assert [t["id"] for f in used["families"] for t in f["tags"]] == ["snow"]

    # a second range inside the first scene, kept: that scene is kept, not waiting
    first = scenes[0]
    kept = client.post(f"/api/v1/videos/{analysed}/tags",
                       json={"tag": "snow", "start": first["start"], "end": first["end"]}).json()
    client.post(f"/api/v1/tags/{kept['id']}/keep")
    n = _tag(client, "snow")["counts"]
    assert n == {"accepted": 1, "proposed": len(scenes) - 1, "rejected": 0}
    assert found("accepted") == n["accepted"] and found("review") == n["proposed"]
    assert found("proposed") == n["accepted"] + n["proposed"]

    client.post(f"/api/v1/tags/{whole['id']}/drop")
    assert _tag(client, "snow")["counts"] == {"accepted": 1, "proposed": 0, "rejected": 1}


def test_tags_say_why_the_list_is_empty(client, core, analysed) -> None:
    assert client.get("/api/v1/tags").json()["tagging"] == {"enabled": False, "model": False, "videos_done": 0}
    client.put("/api/v1/settings", json={"ai": {"enabled": True, "model": "openai/gpt-4o-mini"}})
    core.store.set_step(analysed, "tags", state="done")
    assert client.get("/api/v1/tags").json()["tagging"] == {"enabled": True, "model": True, "videos_done": 1}


def test_collections_are_saved_searches(client, analysed) -> None:
    scenes = client.get(f"/api/v1/videos/{analysed}/scenes").json()["items"]
    end = scenes[-1]["end"]
    assert client.get("/api/v1/collections").json() == {"total": 0, "items": []}

    # a name and something to search for are both needed
    assert client.post("/api/v1/collections", json={"name": " ", "tags": ["snow"]}).status_code == 400
    assert client.post("/api/v1/collections", json={"name": "Nothing"}).status_code == 400
    assert client.post("/api/v1/collections", json={"name": "Odd", "tags": ["not-a-tag"]}).status_code == 400
    assert client.post("/api/v1/collections", json={"name": "Odd", "signals": ["nope"]}).status_code == 400

    col = client.post("/api/v1/collections", json={"name": "Snowy nights", "tags": ["Snow", "night"]}).json()
    assert col["tags"] == ["snow", "night"] and col["person"] is None and col["q"] == "" and col["scenes"] == 0
    # names are unique whatever the case
    assert client.post("/api/v1/collections", json={"name": "snowy NIGHTS", "q": "snow"}).status_code == 400
    words = client.post("/api/v1/collections", json={"name": "Snow talk", "q": "snow"}).json()
    assert words["scenes"] == client.get("/api/v1/search/scenes", params={"q": "snow"}).json()["total"] == 1

    # it is a query: scenes tagged later show up, counted as search counts kept scenes
    for tag in ("snow", "night"):
        t = client.post(f"/api/v1/videos/{analysed}/tags", json={"tag": tag, "start": 0, "end": end}).json()
        assert _collection(client, col["id"])["scenes"] == 0  # proposed, or only one of the two
        client.post(f"/api/v1/tags/{t['id']}/keep")
    found = client.get("/api/v1/search/scenes", params={"tags": "snow,night"}).json()["total"]
    assert _collection(client, col["id"])["scenes"] == found == len(scenes)

    # rename: same rules, and its own name in another case is fine
    assert client.patch(f"/api/v1/collections/{col['id']}", json={"name": "snow talk"}).status_code == 400
    assert client.patch(f"/api/v1/collections/{col['id']}", json={"name": ""}).status_code == 400
    assert client.patch(f"/api/v1/collections/{col['id']}", json={"name": "SNOWY nights"}).json()["name"] == "SNOWY nights"
    assert [c["name"] for c in client.get("/api/v1/collections").json()["items"]] == ["Snow talk", "SNOWY nights"]

    # a key may read them, only the web page changes them
    key = client.post("/api/v1/keys", json={"name": "App", "scopes": ["read", "review"]}).json()["key"]
    h = {"X-Api-Key": key}
    assert client.get("/api/v1/collections", headers=h).json()["total"] == 2
    assert client.post("/api/v1/collections", headers=h, json={"name": "X", "q": "x"}).status_code == 403
    assert client.delete(f"/api/v1/collections/{col['id']}", headers=h).status_code == 403

    assert client.delete(f"/api/v1/collections/{col['id']}").status_code == 204
    assert client.delete(f"/api/v1/collections/{col['id']}").status_code == 404
    assert client.get("/api/v1/collections").json()["total"] == 1


def _collection(client, cid: str) -> dict:
    return next(c for c in client.get("/api/v1/collections").json()["items"] if c["id"] == cid)


def test_search_by_signal(client, core, analysed) -> None:
    scenes = client.get(f"/api/v1/videos/{analysed}/scenes").json()["items"]
    first = scenes[0]
    length = first["end"] - first["start"]
    doc = core.store.result(analysed, "signals") or {"signals": {}}

    def found(**params: str) -> int:
        return client.get("/api/v1/search/scenes", params=params).json()["total"]

    # a signal over most of the first scene finds it; over a sliver of it does not
    doc["signals"]["dark"] = [[first["start"], first["start"] + length * 0.6]]
    doc["signals"]["fade"] = [[first["start"], first["start"] + length * 0.2]]
    core.store.save_result(analysed, "signals", doc)
    assert found(signals="dark") == 1
    assert found(signals="fade") == 0 and found(signals="dark,fade") == 0
    assert found(signals="never-measured") == 0
    # with words: both must hold in the same scene
    assert found(signals="dark", q="christmas") == found(q="christmas")
    assert found(signals="fade", q="christmas") == 0

    col = client.post("/api/v1/collections", json={"name": "In the dark", "signals": ["dark"]}).json()
    assert col["signals"] == ["dark"] and col["scenes"] == 1


# -- custom tags ("My tags") -----------------------------------------------------------
def _mine(client) -> list[dict]:
    return client.get("/api/v1/tags").json()["mine"]


def test_custom_tags_create_edit_and_scope(client, core, analysed) -> None:
    assert _mine(client) == []
    core.store.upsert_title({"id": "show:tvdb:9", "type": "show", "name": "Night Shift", "sort_name": "night shift"})
    core.store.upsert_title({"id": "episode:tvdb:9:s01e01", "type": "episode", "name": "Pilot", "parent_id": "show:tvdb:9",
                             "season": 1, "episode": 1})

    tag = client.post("/api/v1/tags/mine", json={
        "name": "  Running   gag ", "family": "beat", "hint": "The stapler goes missing again",
        "see": "stapler, empty desk, stapler", "hear": ["where's my stapler"], "scope": "show:tvdb:9"}).json()
    assert tag["id"] == "running-gag" and tag["name"] == "Running gag" and tag["family"] == "beat"
    assert tag["see"] == ["stapler", "empty desk"] and tag["hear"] == ["where's my stapler"]
    assert tag["scope"] == {"title": "show:tvdb:9", "name": "Night Shift", "type": "show", "year": None}
    assert tag["custom"] and not tag["retired"] and not tag["label"]
    assert tag["counts"] == {"accepted": 0, "proposed": 0, "rejected": 0}
    # the bundled list is untouched, and the new tag is listed at once, in the same shape
    doc = client.get("/api/v1/tags").json()
    assert sum(len(f["tags"]) for f in doc["families"]) == 137
    assert doc["mine"] == [tag]
    assert set(doc["families"][0]["tags"][0]) <= set(tag)

    # no family and the whole library are the defaults
    free = client.post("/api/v1/tags/mine", json={"name": "Catchphrase"}).json()
    assert free["family"] is None and free["scope"] is None and free["see"] == [] and free["hint"] == ""
    assert [t["id"] for t in _mine(client)] == ["running-gag", "catchphrase"]
    assert [t["id"] for t in client.get("/api/v1/tags", params={"family": "Beat"}).json()["mine"]] == ["running-gag"]

    # edit: name, family, hint, cues and scope; the id stays
    out = client.patch("/api/v1/tags/mine/running-gag", json={
        "name": "Stapler gag", "family": None, "hint": "", "see": [], "hear": "stapler", "scope": "movie:tmdb:1"}).json()
    assert out["id"] == "running-gag" and out["name"] == "Stapler gag" and out["family"] is None
    assert out["see"] == [] and out["hear"] == ["stapler"] and out["scope"]["name"] == "Test Film"
    assert client.patch("/api/v1/tags/mine/running-gag", json={"scope": None}).json()["scope"] is None
    assert client.patch("/api/v1/tags/mine/running-gag", json={"name": "stapler GAG"}).json()["name"] == "stapler GAG"
    assert client.patch("/api/v1/tags/mine/nope", json={"name": "X"}).status_code == 404

    # names and ids resolve everywhere a bundled tag's do: on a scene, in search, as a Plex label
    row = client.post(f"/api/v1/videos/{analysed}/tags", json={"tag": "Stapler Gag", "start": 1, "end": 7}).json()
    assert row["tag"] == "running-gag" and row["name"] == "stapler GAG" and row["family"] is None
    client.post(f"/api/v1/tags/{row['id']}/keep")
    hits = client.get("/api/v1/search/scenes", params={"tags": "stapler gag"}).json()
    assert hits["total"] == 1 and hits["items"][0]["tags"][0]["name"] == "stapler GAG"
    assert _mine(client)[0]["counts"]["accepted"] == 1
    assert client.post("/api/v1/tags/Stapler%20gag/label", json={"label": True}).json() == {"tag": "running-gag", "label": True}
    assert client.post("/api/v1/collections", json={"name": "Gags", "tags": ["Stapler gag"]}).json()["tags"] == ["running-gag"]

    # a key may read them, only the web page changes them
    key = client.post("/api/v1/keys", json={"name": "App", "scopes": ["read", "review"]}).json()["key"]
    h = {"X-Api-Key": key}
    assert len(client.get("/api/v1/tags", headers=h).json()["mine"]) == 2
    assert client.post("/api/v1/tags/mine", headers=h, json={"name": "X"}).status_code == 403
    assert client.patch("/api/v1/tags/mine/catchphrase", headers=h, json={"name": "X"}).status_code == 403
    assert client.delete("/api/v1/tags/mine/catchphrase", headers=h).status_code == 403


def test_custom_tags_are_validated(client, core) -> None:
    core.store.upsert_title({"id": "show:tvdb:9", "type": "show", "name": "Night Shift", "sort_name": "night shift"})
    core.store.upsert_title({"id": "episode:tvdb:9:s01e01", "type": "episode", "name": "Pilot", "parent_id": "show:tvdb:9",
                             "season": 1, "episode": 1})

    def bad(body: dict, word: str, tag: str | None = None) -> None:
        r = (client.patch(f"/api/v1/tags/mine/{tag}", json=body) if tag
             else client.post("/api/v1/tags/mine", json=body))
        assert r.status_code == 400, (body, r.text)
        assert word in r.json()["detail"], r.json()

    bad({}, "name")
    bad({"name": "   "}, "name")
    # a bundled tag's id or name is taken, whatever the case, and so are Marcarr's own
    bad({"name": "Christmas"}, "already has")
    bad({"name": "christmas"}, "already has")
    bad({"name": "Foot or animal chase"}, "already has")  # the bundled name of "chase"
    bad({"name": "Time Of Day!", "id": "night"}, "already has")
    bad({"name": "Full moon"}, "already has")  # its slug is the bundled id full-moon
    bad({"name": "My filler", "id": "fc:filler"}, "fc:")
    bad({"name": "My thing", "id": "Not A Slug"}, "lowercase")
    bad({"name": "Gag", "family": "jokes"}, "family")
    bad({"name": "Gag", "see": 5}, "cues")
    bad({"name": "Gag", "scope": "movie:tmdb:404"}, "no title")
    bad({"name": "Gag", "scope": "episode:tvdb:9:s01e01"}, "episode")
    bad({"name": "Gag", "scope": 7}, "scope")
    assert _mine(client) == []

    assert client.post("/api/v1/tags/mine", json={"name": "Gag", "family": "Mood", "scope": {"title": "show:tvdb:9"}}).json()["family"] == "mood"
    client.post("/api/v1/tags/mine", json={"name": "Catchphrase"})
    bad({"name": "gag"}, "already a custom tag")
    bad({"name": "Other", "id": "gag"}, "already a custom tag")
    bad({"name": "Catchphrase"}, "already a custom tag", tag="gag")
    bad({"name": "Snow"}, "already has", tag="gag")
    bad({"name": ""}, "name", tag="gag")
    bad({"family": "nope"}, "family", tag="gag")
    bad({"retired": "yes"}, "retired", tag="gag")
    assert [(t["id"], t["name"], t["family"]) for t in _mine(client)] == [("gag", "Gag", "mood"), ("catchphrase", "Catchphrase", None)]
    # a bundled tag wins when a name could mean both
    from marcarr import views

    assert views.tag_id("Snow") == "snow" and views.tag_id("GAG") == "gag" and views.tag_family("gag") == "mood"
    assert views.tag_name("catchphrase") == "Catchphrase" and views.tag_family("catchphrase") is None


def test_deleting_a_custom_tag_in_use_retires_it(client, analysed) -> None:
    client.post("/api/v1/tags/mine", json={"name": "Catchphrase"})
    client.post("/api/v1/tags/mine", json={"name": "Unused"})
    assert client.delete("/api/v1/tags/mine/unused").json() == {"deleted": True, "retired": False, "tag": None}
    assert client.delete("/api/v1/tags/mine/unused").status_code == 404
    row = client.post(f"/api/v1/videos/{analysed}/tags", json={"tag": "catchphrase", "start": 1, "end": 7}).json()

    out = client.delete("/api/v1/tags/mine/catchphrase").json()
    assert out["retired"] and not out["deleted"] and out["tag"]["retired"]
    mine = _mine(client)
    assert [(t["id"], t["retired"]) for t in mine] == [("catchphrase", True)]
    assert mine[0]["counts"]["proposed"] == 1
    # its scenes keep the tag and its name
    kept = client.get(f"/api/v1/videos/{analysed}/tags", params={"status": "all"}).json()["items"]
    assert [(t["id"], t["name"]) for t in kept] == [(row["id"], "Catchphrase")]
    # it can be brought back, and removed for good once nothing uses it
    assert not client.patch("/api/v1/tags/mine/catchphrase", json={"retired": False}).json()["retired"]
    assert client.delete(f"/api/v1/tags/{row['id']}").status_code == 204
    assert client.delete("/api/v1/tags/mine/catchphrase").json()["deleted"]
    assert _mine(client) == []


def test_provider_keys_are_masked_and_kept(client) -> None:
    client.put("/api/v1/settings", json={"ai": {"keys": {"openai": "sk-one", "claude": "sk-two"}}})
    keys = client.get("/api/v1/settings").json()["ai"]["keys"]
    assert keys == {"openai": "••••", "claude": "••••"}
    # the mask keeps a key, "" removes one
    client.put("/api/v1/settings", json={"ai": {"keys": {"openai": "••••", "claude": ""}}})
    from marcarr.routes.common import core

    assert core().cfg.ai.keys == {"openai": "sk-one"}
