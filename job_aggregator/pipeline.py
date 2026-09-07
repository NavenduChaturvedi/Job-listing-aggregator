"""Turn a pile of ``Job`` objects into a clean, filtered, de-duplicated table.

pandas is used here because dedup, filtering and CSV/JSON export are exactly
what a dataframe is good at, and it keeps this module short and declarative.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .models import Job, days_old, normalize_url

COLUMNS = ["source", "title", "company", "location", "posted_date", "url", "tags", "description"]

# Words that all mean "this job is remote", used by the location filter.
_REMOTE_WORDS = ("remote", "anywhere", "worldwide", "distributed", "global")


@dataclass
class RunStats:
    per_source: dict[str, int] = field(default_factory=dict)
    scraped: int = 0
    after_filter: int = 0
    duplicates_removed: int = 0
    final: int = 0
    errors: dict[str, str] = field(default_factory=dict)

    def render(self, keyword: str | None, location: str | None) -> str:
        lines = ["", "Sources:"]
        for name, count in self.per_source.items():
            lines.append(f"  {name:<16}: {count} listings")
        for name, err in self.errors.items():
            lines.append(f"  {name:<16}: FAILED - {err}")

        crit = []
        if keyword:
            crit.append(f'keyword "{keyword}"')
        if location:
            crit.append(f'location "{location}"')
        crit_str = (" matching " + " and ".join(crit)) if crit else ""

        lines += [
            "",
            f"{self.scraped} listings scraped",
            f"{self.after_filter} listings{crit_str}",
            f"{self.duplicates_removed} duplicates removed",
            f"{self.final} unique listings",
        ]
        return "\n".join(lines)


def to_dataframe(jobs: list[Job]) -> pd.DataFrame:
    if not jobs:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame([_job_to_row(j) for j in jobs])
    return df[COLUMNS]


def _job_to_row(job: Job) -> dict:
    return {
        "source": job.source,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "posted_date": job.posted_date,
        "url": job.url,
        "tags": list(job.tags),
        "description": job.description,
    }


def filter_jobs(
    df: pd.DataFrame,
    keyword: str | None = None,
    location: str | None = None,
    max_age_days: int | None = None,
) -> pd.DataFrame:
    """Keep rows that match every supplied criterion (AND)."""
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)

    if keyword:
        # Every whitespace-separated term must appear in the row's searchable
        # text: title + company + description. Tags are deliberately excluded -
        # some sources (RemoteOK) attach dozens of unrelated tags to every
        # posting, which would make the keyword filter match everything.
        haystack = (
            df["title"].fillna("")
            + " "
            + df["company"].fillna("")
            + " "
            + df["description"].fillna("")
        ).str.lower()
        for term in keyword.lower().split():
            mask &= haystack.str.contains(_re_escape(term), regex=True)

    if location:
        loc_col = df["location"].fillna("").str.lower()
        wanted = location.lower().strip()
        if any(w in wanted for w in _REMOTE_WORDS):
            mask &= loc_col.apply(lambda v: any(w in v for w in _REMOTE_WORDS) or v == "")
        else:
            mask &= loc_col.str.contains(_re_escape(wanted), regex=True)

    if max_age_days is not None:
        age = df["posted_date"].apply(days_old)
        # keep rows with no usable date rather than silently dropping them
        mask &= age.apply(lambda d: pd.isna(d) or d <= max_age_days)

    return df[mask].reset_index(drop=True)


def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows that repeat a URL, then rows that repeat title+company.

    Returns the cleaned frame and the number of rows removed.
    """
    if df.empty:
        return df, 0

    before = len(df)
    work = df.copy()
    work["_url_key"] = work["url"].apply(normalize_url)
    work["_identity_key"] = (
        work["title"].fillna("").str.lower().str.replace(r"[^a-z0-9]+", "", regex=True)
        + "|"
        + work["company"].fillna("").str.lower().str.replace(r"[^a-z0-9]+", "", regex=True)
    )

    # URL dedup only where we actually have a URL
    has_url = work["_url_key"] != ""
    work = pd.concat(
        [
            work[has_url].drop_duplicates(subset="_url_key", keep="first"),
            work[~has_url],
        ]
    ).sort_index()

    work = work.drop_duplicates(subset="_identity_key", keep="first")

    cleaned = work.drop(columns=["_url_key", "_identity_key"]).reset_index(drop=True)
    return cleaned, before - len(cleaned)


def sort_for_output(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # newest first; rows without a date sink to the bottom
    return df.sort_values("posted_date", ascending=False, na_position="last").reset_index(drop=True)


def _re_escape(text: str) -> str:
    import re

    return re.escape(text)
