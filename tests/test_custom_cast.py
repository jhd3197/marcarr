"""People added by hand: the cast of a home video, which Plex and TMDB know nothing of."""

from __future__ import annotations

from urllib.parse import quote

import pytest

from marcarr.pipeline import StepSkip

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
HOME = "plex:900"


@pytest.fixture()
def home(core) -> str:
    core.store.upsert_title({"id": HOME, "type": "movie", "name": "Our Wedding",
                             "sort_name": "our wedding", "year": 2024})
    return HOME


def _cast(client, tid: str) -> list[dict]:
    return client.get("/api/v1/titles/" + quote(tid)).json()["cast"]


def test_add_person_and_photo(client, core, home) -> None:
    url = f"/api/v1/titles/{quote(home)}/cast"
    assert client.post(url, json={"name": "  "}).status_code == 400
    p = client.post(url, json={"name": "María José"}).json()
    assert p == {"id": "maria-jose", "actor": "", "character": "María José", "photo": None}
    client.post(url, json={"name": "María José"})  # adding twice changes nothing
    assert [(c["id"], c["manual"], c["photo"]) for c in _cast(client, home)] == [("maria-jose", True, None)]

    photo = "/api/v1/people/maria-jose/photo"
    assert client.get(photo).status_code == 404
    assert client.put(photo, content=b"not an image").status_code == 400
    assert client.put("/api/v1/people/nobody/photo", content=JPEG).status_code == 404
    assert client.put(photo, content=JPEG).json()["photo"] == photo
    got = client.get(photo)
    assert got.content == JPEG and got.headers["content-type"] == "image/jpeg"
    assert _cast(client, home)[0]["photo"] == photo
    # a new photo of another type replaces the old file
    client.put(photo, content=PNG)
    got = client.get(photo)
    assert got.content == PNG and got.headers["content-type"] == "image/png"
    assert [f.name for f in (core.data_dir / "people").iterdir()] == ["maria-jose.png"]


def test_remove_person(client, home) -> None:
    url = f"/api/v1/titles/{quote(home)}/cast"
    client.post(url, json={"name": "Maria"})
    client.post(url, json={"name": "Juan"})
    assert client.delete(url + "/maria").status_code == 204
    assert [c["id"] for c in _cast(client, home)] == ["juan"]
    assert client.delete(url + "/maria").status_code == 404
    # the person stays (their scenes in other titles keep their name)
    assert client.get("/api/v1/people/maria").status_code == 200


def test_catalogue_cast_keeps_people_added_by_hand(client, core, home) -> None:
    client.post(f"/api/v1/titles/{quote(home)}/cast", json={"name": "Maria"})
    client.put("/api/v1/people/maria/photo", content=JPEG)
    core.store.save_cast(home, "plex", [
        {"name": "Ada Lane", "character": "Mira Vale", "photo": "/library/1/thumb", "order": 0},
        {"name": "Someone", "character": "Maria", "photo": "/library/2/thumb", "order": 1}])
    cast = {c["person"]: c for c in core.store.cast(home)}
    assert list(cast) == ["mira-vale", "maria"]
    assert cast["maria"]["photo"] == "local:maria.jpg"  # the uploaded photo wins
    core.store.add_cast_member(home, "Juan")
    core.store.save_cast(home, "plex", [{"name": "Ada Lane", "character": "Mira Vale"}])
    assert [c["person"] for c in core.store.cast(home)] == ["mira-vale", "juan"]


def test_cast_step_and_face_references(core, home, film, monkeypatch) -> None:
    vid = core.library.add_file(home, str(film))
    with pytest.raises(StepSkip):
        core.pipeline.step_cast(vid, lambda *a: None, None)
    core.store.add_cast_member(home, "Maria")
    core.store.add_cast_member(home, "Juan")  # no photo: no reference face
    assert core.pipeline.step_cast(vid, lambda *a: None, None) == "2 people you added"

    class Engine:
        def reference(self, photo: bytes) -> int:
            return len(photo)

    monkeypatch.setattr(core.pipeline, "face_engine", lambda: Engine())
    assert core.pipeline.face_refs(home) == {}
    folder = core.data_dir / "people"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "maria.jpg").write_bytes(JPEG)
    core.store.set_person_photo("maria", "local:maria.jpg")
    core.pipeline.forget_refs()
    refs = core.pipeline.face_refs(home)
    assert list(refs) == ["maria"] and refs["maria"]["feature"] == len(JPEG)
