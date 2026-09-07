"""Tunable settings.

Kept tiny on purpose - this tool has no secrets and no accounts, so there is no
``.env`` to manage. Every value can still be overridden with an environment
variable for CI or one-off runs, e.g. ``REQUEST_DELAY=0 python aggregator.py ...``.
"""

from __future__ import annotations

import os


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


# Minimum seconds between two outgoing requests (any host). RemoteOK's
# robots.txt asks for Crawl-delay: 1; we default higher to be safe, and the
# fetcher also honours a larger crawl-delay if a site declares one.
REQUEST_DELAY = _float("REQUEST_DELAY", 2.0)

# Per-request network timeout.
REQUEST_TIMEOUT = _float("REQUEST_TIMEOUT", 25.0)

# Retries for transient failures (HTTP 429 / 5xx / connection errors).
MAX_RETRIES = _int("MAX_RETRIES", 3)

# Sent with every request so site owners can see who we are.
USER_AGENT = os.environ.get(
    "USER_AGENT",
    "job-aggregator-bot/1.0 "
    "(+https://github.com/NavenduChaturvedi/Job-listing-aggregator)",
)
