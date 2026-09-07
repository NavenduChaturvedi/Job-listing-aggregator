"""Smoke tests for the optional Flask dashboard.

Skipped automatically if Flask is not installed (it is not a core dependency).
``aggregate`` is monkeypatched so nothing here touches the network.
"""

import json

import pytest

pytest.importorskip("flask")

from job_aggregator import pipeline  # noqa: E402
from job_aggregator.runner import AggregateResult  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    from webapp import app as webapp

    empty = AggregateResult(
        df=pipeline.to_dataframe([]),
        stats=pipeline.RunStats(per_source={"pythonorg": 0}),
    )
    monkeypatch.setattr(webapp, "aggregate", lambda **_: empty)
    webapp._CACHE.clear()
    return webapp.app.test_client()


def test_landing_page_renders_without_scraping(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Job Listing Aggregator" in resp.data


def test_search_with_no_matches(client):
    resp = client.get("/?keyword=nothingmatchesthis")
    assert resp.status_code == 200
    assert b"No listings matched" in resp.data


def test_csv_export_headers(client):
    resp = client.get("/export.csv?keyword=x")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert resp.data.splitlines()[0].startswith(b"source,title,company")


def test_json_export_is_valid_json(client):
    resp = client.get("/export.json?keyword=x")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert json.loads(resp.data) == []
