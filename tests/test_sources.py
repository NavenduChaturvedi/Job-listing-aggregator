"""Offline tests for the source adapters.

Each adapter is fed a saved fixture through a fake fetcher, so the suite never
touches the network.

    python -m pytest            (needs: pip install pytest)
"""

import json
import os

from job_aggregator.sources.pythonorg import PythonOrgSource
from job_aggregator.sources.remoteok import RemoteOkSource
from job_aggregator.sources.weworkremotely import WeWorkRemotelySource

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


class FakeFetcher:
    """Returns canned content regardless of URL."""

    def __init__(self, text: str):
        self._text = text

    def get_text(self, url):
        return self._text

    def get_json(self, url):
        return json.loads(self._text)


def test_remoteok_parses_and_skips_non_jobs():
    jobs = RemoteOkSource().fetch(FakeFetcher(_read("remoteok.json")))
    # legal notice + the {"id": "789"} row without a position are skipped
    assert len(jobs) == 2

    first = jobs[0]
    assert first.title == "Senior Python Developer"
    assert first.company == "Acme Corp"
    assert first.location == "Remote"          # empty string -> "Remote"
    assert first.posted_date == "2026-09-05"
    assert "python" in first.tags
    assert first.source == "remoteok"
    assert "<strong>" not in first.description  # HTML stripped


def test_weworkremotely_splits_company_and_title():
    jobs = WeWorkRemotelySource().fetch(FakeFetcher(_read("wwr.rss")))
    assert len(jobs) == 2

    a = jobs[0]
    assert a.company == "Acme Corp"
    assert a.title == "Senior Python Developer"
    assert a.location == "Anywhere in the World"
    assert a.posted_date == "2026-09-07"
    assert a.tags == ["Back-End Programming"]

    # no ": " in the title -> company empty, whole string kept as title
    b = jobs[1]
    assert b.company == ""
    assert b.title == "Design Studio Frontend Wizard"


def test_pythonorg_extracts_company_after_br():
    jobs = PythonOrgSource().fetch(FakeFetcher(_read("pythonorg.html")))
    assert len(jobs) == 2

    a = jobs[0]
    assert a.title == "Senior Python Developer"
    assert a.company == "Adzuna"
    assert a.location == "Remote, Remote"
    assert a.url == "https://www.python.org/jobs/8131/"
    assert a.posted_date == "2026-09-03"
    assert "Back end" in a.tags

    assert jobs[1].company == "Contralto Ltd"
