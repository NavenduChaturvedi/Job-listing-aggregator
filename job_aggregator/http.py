"""Polite HTTP fetching, shared by every source adapter.

Guarantees for callers:
  * robots.txt is checked (and cached) before any URL is fetched
  * a site's declared Crawl-delay is honoured if it is longer than our default
  * at least ``config.REQUEST_DELAY`` seconds pass between any two requests
  * HTTP 429 / 5xx / connection errors are retried with exponential back-off
  * one failure type to catch: ``FetchError`` (``RobotsDisallowed`` is a subclass)
"""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from . import config


class FetchError(Exception):
    """A URL could not be retrieved."""


class RobotsDisallowed(FetchError):
    """robots.txt forbids fetching this URL for our User-Agent."""


class Fetcher:
    """Stateful helper: one per run, reused across all sources so the global
    rate limit and the robots cache are actually shared."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept-Language": "en;q=0.9",
            }
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request_at = 0.0

    # -- robots --------------------------------------------------------
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        origin = _origin(url)
        cached = self._robots.get(origin)
        if cached is not None:
            return cached

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        # Fetch robots.txt with OUR session/User-Agent. urllib.robotparser's own
        # fetcher uses a python-urllib UA that some sites (Cloudflare) answer
        # with 403 - which the stdlib then reads as "disallow everything".
        try:
            resp = self._session.get(f"{origin}/robots.txt", timeout=config.REQUEST_TIMEOUT)
        except requests.RequestException:
            parser.parse([])  # unreachable -> assume no rules (fail open)
            self._robots[origin] = parser
            return parser

        if resp.status_code == 200:
            parser.parse(resp.text.splitlines())
        elif 400 <= resp.status_code < 500:
            # RFC 9309: an "unavailable" robots.txt means crawl freely.
            parser.parse([])
        else:
            # 5xx: server trouble. Be conservative for this origin.
            parser.disallow_all = True

        self._robots[origin] = parser
        return parser

    def _allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(config.USER_AGENT, url)

    def _crawl_delay(self, url: str) -> float:
        try:
            declared = self._robots_for(url).crawl_delay(config.USER_AGENT)
        except Exception:
            declared = None
        return max(config.REQUEST_DELAY, float(declared or 0))

    # -- fetching -----------------------------------------------------
    def get(self, url: str) -> requests.Response:
        if not self._allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

        self._respect_rate_limit(self._crawl_delay(url))

        last_error: Exception | None = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, timeout=config.REQUEST_TIMEOUT)
            except requests.RequestException as exc:
                last_error = exc
                _sleep_backoff(attempt, str(exc))
                continue

            if resp.status_code == 200:
                return resp
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = FetchError(f"HTTP {resp.status_code}")
                _sleep_backoff(attempt, f"HTTP {resp.status_code}", _retry_after(resp))
                continue
            raise FetchError(f"HTTP {resp.status_code} for {url}")

        raise FetchError(f"gave up on {url} after {config.MAX_RETRIES} tries: {last_error}")

    def get_json(self, url: str):
        try:
            return self.get(url).json()
        except ValueError as exc:
            raise FetchError(f"invalid JSON from {url}: {exc}") from exc

    def get_text(self, url: str) -> str:
        return self.get(url).text

    # -- internals --------------------------------------------------
    def _respect_rate_limit(self, min_gap: float) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)
        self._last_request_at = time.monotonic()


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _retry_after(resp: requests.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _sleep_backoff(attempt: int, reason: str, floor: float | None = None) -> None:
    delay = max(2.0 ** (attempt - 1), floor or 0)
    print(f"    retry {attempt}/{config.MAX_RETRIES} in {delay:.0f}s ({reason})")
    time.sleep(delay)
