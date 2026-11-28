#!/usr/bin/env bash
# Start a Marcarr image and check that it serves the API and the UI.
#   scripts/docker-smoke.sh marcarr:ci
set -euo pipefail
image="${1:?usage: docker-smoke.sh <image>}"
name="marcarr-smoke-$$"
cfg="$(mktemp -d)"
chmod 777 "$cfg"   # the container runs as uid 1000, whatever the runner's user is
cleanup() { docker logs "$name" 2>&1 | tail -n 20 || true; docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$cfg" 2>/dev/null || true; }
trap cleanup EXIT

docker run -d --name "$name" -p 127.0.0.1::7470 -v "$cfg:/config" "$image" >/dev/null
port="$(docker port "$name" 7470/tcp | head -n1 | sed 's/.*://')"

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$port/api/v1/status" >/tmp/marcarr-status.json 2>/dev/null; then break; fi
  sleep 1
done
grep -q '"version"' /tmp/marcarr-status.json || { echo "the API did not come up" >&2; exit 1; }
curl -fsS "http://127.0.0.1:$port/" | grep -qi "<div id=\"root\"" || { echo "the web UI is not served" >&2; exit 1; }
docker exec "$name" ffmpeg -version >/dev/null
docker exec "$name" ffprobe -version >/dev/null
test -f "$cfg/config.yaml" || { echo "config.yaml was not created in /config" >&2; exit 1; }
echo "ok: $(cat /tmp/marcarr-status.json)"
