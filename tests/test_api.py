"""The v1 API as the UI and other apps use it."""

from __future__ import annotations

from urllib.parse import quote


def test_empty_install(client) -> None:
    assert client.get("/api/v1/status").json()["review"] == 0
    assert client.get("/api/v1/titles").json()["total"] == 0
    tags = client.get("/api/v1/tags").json()
    assert sum(len(f["tags"]) for f in tags["families"]) == 130


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
