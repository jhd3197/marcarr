"""Shared HTTP base for the Plex client: session, timeout, retry on transient errors."""

from __future__ import annotations

import time
from typing import Any

import requests

from ..errors import ClientError

MAX_IMAGE = 20_000_000  # bytes; a bigger "poster" is not one


def read_capped(resp: requests.Response, limit: int) -> bytes | None:
    """The body of a streamed response, or None once it passes `limit` bytes."""
    declared = resp.headers.get("Content-Length", "")
    if declared.isdigit() and int(declared) > limit:
        return None
    buf = bytearray()
    for chunk in resp.iter_content(1 << 16):
        buf += chunk
        if len(buf) > limit:
            return None
    return bytes(buf)


class BaseClient:
    service = "service"
    max_retries = 2
    backoff = 0.5
    max_wait = 30.0

    def __init__(self, base_url: str, timeout: float = 30, headers: dict[str, str] | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    def get_image(self, path: str, params: dict[str, Any] | None = None) -> bytes | None:
        """An image's bytes, or None when the server has none (no retries: art is optional).

        Raises ClientError when the server could not be asked (down, timeout, 5xx,
        429): that is not "no art", and callers must not remember it as such."""
        try:
            resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout,
                                    headers={"Accept": "image/*"}, stream=True)
        except requests.RequestException as exc:
            raise ClientError(f"{self.service} unreachable: {exc.__class__.__name__}") from exc
        with resp:
            if resp.status_code == 429 or resp.status_code >= 500:
                raise ClientError(f"{self.service} returned HTTP {resp.status_code}",
                                  resp.status_code)
            ctype = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or not ctype.startswith("image/"):
                return None
            return read_capped(resp, MAX_IMAGE) or None

    def _once(self, path: str, params: dict[str, Any] | None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ClientError(f"{self.service} unreachable: {exc.__class__.__name__}") from exc
        if resp.status_code in (401, 403):
            raise ClientError(f"{self.service} rejected the credentials", resp.status_code)
        if resp.status_code >= 400:
            raise ClientError(
                f"{self.service} returned HTTP {resp.status_code}",
                resp.status_code,
                resp.headers.get("Retry-After"),
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise ClientError(f"{self.service} sent a non-JSON reply", resp.status_code) from exc

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(self.max_retries + 1):
            try:
                return self._once(path, params)
            except ClientError as exc:
                transient = exc.status is None or exc.status == 429 or exc.status >= 500
                if not transient or attempt == self.max_retries:
                    raise
                delay = self.backoff * 2**attempt
                if exc.retry_after and exc.retry_after.isdigit():
                    delay = max(delay, float(exc.retry_after))
                time.sleep(min(delay, self.max_wait))
        raise AssertionError("unreachable")  # pragma: no cover
