"""The scene brief: one text for Copy brief and the MCP get_scene tool."""

from __future__ import annotations

from marcarr.brief import evidence_text, scene_brief

DETAIL = {
    "n": 3, "start": 62, "end": 95.5, "video": "v1", "edition": "Extended",
    "title": {"id": "movie:1", "name": "The Winter House", "year": 2019},
    "summary": "Presents by the tree", "place_name": "Winter House › Great Hall",
    "seen": ["mira-vale"], "people": ["mira-vale"], "speakers": ["tom-reed"], "mentioned": ["june-holt"],
    "cast": [{"id": "mira-vale", "character": "Mira Vale", "actor": "Ada Lane"},
             {"id": "tom-reed", "character": "Tom Reed", "actor": "Ben Ortiz"}],
    "all_tags": [
        {"id": "tag_1", "name": "Christmas", "status": "proposed", "source": "ai",
         "evidence": {"heard": [{"text": "Merry Christmas", "at": 64}], "seen": ["a tree"]}},
        {"id": "tag_2", "name": "Snow", "status": "accepted", "source": "person", "evidence": {"heard": [], "seen": []}},
        {"id": "tag_3", "name": "Rain", "status": "rejected", "source": "ai", "evidence": {"heard": [], "seen": []}},
    ],
    "lines": [{"start": 64, "end": 66, "text": "Merry Christmas, everyone!"}],
}


def test_brief_for_a_person() -> None:
    text = scene_brief(DETAIL, link="http://m/titles/movie%3A1?t=62")
    assert text.splitlines()[0] == "The Winter House (2019), Extended: scene 3, 1:02 to 1:35"
    assert "Seen: Mira Vale" in text
    assert "Heard speaking, not seen: Tom Reed" in text
    assert "Only named: june-holt" in text
    assert "  Snow (kept)" in text  # kept tags first
    assert "  Christmas (to review): heard: Merry Christmas (1:04) | seen: a tree" in text
    assert "Rain" not in text  # dropped tags are left out
    assert "  1:04 Merry Christmas, everyone!" in text
    assert text.endswith("Link: http://m/titles/movie%3A1?t=62")
    assert "tag_1" not in text


def test_brief_for_an_app_carries_ids() -> None:
    text = scene_brief(DETAIL, ids=True)
    assert "video: v1" in text
    assert "Seen: Mira Vale (mira-vale)" in text
    assert "Christmas (to review, tag_1, ai)" in text
    assert "Rain (dropped" in text


def test_evidence_text() -> None:
    assert evidence_text("snow") == "snow"
    assert evidence_text({"text": "snow", "at": 3725}) == "snow (1:02:05)"
    assert evidence_text({"text": "snow", "at": None}) == "snow"


def test_brief_endpoint(client, analysed) -> None:
    r = client.get(f"/api/v1/videos/{analysed}/scenes/1/brief", params={"link": "http://x/t?t=0"})
    assert r.status_code == 200
    text = r.json()["text"]
    assert text.startswith("Test Film (2020)")
    assert "Merry Christmas" in text  # the dialogue
    assert text.endswith("Link: http://x/t?t=0")
