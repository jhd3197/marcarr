# Marcarr: the web UI is built in a Node stage; the app runs on Python 3.11 with ffmpeg.
#
#   docker run -d -p 7470:7470 -v ./config:/config -v /path/to/media:/data:ro ghcr.io/jhd3197/marcarr
#
# /config holds config.yaml and Marcarr's data (database, caches, face models, log).
# The container runs as uid/gid 1000, so a bind-mounted /config must be writable by it:
#   mkdir -p config && chown -R 1000:1000 config
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MARCARR_CONFIG=/config/config.yaml MARCARR_DATA_DIR=/config/data
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY marcarr/ marcarr/
COPY --from=ui /ui/dist/ marcarr/ui/
RUN pip install --no-cache-dir ".[faces,mcp]" \
    # Fail the build, not the first scan, when the app or the UI is not there.
    && python -c "import marcarr.server, cv2; from pathlib import Path; \
assert (Path(marcarr.__file__).parent / 'ui' / 'index.html').is_file(), 'UI missing'"

# Run as a non-root user.
RUN groupadd --gid 1000 marcarr \
    && useradd --uid 1000 --gid marcarr --no-create-home --shell /usr/sbin/nologin marcarr \
    && mkdir -p /config \
    && chown -R marcarr:marcarr /config
USER marcarr

VOLUME /config
EXPOSE 7470
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7470/api/v1/status', timeout=8)" || exit 1
CMD ["marcarr", "--config", "/config/config.yaml", "serve", "--host", "0.0.0.0", "--port", "7470"]
