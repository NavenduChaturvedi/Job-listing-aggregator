"""Flask dashboard for the job aggregator.

    GET  /                 search form + results table + stats
    GET  /export.csv       same query -> CSV download
    GET  /export.json      same query -> JSON download

All three take the same query parameters:
    keyword, location, source (repeatable), max_age_days, limit

Results are cached in-process for a few minutes so hitting "Download CSV" right
after a search does not scrape every board again.
"""

from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlencode

from flask import Flask, Response, render_template, request

from job_aggregator import export
from job_aggregator.runner import aggregate
from job_aggregator.sources import REGISTRY

# How long a search result is reused before we scrape again. Longer on a public
# deployment (set WEB_CACHE_TTL) so a shared URL does not re-scrape per visitor.
_CACHE_TTL = int(os.environ.get("WEB_CACHE_TTL", "300"))

# Minimum seconds between two *live* scrapes, across all visitors. 0 = no limit
# (fine locally). Set WEB_SCRAPE_MIN_INTERVAL on a public deploy to shield the
# upstream boards: while inside the window we serve a stale cached result if we
# have one instead of scraping again.
_SCRAPE_MIN_INTERVAL = float(os.environ.get("WEB_SCRAPE_MIN_INTERVAL", "0"))

_CACHE: dict[tuple, tuple[float, object]] = {}
_scrape_lock = threading.Lock()
_last_scrape_at = 0.0


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        query = _read_query(request.args)
        result = None
        if _has_search(query):
            result = _aggregate_cached(query)
        return render_template(
            "index.html",
            sources=REGISTRY,
            query=query,
            querystring=_querystring(query),
            result=result,
            rows=_rows(result) if result is not None else None,
        )

    @app.get("/export.csv")
    def export_csv():
        result = _aggregate_cached(_read_query(request.args))
        return _download(export.csv_bytes(result.df), "jobs.csv", "text/csv")

    @app.get("/export.json")
    def export_json():
        result = _aggregate_cached(_read_query(request.args))
        return _download(export.json_bytes(result.df), "jobs.json", "application/json")

    return app


# --------------------------------------------------------------------------
# query parsing / caching
# --------------------------------------------------------------------------
def _read_query(args) -> dict:
    chosen = [s for s in args.getlist("source") if s in REGISTRY]
    return {
        "keyword": (args.get("keyword") or "").strip(),
        "location": (args.get("location") or "").strip(),
        "sources": chosen,
        "max_age_days": _int_or_none(args.get("max_age_days")),
        "limit": _int_or_none(args.get("limit")),
    }


def _has_search(query: dict) -> bool:
    return bool(
        query["keyword"]
        or query["location"]
        or query["sources"]
        or query["max_age_days"]
        or query["limit"]
    )


def _cache_key(query: dict) -> tuple:
    return (
        query["keyword"].lower(),
        query["location"].lower(),
        tuple(sorted(query["sources"])),
        query["max_age_days"],
        query["limit"],
    )


def _cache_get(key: tuple):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    return None


def _aggregate_cached(query: dict):
    global _last_scrape_at
    key = _cache_key(query)

    fresh = _cache_get(key)
    if fresh is not None:
        return fresh

    # Serialise scraping: concurrent visitors asking the same thing wait for the
    # first one instead of all hitting the boards at once.
    with _scrape_lock:
        fresh = _cache_get(key)
        if fresh is not None:
            return fresh

        if _SCRAPE_MIN_INTERVAL and time.time() - _last_scrape_at < _SCRAPE_MIN_INTERVAL:
            stale = _CACHE.get(key)
            if stale is not None:
                return stale[1]

        result = aggregate(
            source_names=query["sources"] or None,
            keyword=query["keyword"] or None,
            location=query["location"] or None,
            max_age_days=query["max_age_days"],
            limit=query["limit"],
        )
        _last_scrape_at = time.time()
        _CACHE[key] = (_last_scrape_at, result)
        return result


# --------------------------------------------------------------------------
# view helpers
# --------------------------------------------------------------------------
def _rows(result) -> list[dict]:
    return result.df.to_dict(orient="records")


def _querystring(query: dict) -> str:
    pairs: list[tuple[str, str]] = []
    if query["keyword"]:
        pairs.append(("keyword", query["keyword"]))
    if query["location"]:
        pairs.append(("location", query["location"]))
    pairs.extend(("source", s) for s in query["sources"])
    if query["max_age_days"] is not None:
        pairs.append(("max_age_days", str(query["max_age_days"])))
    if query["limit"] is not None:
        pairs.append(("limit", str(query["limit"])))
    return urlencode(pairs)


def _download(payload: bytes, filename: str, mimetype: str) -> Response:
    return Response(
        payload,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _int_or_none(raw: str | None) -> int | None:
    try:
        return int(raw) if raw not in (None, "") else None
    except ValueError:
        return None


app = create_app()
