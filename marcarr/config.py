"""config.yaml: schema, loading, saving, and the settings API's view of it.

Everything has a default, so a missing file still boots. Secrets (Plex token,
AI key, TMDB key) may come from the environment instead (ENV_FIELDS); the
settings API masks them and keeps the stored value when the mask comes back.
The Settings page edits this file through GET/PUT /api/v1/settings.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from .errors import ConfigError

MASK = "••••"

ENV_FIELDS = {
    "MARCARR_PLEX_URL": "plex.url",
    "MARCARR_PLEX_TOKEN": "plex.token",
    "MARCARR_AI_API_KEY": "ai.api_key",
    "MARCARR_TMDB_API_KEY": "catalogues.tmdb_api_key",
    "MARCARR_DATA_DIR": "server.data_dir",
}

STEPS = ("shots", "subtitles", "scenes", "signals", "cast", "faces", "tags")
FAMILIES = ("occasion", "weather", "time", "place", "action", "beat", "people", "mood",
            "creature", "element", "content")


def Secret(default: str = "") -> Any:  # noqa: N802 - reads like a type in the models
    return Field(default=default, json_schema_extra={"secret": True})


class PathMap(BaseModel):
    # Plex sees /data/movies, Marcarr sees /mnt/movies: from -> to
    from_: str = Field(default="", alias="from")
    to: str = ""

    model_config = {"populate_by_name": True}


class ServerCfg(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7470
    data_dir: str = "data"
    # False: the web UI and anyone on the network may call the API without a key
    # (a key, when sent, still limits what the caller may do). True: every API
    # call from outside this machine needs a key.
    require_key: bool = False
    public_url: str = ""  # how other apps reach Marcarr, for links in webhooks


class PlexCfg(BaseModel):
    url: str = ""
    token: str = Secret()
    libraries: list[str] = Field(default_factory=list)  # section keys Marcarr looks at
    path_map: list[PathMap] = Field(default_factory=list)
    timeout: float = 15.0


class LabelsCfg(BaseModel):
    write: bool = False  # write marcarr:<tag> labels to Plex
    prefix: str = "marcarr:"
    tags: list[str] = Field(default_factory=lambda: ["christmas", "halloween", "snow", "rain"])


class AICfg(BaseModel):
    enabled: bool = False
    model: str = ""  # text model, a Prompture model string
    vision_model: str = ""  # looks at contact sheets; empty = model
    base_url: str = ""
    api_key: str = Secret()  # used when keys has none for the model's provider
    # One key per Prompture provider ("openai", "claude", "google"...), so the text and
    # the vision model may come from different providers. Masked like any secret.
    keys: dict[str, str] = Field(default_factory=dict)
    # How hard a reasoning model thinks (gpt-5, o-series, Claude with thinking).
    # Tagging reads dialogue and looks at frames: low is enough and much cheaper.
    effort: Literal["low", "medium", "high"] = "low"
    timeout: int = 120
    monthly_limit: float = 10.0  # dollars; the tags step stops when this month passes it
    auto_accept: float = Field(default=1.0, ge=0, le=1)  # AI tags this sure are kept at once


class TagsCfg(BaseModel):
    families_off: list[str] = Field(default_factory=list)
    search_closely: list[str] = Field(default_factory=lambda: ["christmas", "halloween"])

    @field_validator("families_off")
    @classmethod
    def _families(cls, v: list[str]) -> list[str]:
        bad = [f for f in v if f not in FAMILIES]
        if bad:
            raise ValueError(f"unknown tag family: {', '.join(bad)}")
        return list(dict.fromkeys(v))


class FacesCfg(BaseModel):
    enabled: bool = True
    sure: float = 0.45  # SFace cosine score that counts as the person without asking
    maybe: float = 0.30  # below this a face stays unknown
    per_scene: int = 3  # frames looked at per scene


class GeneralCfg(BaseModel):
    theme: Literal["dark", "light", "system"] = "dark"
    language: Literal["en", "es"] = "en"
    clock: Literal["24h", "12h"] = "24h"


class AnalysisCfg(BaseModel):
    steps: dict[str, bool] = Field(default_factory=lambda: dict.fromkeys(STEPS, True))
    at_once: Literal[1, 2, 4] = 1  # videos analysed at the same time
    window_start: str = ""  # "01:00": only start work between these times ("" = any time)
    window_end: str = ""
    on_new: bool = True  # analyse what Plex adds
    transcribe: bool = False  # no text subtitles: transcribe the audio (slow)
    language: str = "en"  # subtitle language to prefer

    @field_validator("steps")
    @classmethod
    def _steps(cls, v: dict[str, bool]) -> dict[str, bool]:
        return {s: bool(v.get(s, True)) for s in STEPS}


class CataloguesCfg(BaseModel):
    tmdb_api_key: str = Secret()


class FFmpegCfg(BaseModel):
    binary: str = "ffmpeg"
    probe_binary: str = "ffprobe"


class Config(BaseModel):
    server: ServerCfg = Field(default_factory=ServerCfg)
    plex: PlexCfg = Field(default_factory=PlexCfg)
    labels: LabelsCfg = Field(default_factory=LabelsCfg)
    ai: AICfg = Field(default_factory=AICfg)
    tags: TagsCfg = Field(default_factory=TagsCfg)
    faces: FacesCfg = Field(default_factory=FacesCfg)
    general: GeneralCfg = Field(default_factory=GeneralCfg)
    analysis: AnalysisCfg = Field(default_factory=AnalysisCfg)
    catalogues: CataloguesCfg = Field(default_factory=CataloguesCfg)
    ffmpeg: FFmpegCfg = Field(default_factory=FFmpegCfg)
    setup_done: bool = False

    @property
    def data_dir(self) -> Path:
        return Path(self.server.data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "marcarr.db"


def default_path() -> Path:
    env = os.environ.get("MARCARR_CONFIG")
    if env:
        return Path(env)
    for p in (Path("config.yaml"), Path("/config/config.yaml")):
        if p.is_file():
            return p
    return Path("config.yaml")


def env_overrides() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, path in ENV_FIELDS.items():
        val = os.environ.get(name, "").strip()
        file = os.environ.get(f"{name}_FILE", "").strip()
        if not val and file:
            try:
                val = Path(file).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise ConfigError(f"{name}_FILE: cannot read {file}: {exc.strerror}") from exc
        if val:
            out[path] = val
    return out


def _dig(d: dict[str, Any], path: str) -> tuple[dict[str, Any], str]:
    *parents, leaf = path.split(".")
    for k in parents:
        d = d.setdefault(k, {})
    return d, leaf


def parse(raw: dict[str, Any] | None) -> Config:
    try:
        return Config.model_validate(raw or {})
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def _read_raw(p: Path) -> dict[str, Any]:
    if not p.is_file():
        return {}
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark else ""
        raise ConfigError(f"{p}: invalid YAML{where}") from exc
    if raw is not None and not isinstance(raw, dict):
        raise ConfigError(f"{p}: top level must be a mapping")
    return raw or {}


def load(path: Path | str | None = None) -> Config:
    raw = _read_raw(Path(path) if path else default_path())
    for path_, val in env_overrides().items():
        d, leaf = _dig(raw, path_)
        d[leaf] = val
    return parse(raw)


def _dump(cfg: Config) -> dict[str, Any]:
    return cfg.model_dump(by_alias=True)


def save(cfg: Config, path: Path | str) -> None:
    """Write the config; values that came from the environment are not written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = _dump(cfg)
    old = _read_raw(p) if p.is_file() else {}
    for path_ in env_overrides():
        d, leaf = _dig(data, path_)
        src: Any = old
        for k in path_.split("."):
            src = src.get(k) if isinstance(src, dict) else None
        d[leaf] = src if isinstance(src, str) else ""
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, p)


def _secret_paths(model: type[BaseModel], prefix: str = "") -> list[str]:
    out: list[str] = []
    for name, f in model.model_fields.items():
        extra = f.json_schema_extra
        if isinstance(extra, dict) and extra.get("secret"):
            out.append(prefix + name)
        ann = f.annotation
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            out += _secret_paths(ann, f"{prefix}{name}.")
    return out


SECRET_PATHS = tuple(_secret_paths(Config))
READ_ONLY_HTTP = ("server.data_dir", "server.host", "server.port", "ffmpeg.binary",
                  "ffmpeg.probe_binary")


def masked(cfg: Config) -> dict[str, Any]:
    d = _dump(cfg)
    for path in SECRET_PATHS:
        parent, leaf = _dig(d, path)
        if parent.get(leaf):
            parent[leaf] = MASK
    d["ai"]["keys"] = {k: MASK for k, v in (d["ai"].get("keys") or {}).items() if v}
    return d


def merge_update(current: Config, incoming: dict[str, Any]) -> Config:
    """Apply a settings payload (any subset of sections). A masked secret keeps
    its stored value; unknown keys and read-only fields are refused."""
    merged = _dump(current)

    def walk(dst: dict[str, Any], src: dict[str, Any], prefix: str) -> None:
        for k, v in src.items():
            path = prefix + k
            if path == "ai.keys" and isinstance(v, dict):
                # per-provider keys: the mask keeps a key, "" removes it, text sets it
                keys = dict(dst.get(k) or {})
                for prov, key in v.items():
                    if key == MASK:
                        continue
                    if key:
                        keys[str(prov)] = str(key).strip()
                    else:
                        keys.pop(str(prov), None)
                dst[k] = keys
                continue
            if k not in dst:
                raise ConfigError(f"unknown setting {path!r}")
            if isinstance(v, dict) and isinstance(dst.get(k), dict) and k != "steps":
                walk(dst[k], v, path + ".")
            elif v != MASK:
                if path in READ_ONLY_HTTP and v != dst[k]:
                    raise ConfigError(f"{path} can only be changed in config.yaml")
                dst[k] = copy.deepcopy(v)

    walk(merged, incoming, "")
    return parse(merged)
