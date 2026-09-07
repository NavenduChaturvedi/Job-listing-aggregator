"""Shared base class for source adapters."""

from __future__ import annotations

from ..http import Fetcher
from ..models import Job


class Source:
    #: short, CLI-friendly identifier (e.g. "remoteok")
    name: str = ""

    #: human-readable, shown in output
    label: str = ""

    def fetch(
        self,
        fetcher: Fetcher,
        keyword: str | None = None,
        location: str | None = None,
    ) -> list[Job]:  # pragma: no cover - interface
        """Return listings from this source.

        ``keyword`` / ``location`` are hints: a source that can filter server
        side (RemoteOK's ``?tag=``) should use them to fetch less; sources that
        cannot just ignore them and let the central pipeline filter.
        """
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Source {self.name}>"
