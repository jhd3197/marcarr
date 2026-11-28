# Marcarr

*marcar*: to mark.

Marcarr is a self-hosted service that runs next to Plex. It looks at each film
or episode once and records what is in it: camera cuts, subtitle lines, scenes,
measured signals, faces, cast and tags ("christmas", "rain", "a cave"). Other
apps ask Marcarr instead of analysing the file again.

Its first two clients are [FansCut](https://github.com/jhd3197/FansCut), which
builds cuts from tagged scenes, and [Doblarr](https://github.com/jhd3197/Doblarr),
which dubs and needs to know where a line is said and who is on screen.

## On its own

You don't need FansCut or Doblarr to use Marcarr. Point it at your Plex server
and it gives you:

- **Scene search across your library**: every rain scene, every Christmas
  dinner, every scene with a given actor, with the film and the time it starts.
- **Plex labels and collections**: films with a tag get a label (`marcarr:christmas`),
  so a Kometa or smart-collection rule can build a "Christmas scenes" row.
- **A review page**: accept, fix or reject what the AI proposed, scene by scene.
- **Tools for AI clients**: an MCP server, so an assistant can ask "where does
  this happen?" or tag a scene itself.
- **An API and one JSON file per video**: for any other tool that wants to know
  what is in a file without decoding it.

## Install

Marcarr needs **ffmpeg** (the Docker image and the Windows bundle include it) and, for
analysis, access to the same video files Plex sees. It listens on port **7470**; the first
run opens a setup page for Plex.

### Docker (Linux, macOS, Windows, NAS)

```
mkdir -p config && chown -R 1000:1000 config      # the container runs as uid 1000
docker run -d --name marcarr -p 7470:7470 \
  -v ./config:/config \
  -v /path/to/media:/data:ro \
  ghcr.io/jhd3197/marcarr:latest
```

Or with Compose: download [docker-compose.yml](docker-compose.yml), edit the media path and
`MARCARR_PLEX_URL`, then `docker compose up -d`. Open http://localhost:7470.

- `/config` holds `config.yaml` and Marcarr's data (database, caches, face models, log).
- Mount your media where Plex sees it (the compose file uses `/data`), or map Plex's paths to
  the container's in Settings > Plex.
- Secrets can come from the environment: `MARCARR_PLEX_TOKEN`, `MARCARR_AI_API_KEY`,
  `MARCARR_TMDB_API_KEY` (each also as `..._FILE` for Docker secrets).
- Images are `linux/amd64` and `linux/arm64`. Tags: `latest`, `0.1.2` and `0.1` for each release.
  To build it yourself: `docker compose up -d --build`.

### Windows (portable)

Download `Marcarr-<version>-windows-x64.zip` from the
[latest release](https://github.com/jhd3197/Marcarr/releases/latest), unzip it, and
double-click `Marcarr.bat`. Python and ffmpeg are inside; your settings and data stay in the
`config` folder next to it. No installer, nothing to uninstall. (There is a `.sha256` file next
to the zip to check the download.)

### pip / pipx (any OS)

```
pipx install "marcarr[faces,mcp]"        # or: pip install "marcarr[faces,mcp]"
marcarr serve                            # http://127.0.0.1:7470
```

Install ffmpeg first (`winget install Gyan.FFmpeg`, `brew install ffmpeg`, `apt install ffmpeg`).
`faces` adds who-is-on-screen (OpenCV); `mcp` adds `marcarr mcp`. Config is `./config.yaml`, or
the path in `$MARCARR_CONFIG`.

### From source

```
python -m venv .venv && .venv/Scripts/pip install -e ".[faces,mcp,dev]"   # or bin/pip
cd ui && npm install && npm run build && cd ..
marcarr serve                      # http://127.0.0.1:7470
```

Settings are in `config.yaml` (see `config.example.yaml`); the Settings page edits it.

Other commands: `marcarr scan` (read Plex once), `marcarr analyse <file>`
(one file, no Plex), `marcarr mcp` (MCP server on stdio), `marcarr status`.

For UI work without Plex: `python scripts/seed_demo.py --config demo/config.yaml video.mp4`,
then `marcarr --config demo/config.yaml serve`, and `npm run dev` in `ui/`
(proxies `/api` to port 7470).

## Layout

- `marcarr/stages/`: the analysis code taken from FansCut (subtitles, scenes,
  signals, cast, faces, the tagger and its prompts, the 130-tag list).
- `marcarr/pipeline.py`: the seven steps per video, states, staleness, cost.
- `marcarr/routes/`: the v1 API. `ui/src/api/types.ts` is the contract.
- `ui/`: React + Vite, built from the design in `docs/design/`.

Connecting FansCut and Doblarr: [docs/CLIENTS.md](docs/CLIENTS.md).
The plan: [docs/PLAN.md](docs/PLAN.md).

## Releases

Everything is automatic from a GitHub release. Bump `__version__` in `marcarr/__init__.py`,
merge `dev` into `main`, then publish a release tagged `v<version>`:

- [publish.yml](.github/workflows/publish.yml) uploads the package to PyPI (needs the
  `PYPI_TOKEN` secret).
- [release.yml](.github/workflows/release.yml) pushes the Docker images to GHCR
  (`ghcr.io/jhd3197/marcarr`) and attaches the Windows zip to the release. To also publish to
  Docker Hub, add the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets. GHCR creates the
  package as private the first time: set it to Public in the package settings.

[ci.yml](.github/workflows/ci.yml) runs on every pull request and on pushes to `dev` and
`main`: ruff and pytest (Linux Python 3.11 and 3.12, Windows 3.12), the web UI typecheck, tests
and build, a Docker build with a start-up check, and a full build and start-up check of the
Windows bundle.
