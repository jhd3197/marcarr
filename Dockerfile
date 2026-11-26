# Marcarr: the UI is built in a Node stage, the app runs on Python 3.11 with ffmpeg.
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
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
RUN pip install --no-cache-dir ".[faces,mcp]"
VOLUME /config
EXPOSE 7470
CMD ["marcarr", "--config", "/config/config.yaml", "serve", "--host", "0.0.0.0", "--port", "7470"]
