"""Language-model calls, through Prompture.

The model is a Prompture model string ("claude/claude-sonnet-5-5",
"ollama/qwen3-vl:8b", "google/gemini-2.5-flash"). With ``ai.base_url`` set and
a bare model name, the endpoint is treated as OpenAI-compatible (Ollama's /v1,
LM Studio, a gateway).

Every call adds its cost to the current :class:`Meter`, so a step knows what
it spent (the Activity page shows it per video and per month).
"""

from __future__ import annotations

import contextlib
import re
import threading
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ValidationError

from .config import AICfg
from .errors import MarcarrError


class AIError(MarcarrError):
    pass


class Meter:
    """Dollars and tokens spent by the calls made inside ``metered()``."""

    def __init__(self) -> None:
        self.cost = 0.0
        self.tokens = 0
        self.calls = 0

    def add(self, usage: dict[str, Any] | None) -> None:
        usage = usage or {}
        self.calls += 1
        try:
            self.cost += float(usage.get("cost") or 0.0)
        except (TypeError, ValueError):
            pass
        try:
            self.tokens += int(usage.get("total_tokens") or 0)
        except (TypeError, ValueError):
            pass


_local = threading.local()


@contextlib.contextmanager
def metered() -> Iterator[Meter]:
    """Count the cost of every AI call made on this thread inside the block."""
    meter = Meter()
    prev = getattr(_local, "meter", None)
    _local.meter = meter
    try:
        yield meter
    finally:
        _local.meter = prev
        if prev is not None:
            prev.cost += meter.cost
            prev.tokens += meter.tokens
            prev.calls += meter.calls


def _record(usage: dict[str, Any] | None) -> None:
    meter = getattr(_local, "meter", None)
    if meter is not None:
        meter.add(usage)
    hook = getattr(_local, "on_call", None)
    if hook is not None and usage:
        hook(usage)


def on_call(fn: Any) -> None:
    """Called with the usage of each model call made on this thread (the live log)."""
    _local.on_call = fn


def model_spec(cfg: AICfg, *, vision: bool = False) -> tuple[str, dict[str, Any]]:
    """The Prompture model string and driver overrides for this config."""
    model = (cfg.vision_model if vision and cfg.vision_model else cfg.model).strip()
    if not model:
        raise AIError("no AI model is set (Settings > AI)")
    overrides: dict[str, Any] = {}
    provider = model.split("/", 1)[0] if "/" in model else ""
    if cfg.base_url and not provider:
        model = f"openai/{model}"
        overrides["base_url"] = cfg.base_url.rstrip("/")
        overrides["api_key"] = cfg.api_key or "not-needed"
    elif not provider:
        raise AIError(f"the model {model!r} needs a provider prefix such as ollama/, claude/ or "
                      "google/ (or set a base URL for an OpenAI-compatible endpoint)")
    else:
        key = (cfg.keys or {}).get(provider) or cfg.api_key
        if key:
            overrides["api_key"] = key
        if cfg.base_url and provider == "ollama":
            overrides["endpoint"] = cfg.base_url
    return model, overrides


def capabilities(model: str) -> Any | None:
    """Prompture's catalog entry for "provider/model" (vision, reasoning, limits)."""
    provider, _, model_id = model.partition("/")
    try:
        from prompture.infra.model_rates import get_model_capabilities

        return get_model_capabilities(provider, model_id)
    except Exception:  # noqa: BLE001 - an unknown model just has no catalog entry
        return None


REASONING_ROOM = 16_000  # a reasoning model thinks before it answers: both count


def call_options(cfg: AICfg, model: str, max_tokens: int) -> dict[str, Any]:
    """Options for one call. A reasoning model gets the configured effort and room
    for its thinking, or it can spend the whole budget before writing the answer."""
    opts: dict[str, Any] = {"timeout": cfg.timeout, "max_tokens": max_tokens, "temperature": 0.2}
    caps = capabilities(model)
    if caps is not None and caps.is_reasoning:
        opts["effort"] = cfg.effort
        room = max(max_tokens * 4, REASONING_ROOM)
        if caps.max_output_tokens:
            room = min(room, int(caps.max_output_tokens))
        opts["max_tokens"] = room
    return opts


def driver_for(cfg: AICfg, *, vision: bool = False) -> Any:
    model, overrides = model_spec(cfg, vision=vision)
    import prompture

    try:
        return prompture.get_driver_for_model(model, **overrides)
    except Exception as exc:  # noqa: BLE001 - any init failure means "unavailable"
        raise AIError(f"could not start {model}: {exc}") from exc


def ask_json(cfg: AICfg, schema: type[BaseModel], system: str, prompt: str, *,
             images: list[Any] | None = None, retries: int = 1, max_tokens: int = 4096) -> Any:
    """A validated instance of *schema*; *images* (bytes or paths) go to a vision model.

    An invalid reply is retried once with the validation error as feedback,
    then reported as AIError (never repaired into a guess).
    """
    import prompture
    from prompture.exceptions import ExtractionError

    vision = bool(images)
    driver = driver_for(cfg, vision=vision)
    model, _ = model_spec(cfg, vision=vision)
    feedback = ""
    last: Exception | None = None
    options = call_options(cfg, model, max_tokens)
    for _attempt in range(retries + 1):
        try:
            result = prompture.ask_for_json(
                driver=driver, content_prompt=prompt + feedback,
                json_schema=schema.model_json_schema(), system_prompt=system,
                model_name=model.split("/", 1)[-1], options=options,
                ai_cleanup=False, cache=False, images=images or None)
            _record(result.get("usage"))
            return schema.model_validate(result["json_object"])
        except (ExtractionError, ValidationError, KeyError, TypeError) as exc:
            last = exc
            _record(getattr(exc, "usage", None))  # a cut-off reply was still paid for
            if "max_tokens" in str(exc):
                # cut off, not wrong: the same question with more room
                options = {**options, "max_tokens": int(options["max_tokens"]) * 2}
                feedback = ""
                continue
            feedback = (f"\nThe previous answer was invalid: {str(exc)[:300]}. "
                        "Return JSON matching the schema exactly.")
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001 - transport failures
            raise AIError(f"{model} failed: {exc}") from exc
    raise AIError(f"{model} returned invalid JSON after {retries + 1} tries: {last}")


APPROX_RE = re.compile(r"^(?:(\d+):)?([0-5]?\d):([0-5]\d)$")


def parse_approx(s: Any) -> float:
    """ "1:02:03" / "05:10" / 310 -> seconds."""
    if isinstance(s, (int, float)):
        return float(s)
    m = APPROX_RE.match(str(s).strip())
    if not m:
        raise AIError(f"bad time {s!r} (use mm:ss or h:mm:ss)")
    h, mi, se = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(se)
