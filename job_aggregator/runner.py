"""Orchestration: run the sources, build the table, filter, dedup, export.

This is the one place that knows the whole flow. It owns the "one source
failing must not kill the run" error handling; the adapters just raise.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import export, pipeline
from .http import Fetcher, FetchError
from .sources import get_sources


@dataclass
class AggregateResult:
    df: pd.DataFrame
    stats: pipeline.RunStats


def aggregate(
    source_names: list[str] | None = None,
    keyword: str | None = None,
    location: str | None = None,
    max_age_days: int | None = None,
    limit: int | None = None,
) -> AggregateResult:
    sources = get_sources(source_names)
    fetcher = Fetcher()
    stats = pipeline.RunStats()

    all_jobs = []
    for source in sources:
        try:
            jobs = source.fetch(fetcher, keyword=keyword, location=location)
        except FetchError as exc:
            stats.errors[source.name] = str(exc)
            print(f"  ! {source.label}: {exc}")
            continue
        except Exception as exc:  # never let one bad adapter abort the run
            stats.errors[source.name] = repr(exc)
            print(f"  ! {source.label}: unexpected error: {exc!r}")
            continue

        stats.per_source[source.name] = len(jobs)
        all_jobs.extend(jobs)
        print(f"  {source.label}: {len(jobs)} listings")

    stats.scraped = len(all_jobs)

    df = pipeline.to_dataframe(all_jobs)
    df = pipeline.filter_jobs(df, keyword=keyword, location=location, max_age_days=max_age_days)
    stats.after_filter = len(df)

    df, removed = pipeline.deduplicate(df)
    stats.duplicates_removed = removed

    df = pipeline.sort_for_output(df)
    if limit is not None:
        df = df.head(limit).reset_index(drop=True)
    stats.final = len(df)

    return AggregateResult(df=df, stats=stats)


def run_cli(args) -> int:
    """Entry point used by aggregator.py. Returns a process exit code."""
    print("Scraping sources...")
    result = aggregate(
        source_names=args.source,
        keyword=args.keyword,
        location=args.location,
        max_age_days=args.max_age_days,
        limit=args.limit,
    )

    print(result.stats.render(args.keyword, args.location))

    if result.df.empty:
        print("\nNo listings matched. Nothing to export.")
        # every source erroring is a real failure; "0 matches" is not
        return 1 if result.stats.errors and not result.stats.per_source else 0

    if not args.no_export:
        csv_path = _join(args.output_dir, args.csv)
        json_path = _join(args.output_dir, args.json)
        export.write_csv(result.df, csv_path)
        export.write_json(result.df, json_path)
        print(f"\nWrote {csv_path}")
        print(f"Wrote {json_path}")

    if args.print_table:
        _print_table(result.df)

    return 0


def _join(directory: str | None, filename: str) -> str:
    import os

    return os.path.join(directory, filename) if directory else filename


def _print_table(df, rows: int = 20) -> None:
    shown = df.head(rows)
    print(f"\nTop {len(shown)} of {len(df)}:")
    for _, r in shown.iterrows():
        date = r["posted_date"] or "----------"
        print(f"  [{date}] {r['title']} @ {r['company']} ({r['location']}) - {r['source']}")
        print(f"           {r['url']}")
