"""Fill a fresh data folder with one analysed video and some review work, for
working on the UI without Plex or an AI key.

    python scripts/seed_demo.py --config demo/config.yaml path/to/video.mp4

It runs the steps that need neither (shots, subtitles, scenes, signals), then
adds a made-up cast, a few proposed and kept tags, faces and named places.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from marcarr import config as cfgmod
from marcarr.core import Core

CAST = [
    ("Ada Lane", "Mira Vale"), ("Ben Ortiz", "Tom Reed"), ("Cleo Park", "June Holt"),
    ("Dev Rao", "The Keeper"),
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("video")
    args = p.parse_args()
    cfg_path = Path(args.config)
    cfg = cfgmod.load(cfg_path)
    if not cfg_path.is_file():
        cfgmod.save(cfg, cfg_path)
    core = Core(cfg, cfg_path, start_worker=False)
    s = core.store
    tid = "local:demo-film"
    s.upsert_title({"id": tid, "type": "movie", "name": "The Winter House", "sort_name": "winter house",
                    "year": 2019, "collection": "Winter House", "summary": "A demo title.",
                    "file": args.video})
    vid = core.library.add_file(tid, args.video)
    core.pipeline.submit(vid, ["shots", "subtitles", "scenes", "signals"])
    core.worker.run_pending("heavy")
    people = s.save_cast(tid, "demo", [{"name": a, "character": c, "photo": "", "order": i}
                                       for i, (a, c) in enumerate(CAST)])
    pid = [x["person"] for x in people]
    scenes = (s.result(vid, "scenes") or {}).get("scenes") or []
    rows = [
        ("christmas", "proposed", 0.62, {"heard": ["Merry Christmas"], "seen": ["Christmas tree", "wrapped presents"]},
         "Mira opens presents by the tree while Tom watches", [pid[0], pid[1]]),
        ("snow", "accepted", 0.91, {"heard": ["snow"], "seen": ["snow at the windows"]},
         "Snow falls past the windows", [pid[0]]),
        ("happy", "proposed", 0.55, {"heard": [], "seen": ["smiles"]}, "", [pid[0], pid[1]]),
        ("train", "proposed", 0.7, {"heard": ["train"], "seen": ["a station platform"]},
         "June and Tom hurry to catch the train", [pid[1], pid[2]]),
        ("castle", "accepted", 0.88, {"heard": ["castle"], "seen": ["towers", "stone walls"]},
         "The castle comes into view", [pid[2], pid[3]]),
        ("mysterious", "proposed", 0.48, {"heard": [], "seen": ["fog", "a dark hall"]}, "", [pid[3]]),
    ]
    for i, (tag, status, conf, ev, summary, ppl) in enumerate(rows):
        sc = scenes[min(i // 2, len(scenes) - 1)]
        s.add_tag(vid, tid, tag, sc["start"], sc["end"], status=status, source="ai:demo/model",
                  confidence=conf, people=ppl, evidence=ev, summary=summary)
    s.add_tag(vid, tid, "rain", scenes[0]["start"], scenes[0]["end"], status="proposed", source="doblarr",
              confidence=None, evidence={"heard": [], "seen": ["rain on glass"]})
    faces = []
    for k, sc in enumerate(scenes):
        for j, person in enumerate(pid[:2] if k < 2 else pid[2:]):
            faces.append({"person": person, "at": round(sc["start"] + 2 + j * 3, 2),
                          "score": 0.52 if j else 0.36, "box": [0.3 + j * 0.25, 0.25, 0.18, 0.32],
                          "confirmed": 1 if j else None})
    s.replace_faces(vid, faces)
    top = s.add_place("Winter House", None, "Winter House", ["castle"])
    hall = s.add_place("Great Hall", top["id"], "Winter House", ["castle"])
    s.add_place("Kitchen", top["id"], "Winter House", ["kitchen"])
    s.set_place_scene(vid, scenes[-1]["start"], scenes[-1]["end"], hall["id"])
    core.save_config(cfgmod.merge_update(core.cfg, {"setup_done": True}))
    core.close()
    print(f"demo video {vid} with {len(scenes)} scenes")


if __name__ == "__main__":
    main()
