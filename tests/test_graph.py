"""The character graph: who is seen with whom, stopped at a scene."""

from __future__ import annotations

from urllib.parse import quote

from marcarr import graph

CAST = {"ann": {"character": "Ann", "actor": "A. Actor", "photo": None},
        "bo": {"character": "Bo", "actor": "B. Actor", "photo": "/p/bo"}}


def scene(n, start, end, seen=(), mentioned=(), speakers=()):
    return {"n": n, "start": start, "end": end, "seen": list(seen), "people": list(seen),
            "mentioned": list(mentioned), "speakers": list(speakers)}


SCENES = [
    scene(1, 0, 10, seen=["ann", "bo"]),
    scene(2, 10, 30, seen=["ann"], mentioned=["cy"]),
    scene(3, 30, 40, seen=["bo"]),
    scene(4, 100, 120, seen=["ann", "bo", "cy"]),
]


def test_pairs_count_shared_scenes_only() -> None:
    g = graph.build(SCENES, CAST)
    pairs = {(e["a"], e["b"]): e for e in g["pairs"]}
    assert pairs[("ann", "bo")]["scenes"] == [1, 4]
    assert pairs[("ann", "bo")]["seconds"] == 30
    assert pairs[("ann", "cy")]["scenes"] == [4]  # being named in scene 2 drew no link
    assert g["pairs"][0]["a"] == "ann"  # strongest first


def test_people_carry_screen_time_first_sighting_and_gap() -> None:
    g = graph.build(SCENES, CAST)
    ann = next(p for p in g["people"] if p["id"] == "ann")
    assert ann["name"] == "Ann" and ann["seconds"] == 50
    assert ann["scenes"] == [1, 2, 4]
    assert ann["first"] == {"n": 1, "start": 0}
    assert ann["gap"] == {"from": 2, "to": 4, "start": 30, "end": 100, "seconds": 70}
    assert ann["partners"][0] == {"id": "bo", "scenes": 2}
    cy = next(p for p in g["people"] if p["id"] == "cy")
    assert cy["name"] == "cy" and cy["named"] == 1
    assert g["people"][0]["id"] == "ann"  # most screen time first


def test_touching_scenes_are_not_a_gap() -> None:
    g = graph.build([scene(1, 0, 10, seen=["ann"]), scene(2, 10, 20, seen=["ann"])], CAST)
    assert g["people"][0]["gap"] is None


def test_through_hides_what_comes_later() -> None:
    g = graph.build(SCENES, CAST, through=2)
    assert g["through"] == 2 and g["scenes"] == 2
    assert {e["a"] + "-" + e["b"] for e in g["pairs"]} == {"ann-bo"}
    cy = next(p for p in g["people"] if p["id"] == "cy")
    assert cy["scenes"] == [] and cy["first"] is None  # only named so far
    assert graph.build(SCENES, CAST, through=99)["through"] is None  # past the end: the whole story


def test_graph_endpoint(client, core, analysed) -> None:
    core.store.add_tag(analysed, "movie:tmdb:1", "snow", 0, 24, people=["mira-vale", "tom-reed"],
                       status="accepted")
    tid = quote("movie:tmdb:1")
    g = client.get(f"/api/v1/titles/{tid}/graph").json()
    assert g["video"] == analysed
    assert g["pairs"][0]["a"] == "mira-vale" and g["pairs"][0]["b"] == "tom-reed"
    assert {p["name"] for p in g["people"]} == {"Mira Vale", "Tom Reed"}
    first = client.get(f"/api/v1/titles/{tid}/graph?through=1").json()
    assert first["scenes"] == 1
    assert client.get(f"/api/v1/titles/{tid}/graph?through=x").status_code == 400
    assert client.get(f"/api/v1/titles/{tid}/graph?video=nope").status_code == 404


def test_who_is_with_tool(core, analysed) -> None:
    from fastapi.testclient import TestClient

    from marcarr import mcp_server
    from marcarr.server import create_app

    core.store.add_tag(analysed, "movie:tmdb:1", "snow", 0, 24, people=["mira-vale", "tom-reed"],
                       status="accepted")
    mcp_server.use_client(TestClient(create_app(core), base_url="http://testserver/api/v1"))
    try:
        text = mcp_server.who_is_with("movie:tmdb:1")
        assert "Mira Vale + Tom Reed: scenes 1" in text
        one = mcp_server.who_is_with("movie:tmdb:1", person="tom-reed", through=1)
        assert one.startswith("Tom Reed: seen in 1 scenes, first in scene 1")
        assert "not seen" in mcp_server.who_is_with("movie:tmdb:1", person="nobody")
    finally:
        mcp_server.use_client(None)  # type: ignore[arg-type]
