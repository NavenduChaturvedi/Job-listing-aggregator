"""The ``Job`` record and the normalisation helpers used to build one.

Every source adapter produces ``Job`` objects, so the rest of the pipeline only
ever deals with this one shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

_WHITESPACE = re.compile(r"\s+")


@dataclass
class Job:
    source: str
    title: str
    company: str
    location: str
    url: str
    posted_date: Optional[str]  # ISO date "YYYY-MM-DD", or None if unknown
    tags: list[str] = field(default_factory=list)
    description: str = ""  # short plain-text snippet, not the full posting

    # --- keys used for de-duplication -----------------------------------
    @property
    def url_key(self) -> str:
        return normalize_url(self.url)

    @property
    def identity_key(self) -> str:
        """title + company, loosely normalised - catches the same job
        cross-posted to two boards under different URLs."""
        return f"{_loose(self.title)}|{_loose(self.company)}"


def _loose(text: str) -> str:
    """Lowercase, strip anything that is not a letter or digit."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def normalize_url(url: str) -> str:
    """Canonical form for comparison: lowercase host, no query/fragment, no
    trailing slash, http and https treated as the same."""
    if not url:
        return ""
    parts = urlparse(url.strip())
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    # scheme is deliberately dropped from the key by forcing it to "" below
    return urlunparse(("", netloc, path, "", "", "")).lstrip("/")


def clean_text(raw: str, *, limit: Optional[int] = None) -> str:
    """Strip HTML tags and collapse whitespace. Optionally truncate.

    Sources hand us description fields that range from plain text to fully
    escaped HTML; running everything through BeautifulSoup normalises both.
    """
    if not raw:
        return ""
    text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
    text = _WHITESPACE.sub(" ", text).strip()
    if limit is not None and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def parse_date(raw: Optional[str]) -> Optional[str]:
    """Best-effort conversion of a date string to an ISO ``YYYY-MM-DD``.

    Accepts ISO-8601 (RemoteOK, python.org ``<time datetime>``) and RFC-822
    (RSS ``<pubDate>``). Returns None if it cannot be parsed - a missing date
    should never break a run.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    raw = raw.strip()

    # ISO-8601, possibly with a trailing "Z"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        pass

    # RFC-822 (e.g. "Mon, 07 Sep 2026 14:09:46 +0000")
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError):
        return None


def days_old(iso_date: Optional[str]) -> Optional[int]:
    if not isinstance(iso_date, str) or not iso_date:
        return None
    try:
        posted = datetime.fromisoformat(iso_date).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - posted).days
