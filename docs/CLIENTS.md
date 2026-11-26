# Connecting FansCut and Doblarr

Marcarr runs at `http://<host>:7470`. Every call is under `/api/v1`. The full
reference is the API page in the app (and `/api/v1/docs` for the OpenAPI
view); the types are in `ui/src/api/types.ts`.

## 1. Give each app a key

Settings > Connected apps > Add an app. Pick its scopes:

| App | Scopes |
|---|---|
| FansCut | read, propose, run |
| Doblarr | read, propose, run |
| MCP clients | read, propose |

Send it as `X-Api-Key: mk_...`. A key never reaches Settings, and a tag an app
adds is always a proposal: a person keeps or drops it.

## 2. Find the video for a file

Titles are named by provider id, never by path: `movie:tmdb:671`,
`show:tvdb:79168`, `episode:tvdb:79168:s01e02` (fallback `plex:<ratingKey>`).

```
GET /api/v1/titles?q=sorcerer          -> items[].id, items[].video_id
GET /api/v1/titles/movie:tmdb:671      -> video.id, video.steps
```

A **video** is one source revision (sampled hash + size + duration + stream
layout). The same file moved is the same video; a re-encode is a new one.
Cache by video id.

## 3. Read what is in it

| Need | Call |
|---|---|
| Everything at once (cache it) | `GET /videos/{id}/analysis` (`marcarr-analysis/1`) |
| Camera cuts | `GET /videos/{id}/shots?from=&to=` |
| Subtitle lines | `GET /videos/{id}/lines?from=&to=` |
| Scenes with tags, people, place | `GET /videos/{id}/scenes?from=&to=&tag=` |
| Who is seen, heard or named | `GET /videos/{id}/presence?person=&from=&to=` |
| Measured signals | `GET /videos/{id}/signals?signal=dark` |
| Faces | `GET /videos/{id}/faces?person=&confirmed=true` |
| What is on screen at t | `GET /videos/{id}/at/{seconds}` |
| Scenes across the library | `GET /search/scenes?tags=christmas,snow&person=&q=` |

Step states per video: `done`, `rerun` (an input changed), `failed`, `run`,
`queued`, `notrun`, `none` (not supported here), `off`.

## 4. Ask for work and hear when it is done

```
POST /api/v1/videos/{id}/run   {"steps": ["shots", "subtitles", "scenes"]}
```

Then add a webhook (Settings > Notifications, or `POST /api/v1/webhooks`)
for `step.finished` / `video.analysed`. Each call is signed:
`X-Marcarr-Signature: sha256=<HMAC of the body with the webhook's secret>`.

## 5. Propose tags

```
POST /api/v1/videos/{id}/tags
{"tag": "Rain", "start": 5332.0, "end": 5390.0,
 "evidence": {"heard": [{"text": "rain", "at": 5340.2}], "seen": ["rain on the window"]},
 "people": ["ron-weasley"], "mentioned": ["hermione-granger"]}
```

`people` are the characters seen on screen; `mentioned` the ones only named in
the dialogue. An evidence item is a short text, or `{"text", "at"}` with the
second of the video that shows it, so a reviewer can jump straight there.

The source is the key's app name (`doblarr`). Kept and dropped tags fire
`tag.kept` / `tag.dropped`.

## 6. Report who speaks or is named

```
POST /api/v1/videos/{id}/presence
{"person": "ron-weasley", "how": "speaker", "start": 5340.0, "end": 5344.5, "at": 5341.0}
```

`how` is `seen`, `mentioned` or `speaker`. A scene then lists the person under
`seen`, `speakers` (heard but not seen) or `mentioned` (only named); `people`
stays the list of those seen. A person keeps or drops it with
`POST /presence/{id}/keep|drop`.

## Moving each app, step by step

**FansCut** (`fanscut/scenes/`): set `marcarr.url` + key. Then

1. `index.build` -> `GET /videos/{id}/analysis` (shots, lines, scenes).
2. `signals.py` -> `/signals`.
3. The tagger and the scene editor -> `/videos/{id}/tags`, `/tags/{id}/keep|drop`,
   `PATCH /videos/{id}/scenes/{n}` for edges. FansCut's own tags (`fc:`) stay in
   FansCut.
4. X-Ray -> `/at/{seconds}` and `/faces` (Marcarr's face tracks replace
   `faces.py`).

**Doblarr** (`doblarr/vision/`): set the URL + key, then shots, scenes and
faces from Marcarr, then the tag uses in docs/PLAN.md (place -> treatments,
weather -> bed policy, mood/beat -> emotion, people -> association,
creature -> reactions), one module at a time.

Until a stage moves, each app keeps its own code: if no Marcarr URL is set it
works as before.
