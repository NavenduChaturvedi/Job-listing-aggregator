"""Source adapters and their registry.

Each adapter is a callable ``fetch(fetcher) -> list[Job]`` with a ``.name``.
Adding a board means writing one module here and adding it to ``REGISTRY`` -
nothing else in the codebase changes.
"""

from __future__ import annotations

from .pythonorg import PythonOrgSource
from .remoteok import RemoteOkSource
from .weworkremotely import WeWorkRemotelySource

# name -> adapter instance
REGISTRY = {
    src.name: src
    for src in (RemoteOkSource(), WeWorkRemotelySource(), PythonOrgSource())
}


def get_sources(names: list[str] | None) -> list:
    """Resolve a list of source names to adapters. ``None`` means "all"."""
    if not names:
        return list(REGISTRY.values())
    chosen = []
    for name in names:
        try:
            chosen.append(REGISTRY[name])
        except KeyError:
            raise ValueError(
                f"unknown source {name!r}; available: {', '.join(REGISTRY)}"
            )
    return chosen
