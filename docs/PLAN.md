# Marcarr: plan for the first version

## Why

FansCut and Doblarr analyse the same files twice, with two copies of the same
code:

| Step | FansCut (`fanscut/scenes/`) | Doblarr (`doblarr/vision/`) |
|---|---|---|
| Camera cuts | Prompture `detect_shots`, threshold 0.2 | Own ffmpeg pass, threshold 0.32 (missed ~25% of cuts on a real film) |
| Scenes | `index.py`: a scene ends at a cut nobody talks across | `scenes.py`: the same rule, plus manual corrections |
| Faces | `faces.py`: YuNet + SFace against cast photos | `faces.py`, `tracks.py`, `references.py`: YuNet + SFace, anime cascade, DINO, tracks across shots, corrections |
| Cast | `cast.py`: Plex roles, TMDB | `published_cast.py`: AniList, ANN, MAL, Bangumi |
| Subtitles | `subs.py` | `subtitles.py`, `cues.py` |

Marcarr does that work once per file and both apps read the result.

## What Marcarr is, and is not

Marcarr owns **what is in a file**: shots, subtitle lines, scenes, signals,
faces, cast and tags, with a review step for anything a model proposed.

It does not own:

- cuts, posters, cut previews: **FansCut**
- dubbing, voices, story facts (`doblarr/knowledge`), active speaker from
  audio energy: **Doblarr**
- ffmpeg helpers, contact sheets, model calls: **Prompture**
  (`prompture.media.understand.frames`, released in 1.19.2)

## Identity

A path is where a file is today, not what it is. Marcarr takes Doblarr's model
(`doblarr/identity.py`):

- **Title**: provider id when known (`movie:tmdb:…`, `show:tvdb:…`), Plex
  rating key as a hint, never a folder name.
- **Source revision**: sampled hash, size, duration and stream layout. The same
  file at a new path is the same revision; a re-encode or another cut is a new
  one.

Every analysis result hangs off a source revision. Tags and corrections a person
made also hang off it, so re-running a stage never loses them.

## Stages

Each stage is recorded per revision as done, stale (an input changed), failed,
not supported here, off, or not run. A rerun only redoes stale stages.

| Stage | Source to start from | Notes |
|---|---|---|
| `shots` | Prompture `detect_shots` | Threshold 0.2; merge flashes under 0.4 s (Doblarr `MIN_SHOT`) |
| `subs` | FansCut `subs.py` | Sidecar, embedded text track, or a same-length sibling file; image subs fall back to transcription |
| `scenes` | Merge both `index.py` and `vision/scenes.py` | Keep Doblarr's manual add/remove and "uncertain" flag, FansCut's min/max scene length |
| `signals` | FansCut `signals.py` | no-face, close-up, dark, silence, loud…; numbers only, never shown as tags |
| `cast` | FansCut `cast.py` + Doblarr `published_cast.py` | Plex, TMDB, AniList and the other catalogues |
| `faces` | Doblarr `vision/` + FansCut `faces.py` | Doblarr's tracks and corrections; FansCut's cast-photo matching and its SURE threshold |
| `tags` | FansCut `vocab.py`, `tags_v1.json`, `tagger.py`, `label.py` | Read the dialogue, then check on a contact sheet; every AI tag is a proposal until a person accepts it |

Optional stages (faces, tags) need OpenCV or a model key; without them the
stage is "not supported here" and the rest still runs.

## What clients get

- **REST API**: `GET /api/titles/{id}/revisions`, `GET /api/revisions/{id}`
  (all stages), `GET /api/revisions/{id}/tags`, `POST` to propose, accept or
  reject a tag, `POST /api/revisions/{id}/run` to (re)run stages.
- **One JSON document per revision** (`marcarr-analysis/1`) with every stage,
  so an app can cache it.
- **MCP server** (from FansCut's `fanscut mcp`), so an AI client can tag scenes.
- **Webhooks** when a stage finishes, so Doblarr can start without polling.

## How each app uses it

**FansCut** stops analysing. Its scene editor, cut pages and X-Ray read and
write through Marcarr. It gets Doblarr's face tracking for free, which is the
missing piece of X-Ray.

**Doblarr** stops running its own shots, scenes and faces, and gains tags:

| Tag family | Doblarr module | Use |
|---|---|---|
| place | `treatments.py` | Room, distance, outdoors for the dubbed voice |
| weather | `bedpolicy.py` | A planned rain or wind bed is not ducked away |
| mood, beat | `emotion.py` | A second reader next to the voice emotion model |
| people | `vision/association.py` | Only people in the scene can be speaking |
| creature | `reactions.py`, `vocalization.py` | A creature sound is kept, not dubbed |

Both apps keep working without Marcarr during the move: if a Marcarr URL is set
they use it, otherwise their own code, until each stage is moved over.

## Stack

Same shape as Doblarr so it sits in the same Docker setup: Python 3.11,
FastAPI, SQLite, a small React UI for reviewing tags and faces, a CPU image and
a GPU image. Depends on `prompture[media]>=1.19.2`; `opencv-python-headless`
is optional.

## Phases

1. **Skeleton**: server, Docker, config, identity and source revisions, Plex
   library scan.
2. **Index**: `shots`, `subs`, `scenes`, the API and the JSON document.
   FansCut reads its index from Marcarr when a URL is set.
3. **Tags**: `signals`, the tag list, the tagger, the review UI and MCP.
   FansCut's tagger moves here.
4. **Faces and cast**: merge the two face pipelines. FansCut X-Ray uses tracks.
5. **Doblarr**: Doblarr reads shots, scenes and faces from Marcarr, then the
   tag uses in the table above, one module at a time.

## Before starting

- Merge FansCut's scene-tagging branch into `dev`: it is the newest copy of
  most of the code Marcarr starts from.
- Settle Doblarr's `main` vs `dev` gap (dev is 50 commits behind).
- Decide whether version 1 covers episodes too. Doblarr is mostly anime
  episodes, so phase 5 needs them; FansCut only needs films.
