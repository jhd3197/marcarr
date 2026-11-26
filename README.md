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

## Running it

```
python -m venv .venv && .venv/Scripts/pip install -e ".[faces,mcp,dev]"   # or bin/pip
cd ui && npm install && npm run build && cd ..
marcarr serve                      # http://127.0.0.1:7470, first run opens the setup
```

Or `docker compose up -d --build`. Settings are in `config.yaml`
(see `config.example.yaml`); the Settings page edits it.

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
