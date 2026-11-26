"""The models Marcarr can use, from Prompture: what each configured provider
offers right now (live lists where the provider has one), with what each model
can do and what it costs, for the model picker in Settings > AI.

Only chat models that answer in text are listed: image, speech, embedding and
moderation models can't tag a scene.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import threading
import time
from typing import Any

from .config import AICfg

log = logging.getLogger("marcarr.models")
TTL = 600.0
NOT_CHAT = re.compile(r"image|dall-e|sora|tts|whisper|transcribe|audio|realtime|embed|moderation|"
                      r"search|computer-use|codex-mini|vision-preview", re.IGNORECASE)
_cache: dict[str, Any] = {}
_lock = threading.Lock()


def _env_fields() -> dict[str, str]:
    """Prompture provider name -> the ProviderEnvironment field for its key."""
    from prompture.infra.provider_env import ProviderEnvironment

    out = {}
    for f in dataclasses.fields(ProviderEnvironment):
        if f.name.endswith("_api_key"):
            out[f.name[: -len("_api_key")]] = f.name
    return out


def key_providers() -> list[str]:
    """Providers that take an API key (for "Add a key")."""
    skip = {"azure", "cachibot", "elevenlabs", "stability", "lmstudio"}  # not chat, or an endpoint
    return sorted(p for p in _env_fields() if not p.startswith("azure") and p not in skip)


def environment(cfg: AICfg) -> Any:
    from prompture.infra.provider_env import ProviderEnvironment

    fields = _env_fields()
    kw: dict[str, str] = {}
    for prov, key in (cfg.keys or {}).items():
        if key and prov in fields:
            kw[fields[prov]] = key
    for model in (cfg.model, cfg.vision_model):  # the old single key belongs to the chosen model
        prov = model.split("/", 1)[0] if "/" in model else ""
        if cfg.api_key and prov in fields and fields[prov] not in kw:
            kw[fields[prov]] = cfg.api_key
    if cfg.base_url and "ollama" in (cfg.model + cfg.vision_model):
        kw["ollama_endpoint"] = cfg.base_url
    return ProviderEnvironment(**kw)


def _model_row(provider: str, model_id: str) -> dict[str, Any] | None:
    from prompture.infra.model_rates import get_model_capabilities, get_model_rates

    if NOT_CHAT.search(model_id):
        return None
    try:
        caps = get_model_capabilities(provider, model_id)
        rates = get_model_rates(provider, model_id)
    except Exception:  # noqa: BLE001 - no catalog entry: still listed, marked unknown
        caps, rates = None, None
    if caps is not None and caps.modalities_output and tuple(caps.modalities_output) != ("text",):
        return None
    return {
        "id": f"{provider}/{model_id}", "name": model_id,
        "vision": None if caps is None else bool(caps.supports_vision),
        "reasoning": None if caps is None else bool(caps.is_reasoning),
        "context": getattr(caps, "context_window", None) or None,
        "input_price": (rates or {}).get("input"), "output_price": (rates or {}).get("output"),
    }


def available(cfg: AICfg, refresh: bool = False) -> dict[str, Any]:
    """{"providers": [{id, name, source, models: [...]}], "keys": [...]} (cached 10 min)."""
    key = repr(sorted((cfg.keys or {}).items())) + cfg.api_key + cfg.model + cfg.vision_model + cfg.base_url
    with _lock:
        hit = _cache.get("v")
        if hit and not refresh and hit[0] == key and time.time() - hit[1] < TTL:
            return hit[2]
    from prompture.infra.discovery import get_available_models

    # Providers that can't be reached (no local LM Studio, say) log their errors:
    # quiet them, a missing provider is just absent from the list.
    quiet = logging.getLogger("prompture")
    level = quiet.level
    quiet.setLevel(logging.CRITICAL)
    try:
        grouped = get_available_models(env=environment(cfg), grouped=True, force_refresh=refresh)
    finally:
        quiet.setLevel(level)
    providers = []
    for prov, d in sorted(grouped.items()):
        rows = [r for m in d.get("models") or [] if (r := _model_row(prov, str(m)))]
        if rows:
            providers.append({"id": prov, "name": d.get("display_name") or prov,
                              "source": d.get("source") or "", "models": rows})
    have = {p["id"] for p in providers}
    keys = [{"provider": p, "set": bool((cfg.keys or {}).get(p)), "listed": p in have}
            for p in key_providers()]
    out = {"providers": providers, "keys": keys}
    with _lock:
        _cache["v"] = (key, time.time(), out)
    return out
