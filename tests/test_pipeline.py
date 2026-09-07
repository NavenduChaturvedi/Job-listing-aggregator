"""Offline tests for filtering and de-duplication."""

from job_aggregator import pipeline
from job_aggregator.models import Job


def _job(**kw) -> Job:
    base = dict(
        source="s",
        title="t",
        company="c",
        location="Remote",
        url="",
        posted_date="2026-09-01",
        tags=[],
        description="",
    )
    base.update(kw)
    return Job(**base)


def test_dedup_by_url_ignores_scheme_and_trailing_slash():
    jobs = [
        _job(title="Job One A", url="https://x.com/jobs/1"),
        _job(title="Job One B", url="http://x.com/jobs/1/"),  # same URL, scheme/slash differ
        _job(title="Job Two", url="https://x.com/jobs/2"),
    ]
    df, removed = pipeline.deduplicate(pipeline.to_dataframe(jobs))
    assert removed == 1
    assert len(df) == 2


def test_dedup_by_title_and_company_across_sources():
    jobs = [
        _job(source="remoteok", title="Senior Python Dev", company="Acme", url="https://a.com/1"),
        _job(
            source="weworkremotely",
            title="senior python dev",
            company="ACME!",
            url="https://b.com/2",
        ),
    ]
    df, removed = pipeline.deduplicate(pipeline.to_dataframe(jobs))
    assert removed == 1
    assert len(df) == 1


def test_keyword_filter_requires_all_terms():
    jobs = [
        _job(title="Python Developer", description="django rest"),
        _job(title="Java Developer", description="spring boot"),
        _job(title="Ops Engineer", tags=["kubernetes"], description="backend"),
    ]
    df = pipeline.filter_jobs(pipeline.to_dataframe(jobs), keyword="python developer")
    assert set(df["title"]) == {"Python Developer"}


def test_location_filter_remote_matches_synonyms():
    jobs = [
        _job(title="A", location="Anywhere in the World"),
        _job(title="B", location="USA Only"),
        _job(title="C", location=""),
    ]
    df = pipeline.filter_jobs(pipeline.to_dataframe(jobs), location="remote")
    assert set(df["title"]) == {"A", "C"}


def test_max_age_days_keeps_undated_rows():
    jobs = [
        _job(title="fresh", posted_date="2026-09-06"),
        _job(title="stale", posted_date="2020-01-01"),
        _job(title="undated", posted_date=None),
    ]
    df = pipeline.filter_jobs(pipeline.to_dataframe(jobs), max_age_days=30)
    titles = set(df["title"])
    assert "stale" not in titles
    assert "undated" in titles
