"""Exception hierarchy; the server maps these onto HTTP statuses."""

from __future__ import annotations


class MarcarrError(Exception):
    """Base for every error FansCut raises on purpose."""


class ConfigError(MarcarrError):
    pass


class NotFoundError(MarcarrError):
    pass


class ClientError(MarcarrError):
    """A remote service (Sonarr, Plex, a catalogue) failed or refused."""

    def __init__(self, message: str, status: int | None = None, retry_after: str | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class FFmpegError(MarcarrError):
    pass


class JobCancelled(MarcarrError):
    pass
