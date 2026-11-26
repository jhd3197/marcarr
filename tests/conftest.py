from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from marcarr.config import Config
from marcarr.core import Core
from marcarr.server import create_app

SRT = """1
00:00:02,000 --> 00:00:05,000
Merry Christmas, everyone!

2
00:00:08,000 --> 00:00:11,000
Look at the snow outside.

3
00:00:14,000 --> 00:00:17,000
We have to catch the train.
"""


@pytest.fixture(scope="session")
def film(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 24-second video with three camera cuts' worth of shots and a sidecar SRT."""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is not installed")
    d = tmp_path_factory.mktemp("media")
    out = d / "film.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12:duration=8",
         "-f", "lavfi", "-i", "smptebars=size=320x180:rate=12:duration=8",
         "-f", "lavfi", "-i", "color=c=green:size=320x180:rate=12:duration=8",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=24",
         "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
         "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-preset", "ultrafast",
         "-c:a", "aac", "-shortest", str(out)],
        check=True, timeout=120)
    (d / "film.en.srt").write_text(SRT, encoding="utf-8")
    return out


@pytest.fixture()
def core(tmp_path: Path) -> Core:
    cfg = Config.model_validate({"server": {"data_dir": str(tmp_path / "data")}, "setup_done": True})
    c = Core(cfg, tmp_path / "config.yaml", start_worker=False)
    yield c
    c.close()


@pytest.fixture()
def client(core: Core) -> TestClient:
    return TestClient(create_app(core))


@pytest.fixture()
def analysed(core: Core, film: Path) -> str:
    """The test film registered as a title and run through the steps that need no AI."""
    core.store.upsert_title({"id": "movie:tmdb:1", "type": "movie", "name": "Test Film",
                             "sort_name": "test film", "year": 2020, "tmdb_id": 1})
    vid = core.library.add_file("movie:tmdb:1", str(film))
    core.pipeline.submit(vid)
    core.worker.run_pending("heavy")
    core.store.save_cast("movie:tmdb:1", "test", [
        {"name": "Ada Lane", "character": "Mira Vale", "photo": "", "order": 0},
        {"name": "Ben Ortiz", "character": "Tom Reed", "photo": "", "order": 1}])
    return vid
